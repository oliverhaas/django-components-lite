# ruff: noqa: N802
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import (
    NamedTuple,
    TypeVar,
    cast,
)

from django.conf import settings

from django_components_lite.util.misc import default

T = TypeVar("T")


# This is the source of truth for the settings that are available. If the documentation
# or the defaults do NOT match this, they should be updated.
class ComponentsSettings(NamedTuple):
    """
    Settings available for django_components_lite.

    **Example:**

    ```python
    COMPONENTS = ComponentsSettings(
        autodiscover=False,
        dirs = [BASE_DIR / "components"],
    )
    ```
    """

    autodiscover: bool | None = None
    """
    Toggle whether to run [autodiscovery](../concepts/fundamentals/autodiscovery.md) at the Django server startup.

    Defaults to `True`

    ```python
    COMPONENTS = ComponentsSettings(
        autodiscover=False,
    )
    ```
    """

    dirs: Sequence[str | PathLike | tuple[str, str] | tuple[str, PathLike]] | None = None
    """
    Specify the directories that contain your components.

    Defaults to `[Path(settings.BASE_DIR) / "components"]`. That is, the root `components/` app.

    Directories must be full paths, same as with
    [STATICFILES_DIRS](https://docs.djangoproject.com/en/5.2/ref/settings/#std-setting-STATICFILES_DIRS).

    These locations are searched during [autodiscovery](../concepts/fundamentals/autodiscovery.md),
    or when you [define HTML, JS, or CSS as separate files](../concepts/fundamentals/html_js_css_files.md).

    ```python
    COMPONENTS = ComponentsSettings(
        dirs=[BASE_DIR / "components"],
    )
    ```

    Set to empty list to disable global components directories:

    ```python
    COMPONENTS = ComponentsSettings(
        dirs=[],
    )
    ```
    """

    app_dirs: Sequence[str] | None = None
    """
    Specify the app-level directories that contain your components.

    Defaults to `["components"]`. That is, for each Django app, we search `<app>/components/` for components.

    The paths must be relative to app, e.g.:

    ```python
    COMPONENTS = ComponentsSettings(
        app_dirs=["my_comps"],
    )
    ```

    To search for `<app>/my_comps/`.

    These locations are searched during [autodiscovery](../concepts/fundamentals/autodiscovery.md),
    or when you [define HTML, JS, or CSS as separate files](../concepts/fundamentals/html_js_css_files.md).

    Set to empty list to disable app-level components:

    ```python
    COMPONENTS = ComponentsSettings(
        app_dirs=[],
    )
    ```
    """

    cache: str | None = None
    """
    Name of the [Django cache](https://docs.djangoproject.com/en/5.2/topics/cache/)
    to be used for storing component's JS and CSS files.

    If `None`, a [`LocMemCache`](https://docs.djangoproject.com/en/5.2/topics/cache/#local-memory-caching)
    is used with default settings.

    Defaults to `None`.

    Read more about [caching](../guides/setup/caching.md).

    ```python
    COMPONENTS = ComponentsSettings(
        cache="my_cache",
    )
    ```
    """

    multiline_tags: bool | None = None
    """
    Enable / disable
    [multiline support for template tags](../concepts/fundamentals/template_tag_syntax.md#multiline-tags).
    If `True`, template tags like `{% component %}` or `{{ my_var }}` can span multiple lines.

    Defaults to `True`.

    Disable this setting if you are making custom modifications to Django's
    regular expression for parsing templates at `django.template.base.tag_re`.

    ```python
    COMPONENTS = ComponentsSettings(
        multiline_tags=False,
    )
    ```
    """

    static_files_allowed: list[str | re.Pattern] | None = None
    """
    A list of file extensions (including the leading dot) that define which files within
    [`COMPONENTS.dirs`](./settings.md#django_components_lite.app_settings.ComponentsSettings.dirs)
    or
    [`COMPONENTS.app_dirs`](./settings.md#django_components_lite.app_settings.ComponentsSettings.app_dirs)
    are treated as [static files](https://docs.djangoproject.com/en/5.2/howto/static-files/).

    If a file is matched against any of the patterns, it's considered a static file. Such files are collected
    when running [`collectstatic`](https://docs.djangoproject.com/en/5.2/ref/contrib/staticfiles/#collectstatic),
    and can be accessed under the
    [static file endpoint](https://docs.djangoproject.com/en/5.2/ref/settings/#static-url).

    You can also pass in compiled regexes ([`re.Pattern`](https://docs.python.org/3/library/re.html#re.Pattern))
    for more advanced patterns.

    By default, JS, CSS, and common image and font file formats are considered static files:

    ```python
    COMPONENTS = ComponentsSettings(
        static_files_allowed=[
            ".css",
            ".js", ".jsx", ".ts", ".tsx",
            # Images
            ".apng", ".png", ".avif", ".gif", ".jpg",
            ".jpeg",  ".jfif", ".pjpeg", ".pjp", ".svg",
            ".webp", ".bmp", ".ico", ".cur", ".tif", ".tiff",
            # Fonts
            ".eot", ".ttf", ".woff", ".otf", ".svg",
        ],
    )
    ```

    !!! warning

        Exposing your Python files can be a security vulnerability.
        See [Security notes](../overview/security_notes.md).
    """

    static_files_forbidden: list[str | re.Pattern] | None = None
    """
    A list of file extensions (including the leading dot) that define which files within
    [`COMPONENTS.dirs`](./settings.md#django_components_lite.app_settings.ComponentsSettings.dirs)
    or
    [`COMPONENTS.app_dirs`](./settings.md#django_components_lite.app_settings.ComponentsSettings.app_dirs)
    will NEVER be treated as [static files](https://docs.djangoproject.com/en/5.2/howto/static-files/).

    If a file is matched against any of the patterns, it will never be considered a static file,
    even if the file matches a pattern in
    [`static_files_allowed`](./settings.md#django_components_lite.app_settings.ComponentsSettings.static_files_allowed).

    Use this setting together with
    [`static_files_allowed`](./settings.md#django_components_lite.app_settings.ComponentsSettings.static_files_allowed)
    for a fine control over what file types will be exposed.

    You can also pass in compiled regexes ([`re.Pattern`](https://docs.python.org/3/library/re.html#re.Pattern))
    for more advanced patterns.

    By default, any HTML and Python are considered NOT static files:

    ```python
    COMPONENTS = ComponentsSettings(
        static_files_forbidden=[
            ".html", ".django", ".dj", ".tpl",
            # Python files
            ".py", ".pyc",
        ],
    )
    ```

    !!! warning

        Exposing your Python files can be a security vulnerability.
        See [Security notes](../overview/security_notes.md).
    """


# NOTE: Some defaults depend on the Django settings, which may not yet be
# initialized at the time that these settings are generated. For such cases
# we define the defaults as a factory function, and use the `Dynamic` class to
# mark such fields.
@dataclass(frozen=True)
class Dynamic[T]:
    getter: Callable[[], T]


# This is the source of truth for the settings defaults. If the documentation
# does NOT match it, the documentation should be updated.
#
# NOTE: Because we need to access Django settings to generate default dirs
#       for `COMPONENTS.dirs`, we do it lazily.
# NOTE 2: We show the defaults in the documentation, together with the comments
#        (except for the `Dynamic` instances and comments like `type: ignore`).
#        So `fmt: off` turns off Black/Ruff formatting and `snippet:defaults` allows
#        us to extract the snippet from the file.
#
# fmt: off
# --snippet:defaults--
defaults = ComponentsSettings(
    autodiscover=True,
    cache=None,
    # Root-level "components" dirs, e.g. `/path/to/proj/components/`
    dirs=Dynamic(lambda: [Path(settings.BASE_DIR) / "components"]),  # type: ignore[arg-type]
    # App-level "components" dirs, e.g. `[app]/components/`
    app_dirs=["components"],
    multiline_tags=True,
    static_files_allowed=[
        ".css",
        ".js", ".jsx", ".ts", ".tsx",
        # Images
        ".apng", ".png", ".avif", ".gif", ".jpg",
        ".jpeg", ".jfif", ".pjpeg", ".pjp", ".svg",
        ".webp", ".bmp", ".ico", ".cur", ".tif", ".tiff",
        # Fonts
        ".eot", ".ttf", ".woff", ".otf", ".svg",
    ],
    static_files_forbidden=[
        # See https://marketplace.visualstudio.com/items?itemName=junstyle.vscode-django-support
        ".html", ".django", ".dj", ".tpl",
        # Python files
        ".py", ".pyc",
    ],
)
# --endsnippet:defaults--
# fmt: on


# Interface through which we access the settings.
#
# This is the only place where we actually access the settings.
# The settings are merged with defaults, and then validated.
#
# The settings are then available through the `app_settings` object.
#
# Settings are loaded from Django settings only once, at `apps.py` in `ready()`.
class InternalSettings:
    def __init__(self) -> None:
        self._settings: ComponentsSettings | None = None

    def _load_settings(self) -> None:
        data = getattr(settings, "COMPONENTS", {})
        components_settings = ComponentsSettings(**data) if not isinstance(data, ComponentsSettings) else data

        # Merge we defaults and otherwise initialize if necessary

        # For DIRS setting, we use a getter for the default value, because the default value
        # uses Django settings, which may not yet be initialized at the time these settings are generated.
        dirs_default_fn = cast("Dynamic[Sequence[str | tuple[str, str]]]", defaults.dirs)
        dirs_default = dirs_default_fn.getter()

        self._settings = ComponentsSettings(
            autodiscover=default(components_settings.autodiscover, defaults.autodiscover),
            cache=default(components_settings.cache, defaults.cache),
            dirs=default(components_settings.dirs, dirs_default),
            app_dirs=default(components_settings.app_dirs, defaults.app_dirs),
            multiline_tags=default(components_settings.multiline_tags, defaults.multiline_tags),
            static_files_allowed=default(components_settings.static_files_allowed, defaults.static_files_allowed),
            static_files_forbidden=self._prepare_static_files_forbidden(components_settings),
        )

    def _get_settings(self) -> ComponentsSettings:
        if self._settings is None:
            self._load_settings()
        return cast("ComponentsSettings", self._settings)

    def _prepare_static_files_forbidden(self, new_settings: ComponentsSettings) -> list[str | re.Pattern]:
        return default(
            new_settings.static_files_forbidden,
            cast("list[str | re.Pattern]", defaults.static_files_forbidden),
        )

    @property
    def AUTODISCOVER(self) -> bool:
        return self._get_settings().autodiscover  # type: ignore[return-value]

    @property
    def CACHE(self) -> str | None:
        return self._get_settings().cache

    @property
    def DIRS(self) -> Sequence[str | PathLike | tuple[str, str] | tuple[str, PathLike]]:
        return self._get_settings().dirs  # type: ignore[return-value]

    @property
    def APP_DIRS(self) -> Sequence[str]:
        return self._get_settings().app_dirs  # type: ignore[return-value]

    @property
    def MULTILINE_TAGS(self) -> bool:
        return self._get_settings().multiline_tags  # type: ignore[return-value]

    @property
    def STATIC_FILES_ALLOWED(self) -> Sequence[str | re.Pattern]:
        return self._get_settings().static_files_allowed  # type: ignore[return-value]

    @property
    def STATIC_FILES_FORBIDDEN(self) -> Sequence[str | re.Pattern]:
        return self._get_settings().static_files_forbidden  # type: ignore[return-value]


app_settings = InternalSettings()

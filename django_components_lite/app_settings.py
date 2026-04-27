# ruff: noqa: N802
import re
from collections.abc import Sequence
from os import PathLike
from pathlib import Path
from typing import (
    NamedTuple,
    cast,
)

from django.conf import settings

from django_components_lite.util.misc import default


class ComponentsSettings(NamedTuple):
    """Settings available for django_components_lite."""

    autodiscover: bool | None = None
    """Whether to run autodiscovery at Django server startup. Default: `True`."""

    dirs: Sequence[str | PathLike | tuple[str, str] | tuple[str, PathLike]] | None = None
    """Absolute paths to directories that contain components.

    Defaults to `[Path(settings.BASE_DIR) / "components"]`. Set to `[]` to disable.
    """

    app_dirs: Sequence[str] | None = None
    """App-relative directories to search for components. Default: `["components"]`."""

    static_files_allowed: list[str | re.Pattern] | None = None
    """File extensions (or regex patterns) within `dirs`/`app_dirs` to treat as static files.

    Defaults to JS, CSS, common image and font extensions.
    Warning: exposing Python files can be a security vulnerability.
    """

    static_files_forbidden: list[str | re.Pattern] | None = None
    """File extensions (or regex patterns) within `dirs`/`app_dirs` that are NEVER static files.

    Takes precedence over `static_files_allowed`. Defaults to HTML and Python files.
    Warning: exposing Python files can be a security vulnerability.
    """


# `dirs` defaults to `None` here because its real default depends on
# `settings.BASE_DIR`, which is unsafe to read at import time; it's resolved
# lazily in `_load_settings()` below.
# fmt: off
# --snippet:defaults--
defaults = ComponentsSettings(
    autodiscover=True,
    dirs=None,
    app_dirs=["components"],
    static_files_allowed=[
        ".css",
        ".js", ".jsx", ".ts", ".tsx",
        # Images
        ".apng", ".png", ".avif", ".gif", ".jpg",
        ".jpeg", ".jfif", ".pjpeg", ".pjp", ".svg",
        ".webp", ".bmp", ".ico", ".cur", ".tif", ".tiff",
        # Fonts
        ".eot", ".ttf", ".woff", ".otf",
    ],
    static_files_forbidden=[
        # See https://marketplace.visualstudio.com/items?itemName=junstyle.vscode-django-support
        ".html", ".django", ".dj", ".tpl",
        ".py", ".pyc",
    ],
)
# --endsnippet:defaults--
# fmt: on


# Settings are loaded once from Django settings, in `apps.py` `ready()`.
class InternalSettings:
    def __init__(self) -> None:
        self._settings: ComponentsSettings | None = None

    def _load_settings(self) -> None:
        data = getattr(settings, "COMPONENTS", {})
        components_settings = ComponentsSettings(**data) if not isinstance(data, ComponentsSettings) else data

        # `dirs` default depends on `settings.BASE_DIR`, only safe to read at call time.
        dirs_default: Sequence[str | PathLike | tuple[str, str] | tuple[str, PathLike]] = [
            Path(settings.BASE_DIR) / "components",
        ]

        self._settings = ComponentsSettings(
            autodiscover=default(components_settings.autodiscover, defaults.autodiscover),
            dirs=default(components_settings.dirs, dirs_default),
            app_dirs=default(components_settings.app_dirs, defaults.app_dirs),
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
    def DIRS(self) -> Sequence[str | PathLike | tuple[str, str] | tuple[str, PathLike]]:
        return self._get_settings().dirs  # type: ignore[return-value]

    @property
    def APP_DIRS(self) -> Sequence[str]:
        return self._get_settings().app_dirs  # type: ignore[return-value]

    @property
    def STATIC_FILES_ALLOWED(self) -> Sequence[str | re.Pattern]:
        return self._get_settings().static_files_allowed  # type: ignore[return-value]

    @property
    def STATIC_FILES_FORBIDDEN(self) -> Sequence[str | re.Pattern]:
        return self._get_settings().static_files_forbidden  # type: ignore[return-value]


app_settings = InternalSettings()

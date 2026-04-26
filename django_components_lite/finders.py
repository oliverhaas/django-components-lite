import os
import re
from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import Any

from django import VERSION as DJANGO_VERSION
from django.contrib.staticfiles.finders import BaseFinder
from django.contrib.staticfiles.utils import get_files
from django.core import checks
from django.core.files.storage import FileSystemStorage
from django.utils._os import safe_join

from django_components_lite.app_settings import app_settings
from django_components_lite.util.loader import get_component_dirs
from django_components_lite.util.misc import any_regex_match, no_regex_match

# Tracks directories searched by the finder.
searched_locations = []


# Mirrors Django's `FileSystemFinder` but uses `COMPONENTS.dirs` as locations,
# so JS/CSS sitting inside component dirs work with `static()` and `collectstatic`.
class ComponentsFileSystemFinder(BaseFinder):
    """Static files finder using `COMPONENTS.dirs` instead of `STATICFILES_DIRS`.

    Eligibility within those dirs is controlled by
    `COMPONENTS.static_files_allowed` / `static_files_forbidden`.
    """

    def __init__(self, app_names: Any = None, *args: Any, **kwargs: Any) -> None:
        component_dirs = [str(p) for p in get_component_dirs()]

        # Same as `django.contrib.staticfiles.finders.FileSystemFinder.__init__`,
        # but using our locations instead of STATICFILES_DIRS.
        self.locations: list[tuple[str, str]] = []
        self.storages: dict[str, FileSystemStorage] = {}
        for root in component_dirs:
            entry = ("", root)
            if entry not in self.locations:
                self.locations.append(entry)
        for prefix, root in self.locations:
            filesystem_storage = FileSystemStorage(location=root)
            filesystem_storage.prefix = prefix
            self.storages[root] = filesystem_storage

        super().__init__(*args, **kwargs)

    # NOTE: Based on `FileSystemFinder.check`
    def check(self, **_kwargs: Any) -> list[checks.CheckMessage]:
        errors: list[checks.CheckMessage] = []
        if not isinstance(app_settings.DIRS, (list, tuple)):
            errors.append(
                checks.Error(
                    "The COMPONENTS.dirs setting is not a tuple or list.",
                    hint="Perhaps you forgot a trailing comma?",
                    id="components.E001",
                ),
            )
            return errors
        for root in app_settings.DIRS:
            if isinstance(root, (list, tuple)):
                prefix, root = root  # noqa: PLW2901
                if prefix.endswith("/"):
                    errors.append(
                        checks.Error(
                            f"The prefix {prefix!r} in the COMPONENTS.dirs setting must not end with a slash.",
                            id="staticfiles.E003",
                        ),
                    )
            elif not Path(root).is_dir():
                errors.append(
                    checks.Warning(
                        f"The directory '{root}' in the COMPONENTS.dirs setting does not exist.",
                        id="components.W004",
                    ),
                )
        return errors

    # NOTE: Same as `FileSystemFinder.find`
    def find(self, path: str, **kwargs: Any) -> list[str] | str:
        """Look for files in the extra locations as defined in COMPONENTS.dirs."""
        # Django 5.2 deprecated `all` in favour of `find_all` and rejected passing both;
        # Django 6.1 removed `all` entirely.
        # See https://github.com/django/django/blob/5.2/django/contrib/staticfiles/finders.py#L58C9-L58C37
        # And https://github.com/django-components/django-components/issues/1119
        if DJANGO_VERSION < (6, 1):
            find_all = self._check_deprecated_find_param(**kwargs)
        else:
            find_all = kwargs.get("find_all", False)

        matches: list[str] = []
        for prefix, root in self.locations:
            if root not in searched_locations:
                searched_locations.append(root)
            matched_path = self.find_location(root, path, prefix)
            if matched_path:
                if not find_all:
                    return matched_path
                matches.append(matched_path)
        return matches

    # NOTE: Same as `FileSystemFinder.find_local`, but we exclude Python/HTML files
    def find_location(self, root: str, path: str, prefix: str | None = None) -> str | None:
        """Resolve a static file under `root`, returning its absolute path or None."""
        if prefix:
            prefix = f"{prefix}{os.sep}"
            if not path.startswith(prefix):
                return None
            path = path.removeprefix(prefix)
        path = safe_join(root, path)

        if Path(path).exists() and self._is_path_valid(path):
            return path
        return None

    # Called from `collectstatic`. Same as `FileSystemFinder.list`, but we exclude Python/HTML files.
    # See https://github.com/django/django/blob/bc9b6251e0b54c3b5520e3c66578041cc17e4a28/django/contrib/staticfiles/management/commands/collectstatic.py#L126C23-L126C30
    def list(self, ignore_patterns: list[str]) -> Iterable[tuple[str, FileSystemStorage]]:
        """List all files in all locations."""
        for _prefix, root in self.locations:
            if Path(root).is_dir():
                storage = self.storages[root]
                for path in get_files(storage, ignore_patterns):
                    if self._is_path_valid(path):
                        yield path, storage

    def _is_path_valid(self, path: str) -> bool:
        allowed = _compile_patterns(tuple(app_settings.STATIC_FILES_ALLOWED))
        forbidden = _compile_patterns(tuple(app_settings.STATIC_FILES_FORBIDDEN))
        return any_regex_match(path, allowed) and no_regex_match(path, forbidden)


# Cached: settings tuples are stable, and `collectstatic` calls this thousands of times.
@cache
def _compile_patterns(patterns: tuple[str | re.Pattern, ...]) -> list[re.Pattern]:
    return [re.compile(rf"\{p}$") if isinstance(p, str) else p for p in patterns]

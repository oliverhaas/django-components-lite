import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import NamedTuple

from django.apps import apps
from django.conf import settings

from django_components_lite.app_settings import app_settings
from django_components_lite.util.logger import logger


def get_component_dirs(include_apps: bool = True) -> list[Path]:
    """Return all directories that may contain component files.

    Combines `COMPONENTS.dirs` with `<app>/<COMPONENTS.app_dirs>` for each installed app.
    `COMPONENTS.dirs` entries must be absolute paths; `BASE_DIR` is required.
    """
    component_dirs = app_settings.DIRS

    logger.debug(
        "get_component_dirs will search for valid dirs from following options:\n"
        + "\n".join([f" - {d!s}" for d in component_dirs]),
    )

    app_paths: list[Path] = []
    if include_apps:
        for conf in apps.get_app_configs():
            for app_dir in app_settings.APP_DIRS:
                comps_path = Path(conf.path).joinpath(app_dir)
                if comps_path.exists():
                    app_paths.append(comps_path)

    directories: set[Path] = set(app_paths)

    for component_dir in component_dirs:
        # Accept `(prefix, path)` tuples for STATICFILES_DIRS compatibility (#489).
        # See https://docs.djangoproject.com/en/5.2/ref/settings/#prefixes-optional
        if isinstance(component_dir, (tuple, list)):
            component_dir = component_dir[1]  # noqa: PLW2901
        try:
            Path(component_dir)
        except TypeError:
            logger.warning(
                f"COMPONENTS.dirs expected str, bytes or os.PathLike object, or tuple/list of length 2. "
                f"See Django documentation for STATICFILES_DIRS. Got {type(component_dir)} : {component_dir}",
            )
            continue

        if not Path(component_dir).is_absolute():
            raise ValueError(f"COMPONENTS.dirs must contain absolute paths, got '{component_dir}'")
        directories.add(Path(component_dir).resolve())

    logger.debug(
        "get_component_dirs matched following template dirs:\n" + "\n".join([f" - {d!s}" for d in directories]),
    )
    return list(directories)


class ComponentFileEntry(NamedTuple):
    """A component file with both its filesystem path and python dot path."""

    dot_path: str
    """Python import path, e.g. `app.components.mycomp`."""
    filepath: Path
    """Filesystem path, e.g. `/path/to/project/app/components/mycomp.py`."""


def get_component_files(suffix: str | None = None) -> list[ComponentFileEntry]:
    """Find files under `get_component_dirs()`, optionally filtered by suffix (e.g. `.py`).

    Files and subdirectories starting with `_` are skipped (except `__init__.py`).
    """
    search_glob = f"**/*{suffix}" if suffix else "**/*"

    dirs = get_component_dirs(include_apps=False)
    component_filepaths = _search_dirs(dirs, search_glob)

    project_root = settings.BASE_DIR if hasattr(settings, "BASE_DIR") and settings.BASE_DIR else Path.cwd()

    modules: list[ComponentFileEntry] = []

    # `COMPONENTS.dirs` are assumed to live under `BASE_DIR` (== CWD), so the
    # path relative to `BASE_DIR` doubles as the python import path.
    for filepath in component_filepaths:
        module_path = _filepath_to_python_module(filepath, project_root, None)
        # `..` in the dot path means a dot-prefixed segment (e.g. `./abc/.def` -> `abc..def`)
        # or a file outside the parent — none of which are valid python modules.
        if ".." in module_path:
            continue

        entry = ComponentFileEntry(dot_path=module_path, filepath=filepath)
        modules.append(entry)

    # App dirs may live outside the project (e.g. third-party apps), so resolve
    # the import path relative to the app's own root module name.
    # See https://github.com/django-components/django-components/issues/669
    for conf in apps.get_app_configs():
        for app_dir in app_settings.APP_DIRS:
            comps_path = Path(conf.path).joinpath(app_dir)
            if not comps_path.exists():
                continue
            app_component_filepaths = _search_dirs([comps_path], search_glob)
            for filepath in app_component_filepaths:
                app_component_module = _filepath_to_python_module(filepath, conf.path, conf.name)
                entry = ComponentFileEntry(dot_path=app_component_module, filepath=filepath)
                modules.append(entry)

    return modules


def _filepath_to_python_module(
    file_path: Path | str,
    root_fs_path: str | Path,
    root_module_path: str | None,
) -> str:
    """Convert a filesystem path under `root_fs_path` into a python dot path."""
    path_cls = PureWindowsPath if os.name == "nt" else PurePosixPath

    rel_path = path_cls(file_path).relative_to(path_cls(root_fs_path))
    rel_path_parts = rel_path.with_suffix("").parts
    module_name = ".".join(rel_path_parts)

    full_module_name = f"{root_module_path}.{module_name}" if root_module_path else module_name
    return full_module_name.removesuffix(".__init__")


def _search_dirs(dirs: list[Path], search_glob: str) -> list[Path]:
    """Glob each directory and return a flat list of matches, skipping `_`-prefixed paths."""
    matched_files: list[Path] = []
    for directory in dirs:
        for path in Path(directory).rglob(search_glob):
            rel_dir_parts = list(path.relative_to(directory).parts)
            name_part = rel_dir_parts.pop()
            if any(part.startswith("_") for part in rel_dir_parts):
                continue
            if name_part.startswith("_") and name_part != "__init__.py":
                continue

            matched_files.append(path)

    return matched_files

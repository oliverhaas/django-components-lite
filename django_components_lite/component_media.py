"""Resolves component-relative media file paths into paths relative to `COMPONENTS.dirs`."""

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from django_components_lite.util.loader import get_component_dirs
from django_components_lite.util.misc import get_module_info

if TYPE_CHECKING:
    from django_components_lite.component import Component


def resolve_component_files(comp_cls: type["Component"]) -> None:
    """Rewrite `template_file`/`js_file`/`css_file` from component-relative to dir-relative paths.

    E.g. for `components/calendar/calendar.py` with `js_file = "calendar.js"`,
    this sets `js_file = "calendar/calendar.js"`.
    """
    comp_dirs = get_component_dirs()

    _module, _module_name, module_file_path = get_module_info(comp_cls)
    if not module_file_path:
        return

    matched_component_dir = _find_component_dir(comp_dirs, module_file_path)
    if matched_component_dir is None:
        return

    comp_dir_abs = Path(matched_component_dir).resolve()
    comp_file_dir = Path(module_file_path).parent

    for attr in ("template_file", "js_file", "css_file"):
        filepath = getattr(comp_cls, attr, None)
        if not filepath or not isinstance(filepath, str):
            continue

        # Skip URLs and absolute paths (incl. protocol-relative `//cdn/...`).
        if filepath.startswith(("http://", "https://", "//", "/")):
            continue

        abs_path = comp_file_dir / filepath
        if abs_path.exists():
            rel_path = abs_path.resolve().relative_to(comp_dir_abs).as_posix()
            setattr(comp_cls, attr, rel_path)


def _find_component_dir(
    component_dirs: Sequence[str | Path],
    target_file_path: str,
) -> str | Path | None:
    """Return the `COMPONENTS.dirs` entry that contains `target_file_path`, or None."""
    abs_target = Path(target_file_path).resolve()
    for component_dir in component_dirs:
        if abs_target.is_relative_to(Path(component_dir).resolve()):
            return component_dir
    return None

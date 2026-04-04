"""
Minimal component media handling.

Resolves component-relative file paths (template_file, js_file, css_file)
into paths relative to COMPONENTS.dirs, suitable for Django's static files
and template loading.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from django_components_lite.util.loader import get_component_dirs
from django_components_lite.util.misc import get_module_info

if TYPE_CHECKING:
    from django_components_lite.component import Component


def resolve_component_files(comp_cls: type["Component"]) -> None:
    """
    Resolve template_file, js_file, and css_file paths relative to the component's
    source file location. Stores resolved paths back on the class.

    E.g. if a component at `components/calendar/calendar.py` declares
    `js_file = "calendar.js"`, this resolves it to `calendar/calendar.js`
    (relative to the COMPONENTS.dirs root).
    """
    comp_dirs = get_component_dirs()

    # Find which COMPONENTS.dirs directory contains this component
    _module, _module_name, module_file_path = get_module_info(comp_cls)
    if not module_file_path:
        return

    matched_component_dir = _find_component_dir(comp_dirs, module_file_path)
    if matched_component_dir is None:
        return

    comp_dir_abs = Path(matched_component_dir).resolve()
    comp_file_dir = Path(module_file_path).parent

    # Resolve each file attribute
    for attr in ("template_file", "js_file", "css_file"):
        filepath = getattr(comp_cls, attr, None)
        if not filepath or not isinstance(filepath, str):
            continue

        # Skip URLs
        if filepath.startswith(("http://", "https://", "://", "/")):
            continue

        # Check if the file exists relative to the component's directory
        abs_path = comp_file_dir / filepath
        if abs_path.exists():
            # Convert to path relative to the component root dir
            rel_path = abs_path.resolve().relative_to(comp_dir_abs).as_posix()
            setattr(comp_cls, attr, rel_path)


def _find_component_dir(
    component_dirs: Sequence[str | Path],
    target_file_path: str,
) -> str | Path | None:
    """Find which COMPONENTS.dirs directory contains the given file."""
    abs_target = Path(target_file_path).resolve()
    for component_dir in component_dirs:
        if abs_target.is_relative_to(Path(component_dir).resolve()):
            return component_dir
    return None

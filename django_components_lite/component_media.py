"""Resolves component-relative media file paths into paths relative to `COMPONENTS.dirs`."""

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from django_components_lite.util.loader import get_component_dirs
from django_components_lite.util.misc import get_module_info

if TYPE_CHECKING:
    from django_components_lite.component import Component


def resolve_component_files(comp_cls: type[Component]) -> None:
    """Rewrite `template_name` and `Media.css`/`Media.js` from component-relative to dir-relative paths.

    E.g. for `components/calendar/calendar.py` with `class Media: js = ["calendar.js"]`,
    this sets `Media.js = ["calendar/calendar.js"]`.
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

    template_name = getattr(comp_cls, "template_name", None)
    if isinstance(template_name, str):
        resolved = _resolve_one(template_name, comp_dir_abs, comp_file_dir)
        if resolved is not None:
            comp_cls.template_name = resolved

    media = comp_cls.__dict__.get("Media")
    if media is not None:
        for attr in ("css", "js"):
            files = getattr(media, attr, None)
            if not files:
                continue
            new_files = [_resolve_one(f, comp_dir_abs, comp_file_dir) or f for f in files]
            setattr(media, attr, new_files)


def _resolve_one(filepath: str, comp_dir_abs: Path, comp_file_dir: Path) -> str | None:
    """Return a dir-relative path for `filepath`, or None to keep the original value."""
    if not isinstance(filepath, str):
        return None
    # Skip URLs and absolute paths (incl. protocol-relative `//cdn/...`).
    if filepath.startswith(("http://", "https://", "//", "/")):
        return None
    abs_path = comp_file_dir / filepath
    if abs_path.exists():
        return abs_path.resolve().relative_to(comp_dir_abs).as_posix()
    return None


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

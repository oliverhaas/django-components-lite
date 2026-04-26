import importlib
from collections.abc import Callable

from django_components_lite.util.loader import get_component_files
from django_components_lite.util.logger import logger


def autodiscover(
    map_module: Callable[[str], str] | None = None,
) -> list[str]:
    """Import every `.py` file under `COMPONENTS.dirs` and per-app components dirs.

    Files/dirs starting with `_` are skipped (except `__init__.py`). `map_module`
    can rewrite the resolved module paths (mainly an escape hatch for tests).
    """
    modules = get_component_files(".py")
    logger.debug(f"Autodiscover found {len(modules)} files in component directories.")
    return _import_modules([entry.dot_path for entry in modules], map_module)


def _import_modules(
    modules: list[str],
    map_module: Callable[[str], str] | None = None,
) -> list[str]:
    imported_modules: list[str] = []
    for module_name in modules:
        if map_module:
            module_name = map_module(module_name)  # noqa: PLW2901

        logger.debug(f'Importing module "{module_name}"')
        importlib.import_module(module_name)
        imported_modules.append(module_name)

    return imported_modules

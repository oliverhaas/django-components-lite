import importlib
from collections.abc import Callable

from django_components_lite.util.loader import get_component_files
from django_components_lite.util.logger import logger


def autodiscover(
    map_module: Callable[[str], str] | None = None,
) -> list[str]:
    """
    Search for all python files in
    [`COMPONENTS.dirs`](../settings#django_components_lite.app_settings.ComponentsSettings.dirs)
    and
    [`COMPONENTS.app_dirs`](../settings#django_components_lite.app_settings.ComponentsSettings.app_dirs)
    and import them.

    NOTE: Subdirectories and files starting with an underscore `_` (except for `__init__.py`) are ignored.

    Args:
        map_module (Callable[[str], str], optional): Map the module paths with `map_module` function.
        This serves as an escape hatch for when you need to use this function in tests.

    Returns:
        List[str]: A list of module paths of imported files.
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

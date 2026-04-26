import re
import sys
from collections.abc import Callable
from hashlib import md5
from importlib import import_module
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    cast,
)

if TYPE_CHECKING:
    from django_components_lite.component import Component

T = TypeVar("T")
U = TypeVar("U")


def is_str_wrapped_in_quotes(s: str) -> bool:
    return s.startswith(('"', "'")) and s[0] == s[-1] and len(s) >= 2


def is_identifier(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return value.isidentifier()


def any_regex_match(string: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(string) is not None for p in patterns)


def no_regex_match(string: str, patterns: list[re.Pattern]) -> bool:
    return all(p.search(string) is None for p in patterns)


# See https://stackoverflow.com/a/2020083/9788634
def get_import_path(cls_or_fn: type[Any]) -> str:
    """Full import path for a class or function, e.g. `"path.to.MyClass"`."""
    module = cls_or_fn.__module__
    if module == "builtins":
        return cls_or_fn.__qualname__  # avoid outputs like 'builtins.str'
    return module + "." + cls_or_fn.__qualname__


def get_module_info(
    cls_or_fn: type[Any] | Callable[..., Any],
) -> tuple[ModuleType | None, str | None, str | None]:
    """Return `(module, module_name, file_path)` for where the class/function is defined."""
    module_name: str | None = getattr(cls_or_fn, "__module__", None)

    if module_name:
        if module_name in sys.modules:
            module = sys.modules[module_name]
        else:
            try:
                module = import_module(module_name)
            except (ImportError, AttributeError):
                module = None
    else:
        module = None

    if module:
        module_file_path: str | None = getattr(module, "__file__", None)
    else:
        module_file_path = None

    return module, module_name, module_file_path


def default[T, U](val: T | None, default: U | Callable[[], U] | type[T], factory: bool = False) -> T | U:
    if val is not None:
        return val
    if factory:
        default_func = cast("Callable[[], U]", default)
        return default_func()
    return cast("U", default)


def get_last_index(lst: list, key: Callable[[Any], bool]) -> int | None:
    """Index of the last item in `lst` for which `key(item)` is true, or None."""
    for index, item in enumerate(reversed(lst)):
        if key(item):
            return len(lst) - 1 - index
    return None


# Produce a stable per-class identifier like `TableComp_a91d03`.
def hash_comp_cls(comp_cls: type["Component"]) -> str:
    full_name = get_import_path(comp_cls)
    name_hash = md5(full_name.encode()).hexdigest()[0:6]  # noqa: S324
    return comp_cls.__name__ + "_" + name_hash

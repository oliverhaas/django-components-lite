import re
import sys
from collections import namedtuple
from collections.abc import Callable, Iterable
from dataclasses import asdict, is_dataclass
from hashlib import md5
from importlib import import_module
from inspect import getmembers
from itertools import chain
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    cast,
)
from urllib import parse

if TYPE_CHECKING:
    from django_components_lite.component import Component

T = TypeVar("T")
U = TypeVar("U")


def is_str_wrapped_in_quotes(s: str) -> bool:
    return s.startswith(('"', "'")) and s[0] == s[-1] and len(s) >= 2


def snake_to_pascal(name: str) -> str:
    return "".join(word.title() for word in name.split("_"))


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
    """Get the full import path for a class or a function, e.g. `"path.to.MyClass"`"""
    module = cls_or_fn.__module__
    if module == "builtins":
        return cls_or_fn.__qualname__  # avoid outputs like 'builtins.str'
    return module + "." + cls_or_fn.__qualname__


def get_module_info(
    cls_or_fn: type[Any] | Callable[..., Any],
) -> tuple[ModuleType | None, str | None, str | None]:
    """Get the module, module name and module file path where the class or function is defined."""
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


def get_index(lst: list, key: Callable[[Any], bool]) -> int | None:
    """Get the index of the first item in the list that satisfies the key"""
    for i in range(len(lst)):
        if key(lst[i]):
            return i
    return None


def get_last_index(lst: list, key: Callable[[Any], bool]) -> int | None:
    """Get the index of the last item in the list that satisfies the key"""
    for index, item in enumerate(reversed(lst)):
        if key(item):
            return len(lst) - 1 - index
    return None


def is_nonempty_str(txt: str | None) -> bool:
    return txt is not None and bool(txt.strip())


# Convert Component class to something like `TableComp_a91d03`
def hash_comp_cls(comp_cls: type["Component"]) -> str:
    full_name = get_import_path(comp_cls)
    name_hash = md5(full_name.encode()).hexdigest()[0:6]  # noqa: S324
    return comp_cls.__name__ + "_" + name_hash


# String is a glob if it contains at least one of `?`, `*`, or `[`
is_glob_re = re.compile(r"[?*[]")


def is_glob(filepath: str) -> bool:
    return is_glob_re.search(filepath) is not None


def flatten[T](lst: Iterable[Iterable[T]]) -> list[T]:
    return list(chain.from_iterable(lst))


def to_dict(data: Any) -> dict:
    """
    Convert object to a dict.

    Handles `dict`, `NamedTuple`, and `dataclass`.
    """
    if isinstance(data, dict):
        return data
    if hasattr(data, "_asdict"):  # Case: NamedTuple
        return data._asdict()
    if is_dataclass(data):  # Case: dataclass
        return asdict(data)  # type: ignore[arg-type]

    return dict(data)


def format_url(url: str, query: dict | None = None, fragment: str | None = None) -> str:
    """
    Given a URL, add to it query parameters and a fragment, returning an updated URL.

    ```py
    url = format_url(url="https://example.com", query={"foo": "bar"}, fragment="baz")
    # https://example.com?foo=bar#baz
    ```

    `query` and `fragment` are optional, and not applied if `None`.

    Boolean `True` values in query parameters are rendered as flag parameters without values.

    `False` and `None` values in query parameters are omitted.

    ```py
    url = format_url(
        url="https://example.com",
        query={"foo": "bar", "baz": None, "enabled": True, "debug": False},
    )
    # https://example.com?foo=bar&enabled
    ```
    """
    parts = parse.urlsplit(url)
    fragment_enc = parse.quote(fragment or parts.fragment, safe="")
    base_qs = dict(parse.parse_qsl(parts.query))
    # Filter out `None` and `False` values
    filtered_query = {k: v for k, v in (query or {}).items() if v is not None and v is not False}
    merged = {**base_qs, **filtered_query}

    # Handle boolean True values as flag parameters (no explicit value)
    query_parts = []
    for key, value in merged.items():
        if value is True:
            query_parts.append(parse.quote_plus(str(key)))
        else:
            query_parts.append(f"{parse.quote_plus(str(key))}={parse.quote_plus(str(value))}")

    encoded_qs = "&".join(query_parts)

    return parse.urlunsplit(parts._replace(query=encoded_qs, fragment=fragment_enc))


def format_as_ascii_table(
    data: list[dict[str, Any]],
    headers: list[str] | tuple[str, ...] | set[str],
    include_headers: bool = True,
) -> str:
    """
    Format a list of dictionaries as an ASCII table.

    Example:

    ```python
    data = [
        {"name": "ProjectPage", "full_name": "project.pages.project.ProjectPage", "path": "./project/pages/project"},
        {"name": "ProjectDashboard", "full_name": "project.components.dashboard.ProjectDashboard", "path": "./project/components/dashboard"},
        {"name": "ProjectDashboardAction", "full_name": "project.components.dashboard_action.ProjectDashboardAction", "path": "./project/components/dashboard_action"},
    ]
    headers = ["name", "full_name", "path"]
    print(format_as_ascii_table(data, headers))
    ```

    Which prints:

    ```txt
    name                      full_name                                                     path
    ==================================================================================================
    ProjectPage               project.pages.project.ProjectPage                             ./project/pages/project
    ProjectDashboard          project.components.dashboard.ProjectDashboard                 ./project/components/dashboard
    ProjectDashboardAction    project.components.dashboard_action.ProjectDashboardAction    ./project/components/dashboard_action
    ```

    """
    # Calculate the width of each column
    column_widths = {header: len(header) for header in headers}
    for row in data:
        for header in headers:
            row_value = str(row.get(header, ""))
            column_widths[header] = max(column_widths[header], len(row_value))

    # Create the header row
    header_row = "  ".join(f"{header:<{column_widths[header]}}" for header in headers)
    separator = "=" * len(header_row)

    # Create the data rows
    data_rows = []
    for row in data:
        row_values = [str(row.get(header, "")) for header in headers]
        data_row = "  ".join(
            f"{value:<{column_widths[header]}}" for value, header in zip(row_values, headers, strict=False)
        )
        data_rows.append(data_row)

    # Combine all parts into the final table
    return "\n".join([header_row, separator, *data_rows]) if include_headers else "\n".join(data_rows)


def is_generator(obj: Any) -> bool:
    """Check if an object is a generator with send method."""
    return hasattr(obj, "send")


def convert_class_to_namedtuple(cls: type[Any]) -> type[tuple[Any, ...]]:
    # Construct fields for a NamedTuple. Unfortunately one can't further subclass the subclass of `NamedTuple`,
    # so we need to construct a new class with the same fields.
    # NamedTuple has:
    # - Required fields, which are defined without values (annotations only)
    # - Optional fields with defaults
    # ```py
    # class Z:
    #     b: str          # Required, annotated
    #     a: int = None   # Optional, annotated
    #     c = 1           # NOT A FIELD! Class var!
    # ```
    # Annotations are stored in `X.__annotations__`, while the defaults are regular class attributes
    # NOTE: We ignore dunder methods
    # NOTE 2: All fields with default values must come after fields without defaults.
    field_names = list(cls.__annotations__.keys())

    # Get default values from the original class and set them on the new NamedTuple class
    field_names_set = set(field_names)
    defaults = {}
    class_attrs = {}
    for name, value in getmembers(cls):
        if name.startswith("__"):
            continue
        # Field default
        if name in field_names_set:
            defaults[name] = value
        else:
            # Class attribute
            class_attrs[name] = value

    # Figure out how many tuple fields have defaults. We need to know this
    # because NamedTuple functional syntax uses the pattern where defaults
    # are applied from the end.
    # Final call then looks like this:
    # `namedtuple("MyClass", ["a", "b", "c", "d"], defaults=[3, 4])`
    # with defaults c=3 and d=4
    num_fields_with_defaults = len(defaults)
    if num_fields_with_defaults:
        defaults_list = [defaults[name] for name in field_names[-num_fields_with_defaults:]]
    else:
        defaults_list = []
    tuple_cls = namedtuple(cls.__name__, field_names, defaults=defaults_list)  # type: ignore[misc]  # noqa: PYI024

    # `collections.namedtuple` doesn't allow to specify annotations, so we pass them afterwards
    tuple_cls.__annotations__ = cls.__annotations__
    # Likewise, `collections.namedtuple` doesn't allow to specify class vars
    for name, value in class_attrs.items():
        setattr(tuple_cls, name, value)

    return tuple_cls

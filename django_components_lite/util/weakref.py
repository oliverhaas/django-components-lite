from typing import Any, TypeVar, overload
from weakref import ReferenceType, finalize, ref

GLOBAL_REFS: dict[int, ReferenceType] = {}


T = TypeVar("T")


@overload  # type: ignore[misc]
def cached_ref[T](obj: T) -> ReferenceType[T]: ...


def cached_ref(obj: Any) -> ReferenceType:
    """Like `weakref.ref()`, but returns the same `ref` instance per object."""
    obj_id = id(obj)
    if obj_id not in GLOBAL_REFS:
        GLOBAL_REFS[obj_id] = ref(obj)

    finalize(obj, lambda: GLOBAL_REFS.pop(obj_id, None))

    return GLOBAL_REFS[obj_id]

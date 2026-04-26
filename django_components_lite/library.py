"""Helpers for interacting with Django's template `Library`."""

from collections.abc import Callable

from django.template.base import Node, Parser, Token
from django.template.library import Library


class TagProtectedError(Exception):
    """Raised when registering a tag whose name is reserved (e.g. `slot`, `fill`, `html_attrs`)."""


PROTECTED_TAGS = ["fill", "html_attrs", "slot"]
"""Tag names users cannot reuse for their own components."""


def register_tag(
    library: Library,
    tag: str,
    tag_fn: Callable[[Parser, Token], Node],
) -> None:
    if is_tag_protected(library, tag):
        raise TagProtectedError(f'Cannot register tag "{tag}", this tag name is protected')
    library.tag(tag, tag_fn)


def mark_protected_tags(lib: Library, tags: list[str] | None = None) -> None:
    """Mark `tags` (or `PROTECTED_TAGS` by default) as reserved on `lib`."""
    protected_tags = tags if tags is not None else PROTECTED_TAGS
    lib._protected_tags = [*protected_tags]


def is_tag_protected(lib: Library, tag: str) -> bool:
    """Return True if `tag` is marked protected on `lib`."""
    protected_tags = getattr(lib, "_protected_tags", [])
    return tag in protected_tags

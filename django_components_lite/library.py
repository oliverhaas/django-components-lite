"""Module for interfacing with Django's Library (`django.template.library`)"""

from collections.abc import Callable

from django.template.base import Node, Parser, Token
from django.template.library import Library


class TagProtectedError(Exception):
    """
    Raised when a component is registered under a name that would overwrite
    one of django_components_lite's own template tags (e.g. `slot`, `fill`).
    """


PROTECTED_TAGS = ["fill", "html_attrs", "slot"]
"""
These are the names that users cannot choose for their components,
as they would conflict with other tags in the Library.
"""


def register_tag(
    library: Library,
    tag: str,
    tag_fn: Callable[[Parser, Token], Node],
) -> None:
    # Register inline tag
    if is_tag_protected(library, tag):
        raise TagProtectedError(f'Cannot register tag "{tag}", this tag name is protected')
    library.tag(tag, tag_fn)


def mark_protected_tags(lib: Library, tags: list[str] | None = None) -> None:
    protected_tags = tags if tags is not None else PROTECTED_TAGS
    lib._protected_tags = [*protected_tags]


def is_tag_protected(lib: Library, tag: str) -> bool:
    protected_tags = getattr(lib, "_protected_tags", [])
    return tag in protected_tags

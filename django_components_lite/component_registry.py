from collections.abc import Callable
from typing import TYPE_CHECKING, NamedTuple, TypeVar
from weakref import ReferenceType

from django.template import Library, TemplateSyntaxError
from django.template.base import Parser, Token

from django_components_lite.library import is_tag_protected, mark_protected_tags, register_tag
from django_components_lite.util.misc import is_str_wrapped_in_quotes
from django_components_lite.util.weakref import cached_ref

if TYPE_CHECKING:
    from django_components_lite.component import Component


AllRegistries = list[ReferenceType["ComponentRegistry"]]


TComponent = TypeVar("TComponent", bound="Component")


class AlreadyRegisteredError(Exception):
    """Raised when registering a component name that is already taken in the registry."""


class NotRegisteredError(Exception):
    """Raised when accessing a component name that is not registered."""


# Tags are tracked per-entry so we can remove them from the Library on unregister.
class ComponentRegistryEntry(NamedTuple):
    cls: type["Component"]
    tags: tuple[str, ...]


# Track all registries so component names can be resolved across them.
ALL_REGISTRIES: AllRegistries = []


def all_registries() -> list["ComponentRegistry"]:
    """Return all live `ComponentRegistry` instances."""
    registries: list[ComponentRegistry] = []
    for reg_ref in ALL_REGISTRIES:
        reg = reg_ref()
        if reg is not None:
            registries.append(reg)
    return registries


class ComponentRegistry:
    """Maps component names to component classes and exposes them as `{% comp %}` tags."""

    def __init__(self, library: Library | None = None) -> None:
        self._registry: dict[str, ComponentRegistryEntry] = {}  # component name -> component_entry mapping
        self._tags: dict[str, set[str]] = {}  # tag -> list[component names]
        self._library = library

        ALL_REGISTRIES.append(cached_ref(self))

    def __copy__(self) -> "ComponentRegistry":
        new_registry = ComponentRegistry(self.library)
        new_registry._registry = self._registry.copy()
        new_registry._tags = self._tags.copy()
        return new_registry

    @property
    def library(self) -> Library:
        """The Django template tag `Library` associated with this registry."""
        # Lazily use the default library if none was passed
        if self._library is not None:
            lib = self._library
        else:
            from django_components_lite.templatetags.component_tags import register as tag_library

            # Protect built-in tags on the default library only; user-supplied
            # libraries are left untouched so they can call `mark_protected_tags`
            # themselves if needed.
            mark_protected_tags(tag_library)
            lib = self._library = tag_library
        return lib

    def register(self, name: str, component: type["Component"]) -> None:
        """Register `component` under `name`; raises `AlreadyRegisteredError` on conflict."""
        existing_component = self._registry.get(name)
        if existing_component and existing_component.cls.class_id != component.class_id:
            raise AlreadyRegisteredError(f'The component "{name}" has already been registered')

        entry = self._register_to_library(name, component)

        # Track which components use which tags (multiple components share `comp`/`compc`).
        for tag in entry.tags:
            if tag not in self._tags:
                self._tags[tag] = set()
            self._tags[tag].add(name)

        self._registry[name] = entry

    def unregister(self, name: str) -> None:
        """Unregister the component registered under `name`; raises `NotRegisteredError` if missing."""
        # Validate
        self.get(name)

        entry = self._registry[name]

        # Remove the tag from the library only if no other component still uses it.
        for tag in entry.tags:
            if tag in self._tags and name in self._tags[tag]:
                self._tags[tag].remove(name)
                if not self._tags[tag]:
                    self._tags.pop(tag, None)
                    is_tag_empty = True
                else:
                    is_tag_empty = False
            else:
                is_tag_empty = True

            if is_tag_empty and not is_tag_protected(self.library, tag) and tag in self.library.tags:
                self.library.tags.pop(tag, None)

        del self._registry[name]

    def get(self, name: str) -> type["Component"]:
        """Return the component class registered under `name`; raises `NotRegisteredError` if missing."""
        if name not in self._registry:
            raise NotRegisteredError(f'The component "{name}" is not registered')

        return self._registry[name].cls

    def has(self, name: str) -> bool:
        """Return True if a component is registered under `name`."""
        return name in self._registry

    def all(self) -> dict[str, type["Component"]]:
        """Return a `{name: component_class}` dict of all registered components."""
        return {key: entry.cls for key, entry in self._registry.items()}

    def clear(self) -> None:
        """Unregister all components."""
        all_comp_names = list(self._registry.keys())
        for comp_name in all_comp_names:
            self.unregister(comp_name)

        self._registry = {}
        self._tags = {}

    def _register_to_library(
        self,
        comp_name: str,
        component: type["Component"],
    ) -> ComponentRegistryEntry:
        # Lazily import to avoid circular dependencies
        from django_components_lite.component import ComponentNode

        registry = self

        # Build a tag function that strips the component name token before delegating.
        def _make_tag_fn(start_tag: str, end_tag: str | None) -> Callable[[Parser, Token], ComponentNode]:
            def tag_fn(parser: Parser, token: Token) -> ComponentNode:
                bits = token.split_contents()
                _tag, *args = bits

                if not args:
                    raise TemplateSyntaxError("Component tag did not receive a component name")

                comp_name_token = None if "=" in args[0] else args.pop(0)
                if not comp_name_token:
                    raise TemplateSyntaxError("Component name must be a non-empty quoted string, e.g. 'my_comp'")
                if not is_str_wrapped_in_quotes(comp_name_token):
                    raise TemplateSyntaxError(f"Component name must be a string 'literal', got: {comp_name_token}")

                parsed_name = comp_name_token[1:-1]

                # Reconstruct token contents without the component name
                token.contents = " ".join([bits[0], *args])

                return ComponentNode.parse(
                    parser,
                    token,
                    registry=registry,
                    name=parsed_name,
                    start_tag=start_tag,
                    end_tag=end_tag,
                )

            return tag_fn

        register_tag(self.library, "comp", _make_tag_fn("comp", "endcomp"))
        register_tag(self.library, "compc", _make_tag_fn("compc", None))

        return ComponentRegistryEntry(cls=component, tags=("comp", "compc"))


registry: ComponentRegistry = ComponentRegistry()
"""The default global `ComponentRegistry`."""

# NOTE: Aliased so that the arg to `@register` can also be called `registry`
_the_registry = registry


def register(
    name: str,
    registry: ComponentRegistry | None = None,
) -> Callable[
    [type[TComponent]],
    type[TComponent],
]:
    """Class decorator that registers a `Component` under `name` (default registry unless given)."""
    if registry is None:
        registry = _the_registry

    def decorator(component: type[TComponent]) -> type[TComponent]:
        registry.register(name=name, component=component)
        return component

    return decorator

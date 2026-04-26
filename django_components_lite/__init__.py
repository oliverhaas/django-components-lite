"""django-components-lite public API."""

# isort: off
from django_components_lite.app_settings import ComponentsSettings
from django_components_lite.attributes import format_attributes, merge_attributes
from django_components_lite.autodiscovery import autodiscover
from django_components_lite.component import (
    Component,
    ComponentNode,
    all_components,
    get_component_by_class_id,
)
from django_components_lite.component_registry import (
    AlreadyRegisteredError,
    ComponentRegistry,
    NotRegisteredError,
    register,
    registry,
    all_registries,
)

from django_components_lite.library import TagProtectedError
from django_components_lite.slots import (
    FillNode,
    Slot,
    SlotContext,
    SlotFallback,
    SlotFunc,
    SlotInput,
    SlotNode,
    SlotResult,
)
from django_components_lite.util.loader import ComponentFileEntry, get_component_dirs, get_component_files
from django_components_lite.util.types import Empty

# isort: on


__all__ = [
    "AlreadyRegisteredError",
    "Component",
    "ComponentFileEntry",
    "ComponentNode",
    "ComponentRegistry",
    "ComponentsSettings",
    "Empty",
    "FillNode",
    "NotRegisteredError",
    "Slot",
    "SlotContext",
    "SlotFallback",
    "SlotFunc",
    "SlotInput",
    "SlotNode",
    "SlotResult",
    "TagProtectedError",
    "all_components",
    "all_registries",
    "autodiscover",
    "format_attributes",
    "get_component_by_class_id",
    "get_component_dirs",
    "get_component_files",
    "merge_attributes",
    "register",
    "registry",
]

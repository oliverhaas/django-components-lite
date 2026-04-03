"""Main package for Django Components."""

# Public API
# isort: off
from django_components.app_settings import ContextBehavior, ComponentsSettings
from django_components.attributes import format_attributes, merge_attributes
from django_components.autodiscovery import autodiscover, import_libraries
from django_components.component import (
    Component,
    ComponentInput,
    ComponentNode,
    ComponentVars,
    OnRenderGenerator,
    all_components,
    get_component_by_class_id,
)
from django_components.component_registry import (
    AlreadyRegistered,
    ComponentRegistry,
    NotRegistered,
    RegistrySettings,
    register,
    registry,
    all_registries,
)
from django_components.dependencies import DependenciesStrategy, render_dependencies
from django_components.library import TagProtectedError
from django_components.node import BaseNode, template_tag
from django_components.slots import (
    FillNode,
    Slot,
    SlotContent,
    SlotContext,
    SlotFallback,
    SlotFunc,
    SlotInput,
    SlotNode,
    SlotRef,
    SlotResult,
)
from django_components.template import cached_template
import django_components.types as types  # noqa: PLR0402
from django_components.util.loader import ComponentFileEntry, get_component_dirs, get_component_files
from django_components.util.types import Empty

# isort: on


__all__ = [
    "AlreadyRegistered",
    "BaseNode",
    "Component",
    "ComponentFileEntry",
    "ComponentInput",
    "ComponentNode",
    "ComponentRegistry",
    "ComponentVars",
    "ComponentsSettings",
    "ContextBehavior",
    "DependenciesStrategy",
    "Empty",
    "FillNode",
    "NotRegistered",
    "OnRenderGenerator",
    "RegistrySettings",
    "Slot",
    "SlotContent",
    "SlotContext",
    "SlotFallback",
    "SlotFunc",
    "SlotInput",
    "SlotNode",
    "SlotRef",
    "SlotResult",
    "TagProtectedError",
    "all_components",
    "all_registries",
    "autodiscover",
    "cached_template",
    "format_attributes",
    "get_component_by_class_id",
    "get_component_dirs",
    "get_component_files",
    "import_libraries",
    "merge_attributes",
    "register",
    "registry",
    "render_dependencies",
    "template_tag",
    "types",
]

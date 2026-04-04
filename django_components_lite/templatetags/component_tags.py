import django.template

from django_components_lite.attributes import HtmlAttrsNode
from django_components_lite.component import ComponentNode
from django_components_lite.slots import FillNode, SlotNode

# Tag name constants
COMPONENT_TAG = "component"
COMPONENT_SC_TAG = "componentsc"
COMPONENT_END_TAG = "endcomponent"
SLOT_TAG = "slot"
SLOT_END_TAG = "endslot"
FILL_TAG = "fill"
FILL_END_TAG = "endfill"

# NOTE: Variable name `register` is required by Django to recognize this as a template tag library
# See https://docs.djangoproject.com/en/5.2/howto/custom-template-tags
register = django.template.Library()

ComponentNode.register(register)
FillNode.register(register)
HtmlAttrsNode.register(register)
SlotNode.register(register)

# Register the self-closing component tag.
# ComponentScNode is identical to ComponentNode, but without an end tag.
ComponentScNode = type(
    "ComponentScNode",
    (ComponentNode,),
    {"tag": COMPONENT_SC_TAG, "end_tag": None},
)
ComponentScNode.register(register)

# Aliases for Python imports
component = ComponentNode.parse
componentsc = ComponentScNode.parse
fill = FillNode.parse
html_attrs = HtmlAttrsNode.parse
slot = SlotNode.parse

__all__ = [
    "COMPONENT_END_TAG",
    "COMPONENT_SC_TAG",
    "COMPONENT_TAG",
    "FILL_END_TAG",
    "FILL_TAG",
    "SLOT_END_TAG",
    "SLOT_TAG",
    "component",
    "componentsc",
    "fill",
    "html_attrs",
    "slot",
]

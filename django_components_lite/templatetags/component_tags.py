import django.template

from django_components_lite.attributes import HtmlAttrsNode
from django_components_lite.component import ComponentNode
from django_components_lite.slots import FillNode, SlotNode

# Self-closing component tag name (easy to rename later)
COMPONENT_SC_TAG = "componentsc"

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
    "COMPONENT_SC_TAG",
    "component",
    "componentsc",
    "fill",
    "html_attrs",
    "slot",
]

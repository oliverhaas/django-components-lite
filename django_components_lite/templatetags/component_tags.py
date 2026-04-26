import django.template

from django_components_lite.attributes import HtmlAttrsNode
from django_components_lite.component import ComponentNode
from django_components_lite.slots import FillNode, SlotNode

# NOTE: Variable name `register` is required by Django to recognize this as a template tag library
# See https://docs.djangoproject.com/en/5.2/howto/custom-template-tags
register = django.template.Library()

class ComponentScNode(ComponentNode):
    """Self-closing form of `{% comp %}`: `{% compc "x" / %}`. No body, no slots."""

    tag = "compc"
    end_tag = None


ComponentNode.register(register)
ComponentScNode.register(register)
FillNode.register(register)
HtmlAttrsNode.register(register)
SlotNode.register(register)

# Aliases for Python imports
component = ComponentNode.parse
componentsc = ComponentScNode.parse
fill = FillNode.parse
html_attrs = HtmlAttrsNode.parse
slot = SlotNode.parse

__all__ = [
    "component",
    "componentsc",
    "fill",
    "html_attrs",
    "slot",
]

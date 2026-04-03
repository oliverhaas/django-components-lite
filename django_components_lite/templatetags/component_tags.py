import django.template

from django_components_lite.attributes import HtmlAttrsNode
from django_components_lite.component import ComponentNode
from django_components_lite.dependencies import ComponentCssDependenciesNode, ComponentJsDependenciesNode

# REMOVED: Provide/Inject system
# from django_components_lite.provide import ProvideNode
from django_components_lite.slots import FillNode, SlotNode

# NOTE: Variable name `register` is required by Django to recognize this as a template tag library
# See https://docs.djangoproject.com/en/5.2/howto/custom-template-tags
register = django.template.Library()


# All tags are defined with our BaseNode class. Reasons for that are:
# - This ensures they all have the same set of features, like supporting flags,
#   or literal lists and dicts as parameters.
# - The individual Node classes double as a source of truth for the tag's documentation.
#
# NOTE: The documentation generation script in `docs/scripts/reference.py` actually
#   searches this file for all `Node` classes and uses them to generate the documentation.
#   The docstring on the Node classes is used as the tag's documentation.
ComponentNode.register(register)
ComponentCssDependenciesNode.register(register)
ComponentJsDependenciesNode.register(register)
FillNode.register(register)
HtmlAttrsNode.register(register)
# REMOVED: ProvideNode.register(register)
SlotNode.register(register)


# For an intuitive use via Python imports, the tags are aliased to the function name.
# E.g. so if the tag name is `slot`, one can also do:
# `from django_components_lite.templatetags.component_tags import slot`
component = ComponentNode.parse
component_css_dependencies = ComponentCssDependenciesNode.parse
component_js_dependencies = ComponentJsDependenciesNode.parse
fill = FillNode.parse
html_attrs = HtmlAttrsNode.parse
# REMOVED: provide = ProvideNode.parse
slot = SlotNode.parse


__all__ = [
    "component",
    "component_css_dependencies",
    "component_js_dependencies",
    "fill",
    "html_attrs",
    # REMOVED: "provide",
    "slot",
]

import django.template

from django_components_lite.attributes import HtmlAttrsNode
from django_components_lite.slots import FillNode, SlotNode

# `register` is the conventional name Django expects for a template-tag library module.
# See https://docs.djangoproject.com/en/5.2/howto/custom-template-tags
register = django.template.Library()

# `comp` and `compc` are intentionally NOT pre-registered here. ComponentRegistry
# installs them when the first component is registered, because the parser needs
# the registry + component name to dispatch correctly. With no components
# registered, `{% comp "..." %}` raises `Invalid block tag: 'comp'`, which is the
# right error.
FillNode.register(register)
HtmlAttrsNode.register(register)
SlotNode.register(register)

# Aliases for Python imports.
fill = FillNode.parse
html_attrs = HtmlAttrsNode.parse
slot = SlotNode.parse

__all__ = ["fill", "html_attrs", "slot"]

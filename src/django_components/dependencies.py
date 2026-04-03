"""
Simplified JS/CSS dependency management for django-components.

Components' JS/CSS files are served via Django's static files system.
Each component prepends its own <link>/<script> tags to its rendered HTML.
"""

from typing import TYPE_CHECKING, List, Literal, Optional, Type

from django.template import Context
from django.templatetags.static import static
from django.utils.safestring import mark_safe

from django_components.node import BaseNode

if TYPE_CHECKING:
    from django_components.component import Component

# Kept for backwards compatibility — strategies are no longer used.
DependenciesStrategy = Literal["document", "fragment", "simple", "prepend", "append", "ignore"]


def render_dependencies(content: str, strategy: DependenciesStrategy = "document") -> str:
    """No-op for backwards compatibility. Dependencies are now prepended by each component."""
    return content


def build_dependency_tags(comp_cls: Type["Component"]) -> str:
    """
    Build <link> and <script> tags for a component's JS/CSS files.

    Returns an HTML string to prepend to the component's rendered output.
    """
    tags: List[str] = []

    css_file = getattr(comp_cls, "css_file", None)
    if css_file:
        url = static(css_file)
        tags.append(f'<link href="{url}" media="all" rel="stylesheet">')

    js_file = getattr(comp_cls, "js_file", None)
    if js_file:
        url = static(js_file)
        tags.append(f'<script src="{url}"></script>')

    return "\n".join(tags)


#########################################################
# Template tags (no-ops — dependencies are now prepended
# directly by each component's render)
#########################################################


class ComponentCssDependenciesNode(BaseNode):
    """No-op. Kept for backwards compatibility with existing templates."""

    tag = "component_css_dependencies"
    end_tag = None
    allowed_flags = ()

    def render(self, context: Context) -> str:  # noqa: ARG002
        return ""


class ComponentJsDependenciesNode(BaseNode):
    """No-op. Kept for backwards compatibility with existing templates."""

    tag = "component_js_dependencies"
    end_tag = None
    allowed_flags = ()

    def render(self, context: Context) -> str:  # noqa: ARG002
        return ""

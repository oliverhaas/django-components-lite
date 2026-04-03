"""
Simplified JS/CSS dependency management for django-components.

Components' JS/CSS files are served via Django's static files system.
Each component prepends its own <link>/<script> tags to its rendered HTML.
"""

from typing import TYPE_CHECKING, List, Literal, Optional, Type

from django.template import Context
from django.templatetags.static import static
from django.utils.safestring import SafeString, mark_safe

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
    from django_components.component_media import UNSET  # noqa: PLC0415

    tags: List[str] = []

    # Media.css / Media.js (third-party or extra files declared via Django's Media class)
    media = comp_cls.media
    if media:
        for tag in media.render_css():
            tags.append(str(tag))
        for tag in media.render_js():
            tags.append(str(tag))

    # css_file — component's own CSS file
    css_path = _get_resolved_file_path(comp_cls, "css_file")
    if css_path:
        url = static(css_path)
        tags.append(f'<link href="{url}" media="all" rel="stylesheet">')

    # js_file — component's own JS file
    js_path = _get_resolved_file_path(comp_cls, "js_file")
    if js_path:
        url = static(js_path)
        tags.append(f'<script src="{url}"></script>')

    return "\n".join(tags)


def _get_resolved_file_path(comp_cls: Type["Component"], attr: str) -> Optional[str]:
    """
    Get the resolved static file path for a component's js_file or css_file.

    After lazy resolution, comp_cls._component_media.js_file / .css_file
    contains a path relative to COMPONENTS.dirs, which is what static() expects.
    """
    from django_components.component_media import UNSET  # noqa: PLC0415

    comp_media = getattr(comp_cls, "_component_media", None)
    if comp_media is None:
        return None

    value = getattr(comp_media, attr, UNSET)
    if value is UNSET or value is None:
        return None

    return str(value)


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

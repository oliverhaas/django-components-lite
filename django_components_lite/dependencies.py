"""
Simplified JS/CSS dependency management for django-components.

Components' JS/CSS files are served via Django's static files system.
Each component prepends its own <link>/<script> tags to its rendered HTML.
"""

from typing import TYPE_CHECKING

from django.templatetags.static import static

if TYPE_CHECKING:
    from django_components_lite.component import Component


def build_dependency_tags(comp_cls: type["Component"]) -> str:
    """
    Build <link> and <script> tags for a component's JS/CSS files.

    Returns an HTML string to prepend to the component's rendered output.
    """
    tags: list[str] = []

    css_file = getattr(comp_cls, "css_file", None)
    if css_file:
        url = static(css_file)
        tags.append(f'<link href="{url}" media="all" rel="stylesheet">')

    js_file = getattr(comp_cls, "js_file", None)
    if js_file:
        url = static(js_file)
        tags.append(f'<script src="{url}"></script>')

    return "\n".join(tags)

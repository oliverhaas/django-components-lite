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

    The result depends only on the class, so it's cached on the class itself
    (on first render, not at class creation — Django's ``static()`` may not
    be ready during import).
    """
    cached = comp_cls.__dict__.get("_dep_tags")
    if cached is not None:
        return cached

    tags: list[str] = []
    css_file = getattr(comp_cls, "css_file", None)
    if css_file:
        tags.append(f'<link href="{static(css_file)}" media="all" rel="stylesheet">')
    js_file = getattr(comp_cls, "js_file", None)
    if js_file:
        tags.append(f'<script src="{static(js_file)}"></script>')

    result = "\n".join(tags)
    comp_cls._dep_tags = result
    return result

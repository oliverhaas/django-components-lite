"""Build per-component <link>/<script> dependency tags from JS/CSS file paths."""

from typing import TYPE_CHECKING

from django.templatetags.static import static

if TYPE_CHECKING:
    from django_components_lite.component import Component


def build_dependency_tags(comp_cls: type["Component"]) -> str:
    """Return cached `<link>`/`<script>` tags for the component's CSS and JS files.

    Cached on first render rather than at class creation, since `static()` may not be
    ready at import time.
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

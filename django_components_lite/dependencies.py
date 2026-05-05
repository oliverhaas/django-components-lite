"""Build per-component <link>/<script> dependency tags from `Media.css` / `Media.js`."""

from typing import TYPE_CHECKING

from django.templatetags.static import static

if TYPE_CHECKING:
    from django_components_lite.component import Component


def build_dependency_tags(comp_cls: type[Component]) -> str:
    """Return cached `<link>` and `<script>` tags for the component's `Media.css` and `Media.js`.

    Cached on first render rather than at class creation, since `static()` may not be
    ready at import time.
    """
    cached = comp_cls.__dict__.get("_dep_tags")
    if cached is not None:
        return cached

    tags: list[str] = []
    media = getattr(comp_cls, "Media", None)
    if media is not None:
        tags.extend(
            f'<link href="{static(css_path)}" media="all" rel="stylesheet">'
            for css_path in getattr(media, "css", None) or ()
        )
        tags.extend(f'<script src="{static(js_path)}"></script>' for js_path in getattr(media, "js", None) or ())

    result = "\n".join(tags)
    comp_cls._dep_tags = result
    return result

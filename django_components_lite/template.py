from typing import TYPE_CHECKING

from django.template import Template
from django.template.loader import get_template as django_get_template

from django_components_lite.util.misc import get_module_info

if TYPE_CHECKING:
    from django_components_lite.component import Component


def get_component_template(component: "Component") -> Template | None:
    """Resolve the Template instance for a Component, or None if no template is defined."""
    if component.template_file is not None:
        # Cache the resolved Template on the class - avoids re-loading on every render.
        cached = getattr(component.__class__, "_cached_template", None)
        if cached is not None:
            return cached
        template = _load_django_template(component.template_file)
        component.__class__._cached_template = template
        return template

    if component.template:
        return _create_template_from_string(component.__class__, component.template)

    return None


def _create_template_from_string(component: type["Component"], template_string: str) -> Template:
    # Build a synthetic Origin so error messages point at the component's source file
    # rather than `<unknown source>`. Format: `path/to/component.py::ComponentName`.
    from django.template import Origin

    _, _, module_filepath = get_module_info(component)
    origin = Origin(name=f"{module_filepath}::{component.__name__}", template_name=None, loader=None)
    return Template(template_string, name=origin.template_name, origin=origin)


def _load_django_template(template_name: str) -> Template:
    return django_get_template(template_name).template

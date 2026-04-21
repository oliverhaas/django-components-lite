# API Reference

## Component

The base class for all components. Subclass this to create your own components.

```python
from django_components_lite import Component, register

@register("my_component")
class MyComponent(Component):
    template_file = "my_component.html"

    def get_context_data(self, **kwargs):
        return {"key": "value"}
```

**Key attributes:**

- `template_file` - Path to the component's template file. Resolved relative to the component's Python file, then relative to `COMPONENTS.dirs`, then Django template dirs.
- `template` - Inline template string (alternative to `template_file`).
- `template_name` - Legacy alias for `template_file`. Works as a descriptor for Django-style templating.
- `css_file` - Path to a CSS file whose `<link>` tag is prepended to the rendered output. Resolved the same way as `template_file`.
- `js_file` - Path to a JS file whose `<script>` tag is prepended to the rendered output.

**Instance attributes (available in `get_context_data`):**

- `self.args` - Positional arguments passed to the component.
- `self.kwargs` - Keyword arguments passed to the component.
- `self.slots` - Dict of slot name to `Slot` instance. Use `"name" in self.slots` to check if a slot was filled.
- `self.context` - The outer Django `Context` at the call site.
- `self.request` - The `HttpRequest` if available (e.g. via `RequestContext`), else `None`.

**Key methods:**

- `get_context_data(**kwargs)` - Return a dict of context variables for the template. Override with any signature; mypy will not complain.
- `render(args=None, kwargs=None, slots=None, context=None, request=None)` - Render the component to an HTML string (class method).
- `render_to_response(...)` - Render and return an `HttpResponse` (class method). Accepts the same arguments as `render()`.

## Registration

```python
from django_components_lite import register

@register("name")
class MyComponent(Component):
    ...
```

Or register manually:

```python
from django_components_lite import registry

registry.register("name", MyComponent)
registry.unregister("name")
registry.get("name")  # Returns the component class
registry.all()  # Returns dict of all registered components
```

## Settings

```python
from django_components_lite import ComponentsSettings

COMPONENTS = ComponentsSettings(
    autodiscover=True,
    dirs=[BASE_DIR / "components"],
    app_dirs=["components"],
)
```

See [Settings](../user-guide/settings.md) for all options.

## Template Tags

Available after `{% load component_tags %}`:

| Tag | Description |
|-----|-------------|
| `{% component "name" %}...{% endcomponent %}` | Render a component |
| `{% slot "name" %}...{% endslot %}` | Define a slot in a component template |
| `{% fill "name" %}...{% endfill %}` | Fill a slot when using a component |

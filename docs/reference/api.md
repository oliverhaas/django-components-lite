# API Reference

## Component

The base class for all components. Subclass this to create your own components.

```python
from django_components_lite import Component, register

@register("my_component")
class MyComponent(Component):
    template_name = "my_component/my_component.html"

    def get_context_data(self, **kwargs):
        return {"key": "value"}
```

**Key attributes:**

- `template_name` - Path to the component's template file
- `template` - Inline template string (alternative to `template_name`)

**Key methods:**

- `get_context_data(**kwargs)` - Return a dict of context variables for the template
- `render(kwargs=None, slots=None)` - Render the component to an HTML string (class method)
- `render_to_response(kwargs=None, slots=None)` - Render and return an `HttpResponse` (class method)

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

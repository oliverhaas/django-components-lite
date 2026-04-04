# API Reference

## Component

::: django_components_lite.Component
    options:
      show_source: false
      members:
        - template_name
        - template
        - get_context_data
        - render
        - render_to_response

## Registration

::: django_components_lite.register
    options:
      show_source: false

::: django_components_lite.ComponentRegistry
    options:
      show_source: false

## Settings

::: django_components_lite.ComponentsSettings
    options:
      show_source: false

## Template Tags

The following template tags are available after `{% load component_tags %}`:

- `{% component "name" %}...{% endcomponent %}` - Render a component
- `{% slot "name" %}...{% endslot %}` - Define a slot in a component template
- `{% fill "name" %}...{% endfill %}` - Fill a slot when using a component

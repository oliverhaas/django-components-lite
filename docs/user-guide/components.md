# Components

## Defining a component

A component is a Python class that extends `Component`:

```python
from django_components_lite import Component, register

@register("card")
class Card(Component):
    template_name = "card/card.html"

    def get_context_data(self, title, body=""):
        return {"title": title, "body": body}
```

## Template

The template uses standard Django template syntax plus component-specific tags:

```html
{% load component_tags %}
<div class="card">
  <h2>{{ title }}</h2>
  <div class="card-body">
    {% slot "content" %}{{ body }}{% endslot %}
  </div>
</div>
```

## Rendering

From a template:

```html
{% load component_tags %}
{% component "card" title="My Card" %}
  {% fill "content" %}
    <p>Custom content here.</p>
  {% endfill %}
{% endcomponent %}
```

From Python:

```python
html = Card.render(kwargs={"title": "My Card"})
```

## Component discovery

Components are automatically discovered from:

- `components/` directories inside each installed app
- Directories listed in `COMPONENTS.dirs`
- Modules listed in `COMPONENTS.libraries`


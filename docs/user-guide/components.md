# Components

## Defining a component

A component is a Python class that extends `Component`:

```python
from django_components_lite import Component, register

@register("card")
class Card(Component):
    template_file = "card.html"

    def get_context_data(self, title, body=""):
        return {"title": title, "body": body}
```

Positional tag args are routed to named parameters on ``get_context_data``. For example:

```django
{% comp "card" "My Title" "Body text" %}{% endcomp %}
```

binds ``title="My Title"`` and ``body="Body text"``. Mixed positional + keyword args (``{% comp "card" "My Title" body="..." %}``) work the same way as a normal Python function call — passing the same parameter both ways raises ``TypeError``. If your override declares ``*args``, positional tag args are forwarded as ``args`` natively.

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
{% comp "card" title="My Card" %}
  {% fill "content" %}
    <p>Custom content here.</p>
  {% endfill %}
{% endcomp %}
```

From Python:

```python
html = Card.render(kwargs={"title": "My Card"})
```

## Component discovery

Components are automatically discovered from:

- `components/` directories inside each installed app
- Directories listed in `COMPONENTS.dirs`


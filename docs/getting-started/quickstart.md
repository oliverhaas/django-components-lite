# Quick Start

## Create a component

Create a file at `components/greeting/greeting.py`:

```python
from django_components_lite import Component, register

@register("greeting")
class Greeting(Component):
    template_name = "greeting/greeting.html"

    def get_context_data(self, name="World"):
        return {"name": name}
```

Create the template at `components/greeting/greeting.html`:

```html
<div class="greeting">
  Hello, {{ name }}!
  {% load component_tags %}
  {% slot "extra" %}{% endslot %}
</div>
```

## Use it in a template

```html
{% load component_tags %}

{% component "greeting" name="Django" %}
  {% fill "extra" %}
    <p>Welcome to components!</p>
  {% endfill %}
{% endcomponent %}
```

This renders:

```html
<div class="greeting">
  Hello, Django!
  <p>Welcome to components!</p>
</div>
```

## Adding CSS and JS

Place static files next to your component:

```
components/greeting/
    greeting.py
    greeting.html
    greeting.css
    greeting.js
```

Define them in your component class:

```python
@register("greeting")
class Greeting(Component):
    template_name = "greeting/greeting.html"

    class Media:
        css = "greeting/greeting.css"
        js = "greeting/greeting.js"

    def get_context_data(self, name="World"):
        return {"name": name}
```

The CSS and JS tags are automatically prepended to the component's rendered HTML.

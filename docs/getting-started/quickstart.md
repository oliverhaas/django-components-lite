# Quick Start

## Create a component

Create a file at `components/greeting/greeting.py`:

```python
from django_components_lite import Component, register

@register("greeting")
class Greeting(Component):
    template_file = "greeting.html"

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

{% comp "greeting" name="Django" %}
  {% fill "extra" %}
    <p>Welcome to components!</p>
  {% endfill %}
{% endcomp %}
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

Declare them as `css_file` / `js_file` attributes on the component class:

```python
@register("greeting")
class Greeting(Component):
    template_file = "greeting.html"
    css_file = "greeting.css"
    js_file = "greeting.js"

    def get_context_data(self, name="World"):
        return {"name": name}
```

Paths are resolved relative to the component's Python file. When the component renders, `<link>` and `<script>` tags for the declared files are automatically prepended to the output.

## Overview

Each component can have single "primary" HTML, CSS and JS file associated with them.

Each of these can be defined as a file path:

- HTML files are defined using [`Component.template_file`](../../reference/api.md#django_components.Component.template_file)
- CSS files are defined using [`Component.css_file`](../../reference/api.md#django_components.Component.css_file)
- JS files are defined using [`Component.js_file`](../../reference/api.md#django_components.Component.js_file)

```py
@register("calendar")
class Calendar(Component):
    template_file = "calendar.html"
    css_file = "calendar.css"
    js_file = "calendar.js"
```

Read more about each file type below:

- [HTML](#html)
- [CSS](#css)
- [JS](#js)

JS and CSS files are served via Django's static files system. When a component is rendered,
`<link>` and `<script>` tags are prepended to the component's HTML output.

## HTML

Components use Django's template system to define their HTML.
This means that you can use [Django's template syntax](https://docs.djangoproject.com/en/5.2/ref/templates/language/) to define your HTML.

Inside the template, you can access the data returned from the [`get_template_data()`](../../../reference/api/#django_components.Component.get_template_data) method.

Define the HTML in a separate file and reference it using [`template_file`](../../reference/api.md#django_components.Component.template_file):

```python
class Button(Component):
    template_file = "button.html"

    def get_template_data(self, args, kwargs, slots, context):
        return {
            "text": kwargs.get("text", "Click me"),
            "icon": kwargs.get("icon", None),
        }
```

```django title="button.html"
<button class="btn">
    {% if icon %}
        <i class="{{ icon }}"></i>
    {% endif %}
    {{ text }}
</button>
```

### HTML processing

Django Components expects the rendered template to be valid HTML.

Here is how the HTML is post-processed:

1. **Insert component ID**: Each root element in the rendered HTML automatically receives a `data-djc-id-cxxxxxx` attribute containing a unique component instance ID.

    ```html
    <!-- Output HTML -->
    <div class="card" data-djc-id-c1a2b3c>
        ...
    </div>
    <div class="backdrop" data-djc-id-c1a2b3c>
        ...
    </div>
    ```

2. **Insert JS and CSS tags**: If the component defines `js_file` or `css_file`, `<script>` and `<link>` tags
   are prepended to the component's rendered HTML.

    For more information, see [Rendering JS / CSS](../../advanced/rendering_js_css).

## JS

Define the component's JS in a separate file using [`js_file`](../../reference/api.md#django_components.Component.js_file):

```python
class Button(Component):
    js_file = "button.js"
```

```js title="button.js"
console.log("Hello, world!");
```

The JS file is served via Django's static files system. A `<script>` tag pointing to the
static file URL is prepended to the component's rendered HTML.

## CSS

Define the component's CSS in a separate file using [`css_file`](../../reference/api.md#django_components.Component.css_file):

```python
class Button(Component):
    css_file = "button.css"
```

```css title="button.css"
.btn {
    color: red;
}
```

The CSS file is served via Django's static files system. A `<link>` tag pointing to the
static file URL is prepended to the component's rendered HTML.

## File paths

File paths for HTML / JS / CSS files are simple strings. You can specify them
relative to the component's directory.

So if you have a directory with following files:

```
[project root]/components/calendar/
├── calendar.html
├── calendar.css
├── calendar.js
└── calendar.py
```

You can define the component like this:

```py title="[project root]/components/calendar/calendar.py"
from django_components import Component, register

@register("calendar")
class Calendar(Component):
    template_file = "calendar.html"
    css_file = "calendar.css"
    js_file = "calendar.js"
```

Assuming that
[`COMPONENTS.dirs`](../../reference/settings.md#django_components.app_settings.ComponentsSettings.dirs)
contains path `[project root]/components`, the example above is the same as writing out:

```py title="[project root]/components/calendar/calendar.py"
from django_components import Component, register

@register("calendar")
class Calendar(Component):
    template_file = "calendar/template.html"
    css_file = "calendar/style.css"
    js_file = "calendar/script.js"
```

If the path cannot be resolved relative to the component, django-components will attempt
to resolve the path relative to the component directories, as set in
[`COMPONENTS.dirs`](../../reference/settings.md#django_components.app_settings.ComponentsSettings.dirs)
or
[`COMPONENTS.app_dirs`](../../reference/settings.md#django_components.app_settings.ComponentsSettings.app_dirs).

## File path resolution

Component file paths (`template_file`, `js_file`, `css_file`) are resolved lazily when the
component is first rendered or when its attributes are first accessed.

File paths are resolved relative to the component's Python file location. If not found there,
they are resolved relative to the component directories set in
[`COMPONENTS.dirs`](../../reference/settings.md#django_components.app_settings.ComponentsSettings.dirs)
or
[`COMPONENTS.app_dirs`](../../reference/settings.md#django_components.app_settings.ComponentsSettings.app_dirs).

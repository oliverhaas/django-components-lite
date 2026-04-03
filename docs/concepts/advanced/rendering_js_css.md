## Introduction

Components consist of 3 parts - HTML, JS and CSS.

Handling of HTML is straightforward - it is rendered as is, and inserted where
the [`{% component %}`](../../../reference/template_tags#component) tag is.

JS and CSS are handled via Django's static files system. Each component's JS and CSS
files are served as static files, and `<script>` / `<link>` tags are prepended to
the component's rendered HTML.

## How JS / CSS works

When a component defines `js_file` or `css_file`, django-components:

1. Resolves the file path relative to the component's directory.
2. Generates `<link>` (for CSS) and `<script>` (for JS) tags pointing to the static file URL.
3. Prepends these tags to the component's rendered HTML output.

For example, given this component:

```python
from django_components_lite import Component

class MyButton(Component):
    template_file = "my_button/my_button.html"
    js_file = "my_button/my_button.js"
    css_file = "my_button/my_button.css"
```

When rendered, the output will look like:

```html
<link href="/static/my_button/my_button.css" media="all" rel="stylesheet">
<script src="/static/my_button/my_button.js"></script>
<button class="my-button">Click me!</button>
```

## Static files setup

Since JS and CSS are served via Django's static files system, make sure you have:

1. `django.contrib.staticfiles` in your `INSTALLED_APPS`.
2. Your component directories included in Django's static file discovery
   (either via `STATICFILES_DIRS` or app directories).
3. Run `collectstatic` for production deployments.

## HTML fragments

When using components with AJAX / HTML-over-the-wire patterns (HTMX, AlpineJS, etc.),
each component fragment will include its own `<link>` and `<script>` tags.

Read more about [HTML fragments](../../advanced/html_fragments).

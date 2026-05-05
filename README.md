# django-components-lite

A fork of [django-components](https://github.com/django-components/django-components) with most features stripped out. A component is a Python class, a Django template, and optional CSS/JS.

If you want the full feature set, use [django-components](https://github.com/django-components/django-components) directly.

## Attribution

Built on [django-components](https://github.com/django-components/django-components) by [Emil Stenström](https://github.com/EmilStenstrom), [Juro Oravec](https://github.com/JuroOravec), and [all contributors](https://github.com/django-components/django-components/graphs/contributors).

## Other Django component libraries

- [django-components](https://github.com/django-components/django-components): the upstream project.
- [django-cotton](https://github.com/wrabit/django-cotton): HTML-like syntax (`<c-card title="..." />`), template-only.
- [django-viewcomponent](https://pypi.org/project/django-viewcomponent/): Rails-style, one Python class per component.
- [slippers](https://pypi.org/project/slippers/): template-only, no Python per component.
- [JinjaX](https://jinjax.scaletti.dev/): HTML-like component syntax for Jinja2.

`django-components-lite` is standard Django template tags (`{% comp %}` / `{% slot %}` / `{% fill %}`), one Python class per component, no special template syntax, no monkeypatches, no extension system. The package is ~3000 LOC and can be vendored.

## Features

- Component classes with Python logic and Django templates
- `{% comp %}` / `{% endcomp %}` (and self-closing `{% compc %}`) template tags
- Slots and fills (`{% slot %}`, `{% fill %}`)
- Component autodiscovery
- Component registry
- Static file handling (JS/CSS)
- Isolated component context
- HTML attribute rendering utilities

## Removed vs. upstream

- Extension system
- Built-in components (`DynamicComponent`, `ErrorFallback`)
- Component caching
- Provide/Inject system
- Template expressions
- Management commands
- JS/CSS data methods and dependency management
- Type validation (Args/Kwargs/Slots/TemplateData)
- `on_render()` generator system and deferred rendering
- `context_behavior` setting (always isolated, like Django's `inclusion_tag`)
- Tag formatters
- Component views and URLs
- `libraries` setting and `import_libraries()`
- `reload_on_file_change` setting
- All deprecated setting aliases

## Installation

```bash
pip install django-components-lite
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "django_components_lite",
]
```

Add the component template loader so component templates get discovered:

```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
                "django_components_lite.template_loader.Loader",
            ],
        },
    },
]
```

By default, components are discovered in:
- a `components/` directory at project root, and
- a `components/` directory inside each installed app.

To customize, set `COMPONENTS`:

```python
from django_components_lite import ComponentsSettings

COMPONENTS = ComponentsSettings(
    dirs=[BASE_DIR / "components"],
    app_dirs=["components"],
)
```

## Defining a component

A component is a Python class with a template:

```python
# components/greeting/greeting.py
from django_components_lite import Component, register

@register("greeting")
class Greeting(Component):
    template_name = "greeting.html"

    def get_context_data(self, name="World"):
        return {"name": name}
```

```html
<!-- components/greeting/greeting.html -->
{% load component_tags %}
<div class="greeting">
  Hello, {{ name }}!
  {% slot "extra" %}{% endslot %}
</div>
```

`template_name` is resolved relative to the component's Python file, then `COMPONENTS.dirs`, then Django's template dirs. Use `template = "..."` for an inline template string.

Static files are declared via a nested `Media` class (same shape as Django's [Forms.Media](https://docs.djangoproject.com/en/stable/topics/forms/media/)):

```
components/greeting/
    greeting.py
    greeting.html
    greeting.css
    greeting.js
```

```python
class Greeting(Component):
    template_name = "greeting.html"

    class Media:
        css = ["greeting.css"]
        js = ["greeting.js"]
```

A `<link>` or `<script>` tag is prepended to the output for each entry.

## Using a component

From a template:

```html
{% load component_tags %}
{% comp "greeting" name="Django" %}
  {% fill "extra" %}<p>Welcome!</p>{% endfill %}
{% endcomp %}
```

Self-closing form (no body / no fills):

```html
{% compc "greeting" name="Django" %}
```

Positional arguments are routed to named parameters on `get_context_data`:

```python
def get_context_data(self, title, body=""): ...
```

```html
{% comp "card" "My Title" "Body text" %}{% endcomp %}
```

binds `title="My Title"` and `body="Body text"`. Mixed positional and keyword args follow Python call semantics. If `get_context_data` declares `*args`, positional tag args are forwarded.

From Python:

```python
html = Greeting.render(kwargs={"name": "Django"})
```

`Component.render_to_response(...)` returns an `HttpResponse`.

## Slots

Slots are placeholders a parent template fills in.

```html
{% load component_tags %}
<div class="panel">
  <header>{% slot "header" %}Default header{% endslot %}</header>
  <main>{% slot "body" required %}{% endslot %}</main>
  <footer>{% slot "footer" %}{% endslot %}</footer>
</div>
```

Fill them with `{% fill %}`:

```html
{% comp "panel" %}
  {% fill "header" %}<h2>Custom Header</h2>{% endfill %}
  {% fill "body" %}<p>Panel content.</p>{% endfill %}
{% endcomp %}
```

Content inside `{% comp %}` without a `{% fill %}` goes into the slot marked `default`:

```html
{% slot "content" default %}{% endslot %}
```

```html
{% comp "panel" %}
  This goes into the default slot.
{% endcomp %}
```

The body of `{% slot %}` is the fallback when no `{% fill %}` is provided. To branch on whether a slot was filled, check `self.slots`:

```python
def get_context_data(self, **kwargs):
    return {"has_header": "header" in self.slots}
```

## Settings

```python
from django_components_lite import ComponentsSettings

COMPONENTS = ComponentsSettings(
    autodiscover=True,
    dirs=[BASE_DIR / "components"],
    app_dirs=["components"],
    static_files_allowed=[".css", ".js"],
    static_files_forbidden=[".html", ".py"],
)
```

| Setting | Default | Description |
|---|---|---|
| `autodiscover` | `True` | Automatically discover components in app directories |
| `dirs` | `[BASE_DIR / "components"]` | Root-level directories to search for components |
| `app_dirs` | `["components"]` | Subdirectory name within apps to search for components |
| `static_files_allowed` | CSS, JS, images, fonts | File extensions served as static files |
| `static_files_forbidden` | `.html`, `.py`, etc. | File extensions never served as static files |

Tag names (`{% comp %}` / `{% endcomp %}` / `{% compc %}`) are not configurable.

## API reference

### `Component`

Class attributes:

- `template_name`: path to the template, resolved relative to the component's Python file, then `COMPONENTS.dirs`, then Django template dirs.
- `template`: inline template string, used instead of `template_name`.
- `class Media`: nested class with `css` and `js` lists of file paths.

Instance attributes (available in `get_context_data`):

- `self.args`: positional arguments.
- `self.kwargs`: keyword arguments.
- `self.slots`: dict of slot name to `Slot`. `"name" in self.slots` checks whether a slot was filled.
- `self.context`: outer Django `Context` at the call site.
- `self.request`: the `HttpRequest`, or `None`.

Methods:

- `get_context_data(**kwargs)`: return a dict of context variables. Override with any signature.
- `Component.render(context=None, args=None, kwargs=None, slots=None, request=None)`: returns rendered HTML.
- `Component.render_to_response(...)`: same arguments as `render()`, returns an `HttpResponse`. Extra kwargs are forwarded to the response class.

### Registration

```python
from django_components_lite import register, registry

@register("name")
class MyComponent(Component): ...

# or manually:
registry.register("name", MyComponent)
registry.unregister("name")
registry.get("name")   # component class
registry.all()         # dict of all registered components
```

### Template tags

Available after `{% load component_tags %}`:

| Tag | Description |
|---|---|
| `{% comp "name" %}...{% endcomp %}` | Render a component, with optional slot fills in the body |
| `{% compc "name" %}` | Self-closing form, no body, no end tag |
| `{% slot "name" %}...{% endslot %}` | Define a slot in a component template |
| `{% fill "name" %}...{% endfill %}` | Fill a slot when using a component |
| `{% html_attrs attrs defaults key=val %}` | Render an HTML attribute string by merging `attrs` over `defaults`, then appending extra kwargs (`class`/`style` are space-joined) |

### HTML attribute helpers

Used by `{% html_attrs %}` and available in Python:

```python
from django_components_lite import format_attributes, merge_attributes

merge_attributes({"class": "btn"}, {"class": "btn-primary"})
# -> {"class": "btn btn-primary"}

format_attributes({"class": "btn", "disabled": True})
# -> 'class="btn" disabled'
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## Links

- [django-components](https://github.com/django-components/django-components): upstream
- [Issues](https://github.com/oliverhaas/django-components-lite/issues)

## License

MIT. See [LICENSE](LICENSE).

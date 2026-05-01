# django-components-lite

**An exploratory, lightweight fork of [django-components](https://github.com/django-components/django-components).**

This package strips django-components down to its core: simple, reusable template components for Django, just templates with some optional Python logic. The goal is to see how a minimal django-components feels in practice.

## Attribution

This project is built on the work of the **[django-components](https://github.com/django-components/django-components)** project by **[Emil Stenström](https://github.com/EmilStenstrom)**, **[Juro Oravec](https://github.com/JuroOravec)**, and [all contributors](https://github.com/django-components/django-components/graphs/contributors).

**If you're looking for a mature, full-featured, and widely used component library for Django, use [django-components](https://github.com/django-components/django-components).** It has an active community, extensive documentation, and a rich feature set.

## How this compares

A few Django component libraries with different philosophies:

- **[django-components](https://github.com/django-components/django-components)** — the upstream project. Big, full-featured, introduces a lot of new template behavior, almost a parallel template language.
- **[django-cotton](https://github.com/wrabit/django-cotton)** — HTML-like syntax (`<c-card title="..." />`); template-only, no Python logic per component.
- **[django-viewcomponent](https://pypi.org/project/django-viewcomponent/)** — modeled on Rails ViewComponent. One Python class per component encapsulating template + logic.
- **[slippers](https://pypi.org/project/slippers/)** — intentionally tiny; template-only, no Python per component.
- **[JinjaX](https://jinjax.scaletti.dev/)** — HTML-like component syntax for Jinja2 (not Django templates).

`django-components-lite` sits on the small end of that spectrum: standard Django template tags (`{% comp %}` / `{% slot %}` / `{% fill %}`), one Python class per component for context logic, no special template syntax, no monkeypatches, no extension system.

If even this is more than you need, the package is small (~3000 LOC of regular Django patterns) and is a reasonable starting point to copy into your project and inline rather than depend on as a separate package.

## Features

What django-components-lite keeps:

- Component classes with Python logic and Django templates
- `{% comp %}` / `{% endcomp %}` (and self-closing `{% compc %}`) template tags
- Slots and fills (`{% slot %}`, `{% fill %}`)
- Component autodiscovery
- Component registry
- Static file handling (JS/CSS)
- Isolated component context
- HTML attribute rendering utilities

## What's removed (vs. upstream)

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

`template_name` is resolved relative to the component's Python file, then relative to `COMPONENTS.dirs`, then Django's template dirs. You can use `template = "..."` for an inline template string instead.

To attach static files, place them next to the component and declare them via a nested `Media` class (matching Django's [Forms.Media](https://docs.djangoproject.com/en/stable/topics/forms/media/) convention):

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

When the component renders, `<link>` and `<script>` tags for the declared files are prepended to the output.

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

binds `title="My Title"` and `body="Body text"`. Mixed positional + keyword args follow Python call semantics — passing the same parameter both ways raises `TypeError`. If your override declares `*args`, positional tag args are forwarded as `args`.

From Python:

```python
html = Greeting.render(kwargs={"name": "Django"})
```

`Component.render_to_response(...)` is also available and returns an `HttpResponse`.

## Slots

Slots let parent templates inject content into specific spots in a component.

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

Content placed directly inside `{% comp %}` (no `{% fill %}`) goes into the slot marked `default`:

```html
{% slot "content" default %}{% endslot %}
```

```html
{% comp "panel" %}
  This goes into the default slot.
{% endcomp %}
```

The body of `{% slot %}` is the fallback, used when no `{% fill %}` is provided. To branch on whether a slot was filled, check `self.slots` in Python and pass the result as a context variable:

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

Component tag names are fixed: `{% comp %}` / `{% endcomp %}` / `{% compc %}`. They are not configurable.

## API reference

### `Component`

Subclass to define your own component.

**Class attributes:**

- `template_name` — Path to the template. Resolved relative to the component's Python file, then `COMPONENTS.dirs`, then Django template dirs.
- `template` — Inline template string (alternative to `template_name`).
- `class Media:` — Nested class declaring CSS/JS files. `Media.css` and `Media.js` are lists of paths; one `<link>` / `<script>` tag is prepended per entry.

**Instance attributes (available in `get_context_data`):**

- `self.args` — positional arguments passed to the component.
- `self.kwargs` — keyword arguments.
- `self.slots` — dict of slot name to `Slot` instance. `"name" in self.slots` checks whether a slot was filled.
- `self.context` — outer Django `Context` at the call site.
- `self.request` — the `HttpRequest` if available, else `None`.

**Methods:**

- `get_context_data(**kwargs)` — return a dict of context variables. Override with any signature.
- `Component.render(context=None, args=None, kwargs=None, slots=None, request=None)` — class method, returns rendered HTML string.
- `Component.render_to_response(...)` — class method, returns `HttpResponse`. Same arguments as `render()`, plus extra kwargs forwarded to the response class.

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

For composing attribute dicts in Python (used by `{% html_attrs %}` under the hood):

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

- [django-components (upstream)](https://github.com/django-components/django-components) — the full-featured upstream project
- [Issues](https://github.com/oliverhaas/django-components-lite/issues)

## License

MIT — see [LICENSE](LICENSE).

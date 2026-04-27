# django-components-lite

**An exploratory, lightweight fork of [django-components](https://github.com/django-components/django-components).**

This package strips django-components down to its core: simple, reusable template components for Django, just templates with some optional python logic. The goal is to see how a minimal django-components feels in practice.

## Attribution

This project is built on the excellent work of the **[django-components](https://github.com/django-components/django-components)** project by **[Emil Stenström](https://github.com/EmilStenstrom)**, **[Juro Oravec](https://github.com/JuroOravec)**, and [all contributors](https://github.com/django-components/django-components/graphs/contributors). 

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

What django-components-lite keeps from django-components:

- Component classes with Python logic and Django templates
- `{% comp %}` / `{% endcomp %}` template tags
- Slots and fills (`{% slot %}`, `{% fill %}`)
- Component autodiscovery
- Component registry
- Static file handling (JS/CSS)
- Isolated component context
- HTML attribute rendering utilities

## What's removed?

Compared to django-components, the following have been stripped out:

- Extension system
- Built-in components (DynamicComponent, ErrorFallback)
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

Add to your Django settings:

```python
INSTALLED_APPS = [
    # ...
    "django_components_lite",
]
```

## Quick example

```python
# myapp/components/greeting/greeting.py
from django_components_lite import Component, register

@register("greeting")
class Greeting(Component):
    template_file = "greeting.html"

    def get_context_data(self, name):
        return {"name": name}
```

```html
<!-- myapp/components/greeting/greeting.html -->
<div class="greeting">
  Hello, {{ name }}!
  {% slot "extra" %}{% endslot %}
</div>
```

```html
<!-- In any template -->
{% load component_tags %}
{% comp "greeting" name="World" %}
  {% fill "extra" %}
    <p>Welcome!</p>
  {% endfill %}
{% endcomp %}
```

## Links

- [django-components (original)](https://github.com/django-components/django-components)  -  the full-featured upstream project
- [Documentation](https://oliverhaas.github.io/django-components-lite/)
- [Issues](https://github.com/oliverhaas/django-components-lite/issues)

## License

MIT  -  see [LICENSE](LICENSE).

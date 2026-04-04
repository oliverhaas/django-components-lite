# django-components-lite

**An exploratory, lightweight fork of [django-components](https://github.com/django-components/django-components).**

This package strips django-components down to its core: simple, reusable template components for Django  -  nothing more. The goal is to see how a minimal django-components feels in practice.

## Attribution

This project is built on the excellent work of the **[django-components](https://github.com/django-components/django-components)** project by **[Emil Stenström](https://github.com/EmilStenstrom)**, **[Juro Oravec](https://github.com/JuroOravec)**, and [all contributors](https://github.com/django-components/django-components/graphs/contributors). Their years of work made this possible.

**If you're looking for a mature, full-featured, and battle-tested component library for Django, use [django-components](https://github.com/django-components/django-components).** It has an active community, extensive documentation, and a rich feature set.


## Features

What django-components-lite keeps from django-components:

- Component classes with Python logic and Django templates
- `{% component %}` / `{% endcomponent %}` template tags
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
- `context_behavior` setting (always isolated)
- Tag formatters
- Component views and URLs

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
from django_components_lite import Component

class Greeting(Component):
    template_name = "greeting/greeting.html"

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
{% component "greeting" name="World" %}
  {% fill "extra" %}
    <p>Welcome!</p>
  {% endfill %}
{% endcomponent %}
```

## Links

- [django-components (original)](https://github.com/django-components/django-components)  -  the full-featured upstream project
- [Documentation](https://oliverhaas.github.io/django-components-lite/)
- [Issues](https://github.com/oliverhaas/django-components-lite/issues)

## License

MIT  -  see [LICENSE](LICENSE).

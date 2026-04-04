# django-components-lite

Lightweight reusable template components for Django.

An exploratory fork of [django-components](https://github.com/django-components/django-components) that strips the library down to its core: define a component with a Python class and a template, use it in your templates, and render.

## Features

- Component classes with Python logic and Django templates
- `{% component %}` / `{% endcomponent %}` template tags
- Slots and fills (`{% slot %}`, `{% fill %}`)
- Component autodiscovery
- Component registry
- Static file handling (JS/CSS)
- Isolated component context
- HTML attribute rendering utilities

## Attribution

This project is built on the work of the [django-components](https://github.com/django-components/django-components) project by [Emil Stenstrom](https://github.com/EmilStenstrom), [Juro Oravec](https://github.com/JuroOravec), and [all contributors](https://github.com/django-components/django-components/graphs/contributors).

**If you want a mature, full-featured component library for Django with a longer history of maintaining it, use [django-components](https://github.com/django-components/django-components).**

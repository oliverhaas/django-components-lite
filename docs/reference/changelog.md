# Changelog

## 0.1.0a1

Initial release. Forked from [django-components](https://github.com/django-components/django-components) v0.143.0.

- Stripped to core component rendering functionality
- Renamed package to `django-components-lite` (import: `django_components_lite`)
- Python 3.12+ and Django 5.2+ only
- Switched to hatchling build system with uv
- Removed: extension system, built-in components, caching, provide/inject, template expressions, management commands, JS/CSS data methods, type validation, on_render generators, context_behavior setting, tag formatters, component views/URLs
- Removed deprecated settings

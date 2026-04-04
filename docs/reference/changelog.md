# Changelog

## 0.1.0a1

Initial release. Forked from [django-components](https://github.com/django-components/django-components) v0.143.0.

### Removed from upstream

- Extension system
- Built-in components (DynamicComponent, ErrorFallback)
- Component caching
- Provide/Inject system (`inject()` method, `{% provide %}` tag)
- Template expressions
- Management commands
- JS/CSS data methods and dependency management
- Type validation (Args/Kwargs/Slots/TemplateData)
- `on_render()` generator system and deferred rendering
- `context_behavior` setting (always isolated)
- Tag formatters
- Component views and URLs
- `libraries` setting and `import_libraries()` function
- `reload_on_file_change` setting
- All deprecated setting aliases (`debug_highlight_components`, `debug_highlight_slots`, `dynamic_component_name`, `template_cache_size`, `reload_on_template_change`, `forbidden_static_files`)

### Changed

- Renamed package to `django-components-lite` (import: `django_components_lite`)
- Python 3.12+ and Django 5.2+ only
- Switched build system from setuptools to hatchling
- Switched from pip/tox to uv
- Moved source from `src/` to flat layout
- Moved `sampleproject/` to `examples/simple/`
- Rewrote documentation from scratch
- Simplified CI workflows
- Automatic tagging and PyPI publishing on version bump

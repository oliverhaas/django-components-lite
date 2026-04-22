# Changelog

## 0.4.1

### Fixed

- Component subclasses with `TYPE_CHECKING`-guarded forward-reference annotations on `get_context_data` no longer crash at class-creation time on Python 3.14. The positional-parameter introspection now reads `func.__code__` directly instead of going through `inspect.signature`, which on 3.14 eagerly evaluates `__annotate__` (PEP 649) and raises `NameError` for unresolved names. The fix is also version-agnostic and slightly faster.

## 0.4.0

### Added

- Positional tag arguments are now routed to named parameters on ``Component.get_context_data``. ``{% comp "form_input_label" "Email" "email" %}`` now binds cleanly to ``def get_context_data(self, label, for_)``. Mixed positional + keyword args follow Python function-call semantics: passing the same parameter both ways raises ``TypeError``, as does exceeding the declared positional count. Overrides that declare ``*args`` receive positional tag args natively. The base ``def get_context_data(self, **kwargs)`` is unchanged — positional args remain accessible via ``self.args``.

## 0.3.0

### Breaking

The default component tag names changed: `{% component %}` / `{% endcomponent %}` / `{% componentsc %}` are now `{% comp %}` / `{% endcomp %}` / `{% compc %}`. If you want the old names back, add to your Django settings:

```python
COMPONENTS = ComponentsSettings(
    tag_name="component",
    tag_name_sc="componentsc",
)
```

### Added

- `tag_name` and `tag_name_sc` settings to configure the component tag names. The end tag is always derived as `f"end{tag_name}"`. See [Settings](../user-guide/settings.md#customizing-tag-names).

## 0.2.1

### Fixed

- `Component.get_context_data` now declared as `Any` at the class body so subclass overrides with narrowed signatures (e.g. `def get_context_data(self, *, user): ...`) don't trigger mypy's `[override]` Liskov-substitution check. Runtime behavior is unchanged.

## 0.2.0

### Performance

Render pipeline rewritten around a flat `Context` instead of stacked `context.update()` pushes. On a 3000-component props-only page, per-component overhead dropped from ~30 µs to ~5.7 µs, bringing total render time to within 1.57x of plain `{% include %}` (was 3.49x) and 1.37x of Django's `@register.inclusion_tag` (was ~3x).

Key changes:

- Build the render `Context` flat: `template_data`, context processors, and internal keys merged into the base dict, no per-render stack pushes.
- Skip the `context.new()` / `copy.copy()` path when creating the isolated context; construct the `Context` directly.
- Skip the outer-context snapshot when no slots are passed (filled slots are the only consumer).
- Skip `resolve_fills` when the `{% comp %}` tag has no body.
- Skip `normalize_slot_fills` when no slots are passed.
- Skip `context_processors_data` property access when no request is set.
- Inline the `component_error_message` context manager as a direct try/except.
- Drop the inner `snapshot_context` call (leftover from the removed flat-queue nested-render machinery).
- Dedupe `_get_parent_component_context` and `_get_component_name` lookups.

### Removed (public API)

- `Component.on_render()` overridable hook - the template is rendered directly.
- `ComponentVars` class and the `component_vars` context key. Check slot presence via `'name' in self.slots` in Python instead of `{% if component_vars.slots.name %}`.
- `prepare_component_template` / `_maybe_bind_template` helpers (internal, exported via `template.py`).

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

# Changelog

## 0.6.0

API alignment with Django conventions for class-based views and Forms.Media. Breaking.

### Breaking

- `template_file` is now `template_name`, matching Django's class-based view convention (`TemplateView.template_name`, etc.). The legacy `template_name` alias and the descriptor that proxied it onto `template_file` are gone.
- `js_file` and `css_file` are gone, replaced by a nested `Media` class matching Django's [Forms.Media](https://docs.djangoproject.com/en/stable/topics/forms/media/) convention. `Media.css` and `Media.js` are lists of paths; one `<link>` / `<script>` is prepended per entry. Single-file via list-of-one is the only form (no string convenience, no media-type dict).

```python
# Before
class Greeting(Component):
    template_file = "greeting.html"
    css_file = "greeting.css"
    js_file = "greeting.js"

# After
class Greeting(Component):
    template_name = "greeting.html"

    class Media:
        css = ["greeting.css"]
        js = ["greeting.js"]
```

- Removed the dead `js: str | None = None` inline-string attribute. It was declared on `Component` but never read anywhere. Inline JS was never supported; put it inside the template (or in a `Media.js` file).

### Removed (internal cleanup)

- `ComponentTemplateNameDescriptor` and the entire `ComponentMeta` metaclass. After dropping the legacy alias, the metaclass only existed to call `resolve_component_files` on class creation; that's now done in `__init_subclass__`.

## 0.5.2

Maintenance release. No API change. Bug fix + internal cleanup, with the docs site consolidated into the README so PyPI now ships the full reference.

### Fixed

- Stray trailing `'` in the "required slot not provided" error message in `SlotNode.render`.

### Removed (internal cleanup)

- Dead `_is_dynamic_component` lookup and its two guards in `SlotNode.render`. `DynamicComponent` was removed in 0.1.0a1; the attribute is never set on any current `Component` subclass, so the guards were unreachable.
- Brittle `ComponentNode.register(register)` / `ComponentScNode.register(register)` pre-registrations in `templatetags/component_tags.py` and the `component` / `componentsc` aliases. They would have crashed if ever invoked (`ComponentNode.parse` requires kwargs `Library.tag()` doesn't pass), but in practice were always overwritten by `ComponentRegistry._register_to_library` first.
- `ComponentScNode` class. The registry never used it; it calls `ComponentNode.parse` with the appropriate `start_tag` / `end_tag` kwargs directly.

### Docs

- Consolidate the mkdocs site (8 pages) into `README.md` + `CHANGELOG.md` at the repo root. Drop `mkdocs.yml`, `docs/`, the `docs` dep group in pyproject, and the gh-pages deploy workflow.
- Add a "How this compares" section to the README covering django-cotton, django-viewcomponent, slippers, JinjaX.

### Tests

- Add slot-heavy benchmark backends (`benchmarks/djc_lite_slots/`, `benchmarks/djc_slots/`) exercising `snapshot_context`, slot/fill machinery, and `{% extends %}` inheritance. The existing benches are props-only.
- Replace the placeholder `tests/test_settings.py` with five tests covering defaults, partial override merging, `ComponentsSettings` NamedTuple acceptance, lazy `dirs` resolution, and explicit empty values.

## 0.5.1

Production-readiness pass. No breaking changes.

### Fixed

- `ComponentRegistry.unregister()` now removes both the `comp` and `compc` tags from the Library (only `comp` was tracked, so `compc` leaked).
- `_extends_context_reset` now restores `extends_context` in a `finally` block, so a raised exception during fill extraction no longer leaks state across renders.
- Type-checker friendliness: `ComponentNode.end_tag` is annotated `ClassVar[str | None]` so subclasses (e.g. `ComponentScNode`) can set it to `None` without tripping mypy.
- `Slot._resolve_slot_context` no longer accepts an unused `component` parameter.
- `FillNode` validation now consistently raises `TemplateSyntaxError` (was `RuntimeError` for three checks).

### Removed (internal cleanup)

- Dropped `ComponentRegistry.__del__` and the `weakref.finalize` callback on the component class — both fragile or never firing in practice.
- Dropped ~250 LOC of dead helpers and unused branches: `template.load_component_template`, `_STRATEGY_CONTEXT_KEY` / `DJC_DEPS_STRATEGY`, the unused `_template` and `_signature` class attributes, `name_escape_re`, the `app_settings.Dynamic[T]` wrapper, and ten unused helpers in `util/misc.py` (`snake_to_pascal`, `is_nonempty_str`, `is_glob`, `flatten`, `to_dict`, `format_url`, `format_as_ascii_table`, `is_generator`, `convert_class_to_namedtuple`, `get_index`).
- `playwright` removed from dev dependencies; CI no longer installs Chromium.

### Performance

- `finders.py`: cache compiled regex patterns on the (immutable) settings tuple so `collectstatic` doesn't rebuild them per file.
- Tests: drop the per-test `gc.collect()` in `conftest.py`; suite runs ~7× faster (~3.4s → ~0.5s).

### Docs

- Trim docstrings and comments package-wide. Roughly 2300 lines removed (-43% LOC) by collapsing inherited multi-paragraph upstream docstrings to one or two sentences and dropping references to features that no longer exist in this fork.
- Quickstart: move `{% load component_tags %}` to the top of the template.
- Document `{% compc %}`, `{% html_attrs %}`, `format_attributes`, and `merge_attributes`.
- Ship `tests/` in the sdist so downstream packagers can run them.

## 0.5.0

Lean-out release. Roughly 870 LOC removed (~12% of the package).

### Breaking

- Removed the `tag_name` and `tag_name_sc` settings. The component tag names are now fixed at `{% comp %}` / `{% endcomp %}` / `{% compc %}` and cannot be configured.
- Removed the `multiline_tags` setting and its underlying monkeypatch of `django.template.base.tag_re`. Component tag invocations must now fit on a single line. If you need multi-line tag args, install the patch yourself in your app config:

```python
import re
from django.template import base
base.tag_re = re.compile(base.tag_re.pattern, re.DOTALL)
```

- Removed nested-tag-in-string-arg syntax. Calls like `{% comp "x" desc="{% lorem 3 w %}" / %}` are no longer supported. Workaround:

```django
{% lorem 3 w as desc %}
{% comp "x" desc=desc / %}
```

The custom template parser (`util/template_parser.py`, ~220 LOC) and the associated `compile_nodelist` monkeypatch are gone.

- Removed `RegistrySettings`. It was an empty `NamedTuple` reserved for future use; the `settings` parameter on `ComponentRegistry.__init__` is also gone.
- Removed `BaseNode.node_id` (and the `node_id` argument it accepted). It was only used for `__repr__` and a now-removed extension hook.
- Removed `BaseNode.template_component` (and `ComponentNode.template_component`). The field exposed the `Component` class that owned a tag's template, used only by user code via `Slot.fill_node.template_component` for introspection. Internal code never read it. Together with the supporting `Origin.component_cls` plumbing, the `cache_component_template_file` registry, and the `monkeypatch_template_init` patch, this was ~150 LOC of infrastructure for a niche, observation-only API.

### Removed (internal cleanup)

- `util/cache.py`: hand-rolled LRU cache, never imported anywhere.
- `util/nanoid.py` and `constants.py`: only used by `node_id`.
- The `monkeypatch_inclusion_node` patches that set `_DJC_INSIDE_INCLUSION_TAG`. The flag was set but never read after the JS/CSS dependency system was removed.
- The `monkeypatch_template_cls` patch and the entire `util/django_monkeypatch.py` module: only existed to support `template_component`. Django's `Template` class is no longer monkeypatched.
- Stale `PROTECTED_TAGS` entries (`component_css_dependencies`, `component_js_dependencies`).

## 0.4.1

### Fixed

- Component subclasses with `TYPE_CHECKING`-guarded forward-reference annotations on `get_context_data` no longer crash at class-creation time on Python 3.14. The positional-parameter introspection now reads `func.__code__` directly instead of going through `inspect.signature`, which on 3.14 eagerly evaluates `__annotate__` (PEP 649) and raises `NameError` for unresolved names. The fix is also version-agnostic and slightly faster.

## 0.4.0

### Added

- Positional tag arguments are now routed to named parameters on ``Component.get_context_data``. ``{% comp "form_input_label" "Email" "email" %}`` now binds cleanly to ``def get_context_data(self, label, for_)``. Mixed positional + keyword args follow Python function-call semantics: passing the same parameter both ways raises ``TypeError``, as does exceeding the declared positional count. Overrides that declare ``*args`` receive positional tag args natively. The base ``def get_context_data(self, **kwargs)`` is unchanged; positional args remain accessible via ``self.args``.

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

- `tag_name` and `tag_name_sc` settings to configure the component tag names. The end tag is always derived as `f"end{tag_name}"`. (Removed again in 0.5.0.)

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

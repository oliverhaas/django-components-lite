# Benchmarks

Renders a page with 3 different "components" (card, button, alert), each
repeated 1000 times, across four implementations:

- Plain `{% include %}`
- Django `@register.inclusion_tag`
- `django-components-lite` (this package)
- `django-components` (upstream, optional)

Each backend runs in its own subprocess so the two component libraries don't
clash on the `component_tags` template library name.

## Setup

```bash
uv sync --group benchmark
```

The `benchmark` group installs `django-components` (upstream). The other
backends only need what's already in the main dependencies.

## Run

```bash
python -m benchmarks.run
```

The orchestrator prints a comparison table (min / mean / max wall time per
render, plus a ratio against the fastest backend). A backend that fails to
start (e.g. upstream not installed) is skipped with a note on stderr.

To run a single backend directly:

```bash
python -m benchmarks.include.bench 5        # 5 repeats
python -m benchmarks.djc_lite.bench 5
```

## Notes

- The scenario is props-only: no slots, no children. `{% include %}` and
  inclusion tags have no slot equivalent, so including them would bias the
  comparison.
- All four backends produce the same HTML output. The per-render cost is
  dominated by template parsing/rendering for `3000` component invocations.
- Times include template rendering only, not the one-time Django setup or
  template compilation (compiled templates are cached by Django on first load,
  and we warm up before measuring).

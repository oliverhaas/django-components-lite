# Settings

Configure django-components-lite via the `COMPONENTS` setting in your Django settings:

```python
from django_components_lite import ComponentsSettings

COMPONENTS = ComponentsSettings(
    autodiscover=True,
    dirs=[BASE_DIR / "components"],
    app_dirs=["components"],
    multiline_tags=True,
    static_files_allowed=[".css", ".js"],
    static_files_forbidden=[".html", ".py"],
)
```

## Available settings

| Setting | Default | Description |
|---------|---------|-------------|
| `autodiscover` | `True` | Automatically discover components in app directories |
| `dirs` | `[BASE_DIR / "components"]` | Root-level directories to search for components |
| `app_dirs` | `["components"]` | Subdirectory name within apps to search for components |
| `multiline_tags` | `True` | Allow component tag arguments to span multiple lines |
| `tag_name` | `"comp"` | Name of the block-form component tag. End tag is always `f"end{tag_name}"`. |
| `tag_name_sc` | `f"{tag_name}c"` | Name of the self-closing component tag. |
| `static_files_allowed` | CSS, JS, images, fonts | File extensions served as static files |
| `static_files_forbidden` | `.html`, `.py`, etc. | File extensions never served as static files |

## Customizing tag names

The default component tag names are `{% comp %}` / `{% endcomp %}` / `{% compc %}`. Override them via `tag_name` and `tag_name_sc`:

```python
COMPONENTS = ComponentsSettings(
    tag_name="component",      # `{% component %}...{% endcomponent %}`
    tag_name_sc="componentsc", # `{% componentsc "x" / %}`
)
```

If you only set `tag_name`, `tag_name_sc` defaults to `f"{tag_name}c"`. The end tag is always derived as `f"end{tag_name}"` and cannot be set independently.

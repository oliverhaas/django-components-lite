# Settings

Configure django-components-lite via the `COMPONENTS` setting in your Django settings:

```python
from django_components_lite import ComponentsSettings

COMPONENTS = ComponentsSettings(
    autodiscover=True,
    dirs=[BASE_DIR / "components"],
    app_dirs=["components"],
    multiline_tags=True,
    reload_on_file_change=False,
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
| `reload_on_file_change` | `False` | Reload dev server when component files change |
| `static_files_allowed` | CSS, JS, images, fonts | File extensions served as static files |
| `static_files_forbidden` | `.html`, `.py`, etc. | File extensions never served as static files |

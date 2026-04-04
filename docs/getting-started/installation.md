# Installation

## Install the package

```bash
pip install django-components-lite
```

Or with uv:

```bash
uv add django-components-lite
```

## Add to Django settings

```python
INSTALLED_APPS = [
    # ...
    "django_components_lite",
]
```

## Configure templates

Add the component directories to your template loaders:

```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                        "django_components_lite.template_loader.Loader",
                    ],
                ),
            ],
        },
    },
]
```

## Configure component directories

By default, components are discovered in `components/` directories within each app and in a root-level `components/` directory.

You can customize this via settings:

```python
from django_components_lite import ComponentsSettings

COMPONENTS = ComponentsSettings(
    dirs=[BASE_DIR / "components"],
    app_dirs=["components"],
)
```

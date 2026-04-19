"""``django-components-lite`` backend."""

from __future__ import annotations

from pathlib import Path

import django
from django.conf import settings

BASE = Path(__file__).resolve().parent

settings.configure(
    BASE_DIR=BASE,
    INSTALLED_APPS=["django_components_lite"],
    TEMPLATES=[
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [BASE / "templates", BASE / "components"],
            "OPTIONS": {
                "builtins": ["django_components_lite.templatetags.component_tags"],
                "loaders": [
                    "django.template.loaders.filesystem.Loader",
                    "django.template.loaders.app_directories.Loader",
                    "django_components_lite.template_loader.Loader",
                ],
            },
        },
    ],
    COMPONENTS={"autodiscover": False},
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    SECRET_KEY="bench",
    USE_TZ=True,
)
django.setup()

from django.template.loader import get_template

from benchmarks._common import bench
from benchmarks.data import context
from benchmarks.djc_lite.components.alert import alert as _alert  # noqa: F401
from benchmarks.djc_lite.components.button import button as _button  # noqa: F401
from benchmarks.djc_lite.components.card import card as _card  # noqa: F401

template = get_template("page.html")


def run():
    template.render(context)


if __name__ == "__main__":
    bench(run, "django-components-lite")

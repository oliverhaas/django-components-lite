"""``django-components-lite`` backend, slot-heavy template that stresses ``snapshot_context``."""

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
from benchmarks.data import context_slots
from benchmarks.djc_lite_slots.components.card_slots import CardSlots as _CardSlots  # noqa: F401
from benchmarks.djc_lite_slots.components.panel import Panel as _Panel  # noqa: F401
from benchmarks.djc_lite_slots.components.row import Row as _Row  # noqa: F401

template = get_template("page_slots.html")


def run():
    template.render(context_slots)


if __name__ == "__main__":
    bench(run, "django-components-lite (slots)")

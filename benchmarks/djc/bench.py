"""Upstream ``django-components`` backend (optional; install via ``uv sync --group benchmark``)."""

from __future__ import annotations

from pathlib import Path

import django
from django.conf import settings

BASE = Path(__file__).resolve().parent

settings.configure(
    BASE_DIR=BASE,
    INSTALLED_APPS=["django_components"],
    TEMPLATES=[
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [BASE / "templates", BASE / "components"],
            "OPTIONS": {
                "builtins": ["django_components.templatetags.component_tags"],
                "loaders": [
                    "django.template.loaders.filesystem.Loader",
                    "django.template.loaders.app_directories.Loader",
                    "django_components.template_loader.Loader",
                ],
            },
        },
    ],
    COMPONENTS={"autodiscover": False},
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    SECRET_KEY="bench",
    USE_TZ=True,
    ROOT_URLCONF="benchmarks.urls",
)
django.setup()

from django.template.loader import get_template

from benchmarks._common import bench
from benchmarks.data import context
from benchmarks.djc.components.alert import alert as _alert  # noqa: F401
from benchmarks.djc.components.button import button as _button  # noqa: F401
from benchmarks.djc.components.card import card as _card  # noqa: F401

template = get_template("page.html")


def run():
    template.render(context)


if __name__ == "__main__":
    bench(run, "django-components")

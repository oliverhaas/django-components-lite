"""Plain ``{% include %}`` backend."""

from __future__ import annotations

from pathlib import Path

import django
from django.conf import settings

BASE = Path(__file__).resolve().parent

settings.configure(
    BASE_DIR=BASE,
    INSTALLED_APPS=[],
    TEMPLATES=[
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [BASE / "templates"],
            "OPTIONS": {},
        },
    ],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    SECRET_KEY="bench",
    USE_TZ=True,
)
django.setup()

from django.template.loader import get_template

from benchmarks._common import bench
from benchmarks.data import context

template = get_template("page.html")


def run():
    template.render(context)


if __name__ == "__main__":
    bench(run, "plain {% include %}")

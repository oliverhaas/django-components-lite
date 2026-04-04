"""Pytest configuration and fixtures for django-components-lite tests."""

import gc
from pathlib import Path
from unittest.mock import patch

import django
import pytest
from django.conf import settings
from django.core.cache import BaseCache, caches
from django.template import engines
from django.template.loaders.base import Loader


def pytest_configure(config):
    """Configure Django settings before any tests run."""
    if settings.configured:
        return

    settings.configure(
        BASE_DIR=Path(__file__).resolve().parent,
        INSTALLED_APPS=("django_components_lite", "tests.test_app"),
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [
                    "tests/templates/",
                    "tests/components/",
                ],
                "OPTIONS": {
                    "builtins": [
                        "django_components_lite.templatetags.component_tags",
                    ],
                    "loaders": [
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                        "django_components_lite.template_loader.Loader",
                    ],
                },
            },
        ],
        COMPONENTS={
            "autodiscover": False,
        },
        MIDDLEWARE=[],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            },
        },
        SECRET_KEY="secret",  # noqa: S106
        ROOT_URLCONF="tests.urls",
    )
    django.setup()


@pytest.fixture(autouse=True)
def _djc_isolation():
    """Isolate component state between tests.

    This fixture replaces the old @djc_test decorator. It:
    1. Snapshots global component/registry state before each test
    2. Mocks ID generation for deterministic output
    3. Mocks CSRF tokens
    4. Restores all state after each test
    """
    from django_components_lite.app_settings import app_settings
    from django_components_lite.component import ALL_COMPONENTS, component_node_subclasses_by_name
    from django_components_lite.component_registry import ALL_REGISTRIES
    from django_components_lite.template import _reset_component_template_file_cache, loading_components

    # --- Setup ---

    # Snapshot current state
    initial_components = list(ALL_COMPONENTS)
    initial_registries = [
        (reg_ref, list(reg_ref()._registry.keys())) for reg_ref in ALL_REGISTRIES if reg_ref() is not None
    ]

    # Deterministic ID generation
    id_count = 10599485

    def mock_gen_id(*_args, **_kwargs):
        nonlocal id_count
        id_count += 1
        return f"{id_count:x}"

    id_patcher = patch("django_components_lite.util.misc.generate", side_effect=mock_gen_id)
    csrf_patcher = patch("django.middleware.csrf.get_token", return_value="predictabletoken")

    # Start patchers and set testing flag
    from django.test.signals import setting_changed

    def on_setting_changed(*, setting, **kwargs):
        if setting in ("COMPONENTS", "BASE_DIR"):
            app_settings._load_settings()

    setting_changed.connect(on_setting_changed)
    id_patcher.start()
    csrf_patcher.start()
    app_settings._load_settings()

    yield

    # --- Teardown ---

    id_patcher.stop()
    csrf_patcher.stop()
    setting_changed.disconnect(on_setting_changed)

    # Clear template loader caches
    for engine in engines.all():
        for loader in engine.engine.template_loaders:
            if isinstance(loader, Loader):
                loader.reset()

    # Clear cached Node subclasses
    component_node_subclasses_by_name.clear()

    # Remove components added during test
    initial_set = set(initial_components)
    for i in range(len(ALL_COMPONENTS) - 1, -1, -1):
        ref = ALL_COMPONENTS[i]
        if ref() is None or ref not in initial_set:
            del ALL_COMPONENTS[i]

    # Remove registries added during test
    initial_reg_refs = {r for r, _ in initial_registries}
    for i in range(len(ALL_REGISTRIES) - 1, -1, -1):
        ref = ALL_REGISTRIES[i]
        if ref() is None or ref not in initial_reg_refs:
            del ALL_REGISTRIES[i]

    # Unregister components added during test from remaining registries
    for reg_ref, init_keys in initial_registries:
        registry = reg_ref()
        if not registry:
            continue
        initial_keys = set(init_keys)
        current_keys = set(registry._registry.keys())
        for key in current_keys - initial_keys:
            registry.unregister(key)

    # Clear component template cache and other state
    _reset_component_template_file_cache()
    loading_components.clear()

    # Clear Django caches
    all_caches: list[BaseCache] = list(caches.all())
    for cache in all_caches:
        cache.clear()

    gc.collect()
    app_settings._load_settings()

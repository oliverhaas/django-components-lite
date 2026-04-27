from pathlib import Path

from django.test import override_settings

from django_components_lite.app_settings import ComponentsSettings, app_settings, defaults


class TestSettings:
    def test_defaults_when_no_components_setting(self):
        with override_settings(COMPONENTS={}):
            app_settings._load_settings()
            assert app_settings.AUTODISCOVER is True
            assert list(app_settings.DIRS) == [Path(Path(__file__).parent.resolve()) / "components"]
            assert list(app_settings.APP_DIRS) == ["components"]
            assert defaults.static_files_allowed == app_settings.STATIC_FILES_ALLOWED
            assert defaults.static_files_forbidden == app_settings.STATIC_FILES_FORBIDDEN

    def test_partial_override_merges_with_defaults(self):
        with override_settings(COMPONENTS={"autodiscover": False, "app_dirs": ["my_comps"]}):
            app_settings._load_settings()
            assert app_settings.AUTODISCOVER is False
            assert list(app_settings.APP_DIRS) == ["my_comps"]
            # Untouched settings still get their defaults.
            assert defaults.static_files_allowed == app_settings.STATIC_FILES_ALLOWED

    def test_accepts_components_settings_namedtuple(self):
        with override_settings(COMPONENTS=ComponentsSettings(autodiscover=False)):
            app_settings._load_settings()
            assert app_settings.AUTODISCOVER is False

    def test_dirs_default_resolves_lazily_from_base_dir(self):
        # `dirs` default depends on `BASE_DIR`, so changing BASE_DIR after import
        # must still produce the right default.
        custom_base = Path(__file__).parent.resolve() / "test_app"
        with override_settings(COMPONENTS={}, BASE_DIR=custom_base):
            app_settings._load_settings()
            assert list(app_settings.DIRS) == [custom_base / "components"]

    def test_dirs_explicit_empty_list_disables_default(self):
        with override_settings(COMPONENTS={"dirs": []}):
            app_settings._load_settings()
            assert list(app_settings.DIRS) == []

from django_components_lite.app_settings import app_settings


class TestSettings:
    def test_settings_load(self):
        app_settings._load_settings()
        # Just verify settings loaded without error
        assert app_settings.AUTODISCOVER is not None

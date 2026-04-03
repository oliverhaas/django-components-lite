from django_components_lite.app_settings import app_settings
from django_components_lite.testing import djc_test

from .testutils import setup_test_config

setup_test_config()


@djc_test
class TestSettings:
    def test_settings_load(self):
        app_settings._load_settings()
        # Just verify settings loaded without error
        assert app_settings.AUTODISCOVER is not None

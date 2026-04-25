from django.apps import AppConfig


class ComponentsConfig(AppConfig):
    name = "django_components_lite"

    def ready(self) -> None:
        from django_components_lite.app_settings import app_settings
        from django_components_lite.autodiscovery import autodiscover

        if app_settings.AUTODISCOVER:
            autodiscover()

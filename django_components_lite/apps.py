import re

from django.apps import AppConfig
from django.template import Template
from django.template.library import InclusionNode


class ComponentsConfig(AppConfig):
    name = "django_components_lite"

    # This is the code that gets run when user adds django_components_lite
    # to Django's INSTALLED_APPS
    def ready(self) -> None:
        from django_components_lite.app_settings import app_settings
        from django_components_lite.autodiscovery import autodiscover
        from django_components_lite.util.django_monkeypatch import (
            monkeypatch_inclusion_node,
            monkeypatch_template_cls,
        )

        # NOTE: This monkeypatch is applied here, before Django processes any requests.
        #       To make django-components work with django-debug-toolbar-template-profiler
        #       See https://github.com/django-components/django-components/discussions/819
        monkeypatch_template_cls(Template)
        # Fixes https://github.com/django-components/django-components/pull/1390
        monkeypatch_inclusion_node(InclusionNode)

        if app_settings.AUTODISCOVER:
            autodiscover()

        # Allow tags to span multiple lines. This makes it easier to work with
        # components inside Django templates, allowing us syntax like:
        # ```html
        #   {% component "icon"
        #     icon='outline_chevron_down'
        #     size=16
        #     color="text-gray-400"
        #     attrs:class="ml-2"
        #   %}{% endcomponent %}
        # ```
        #
        # See https://stackoverflow.com/a/54206609/9788634
        if app_settings.MULTILINE_TAGS:
            from django.template import base

            base.tag_re = re.compile(base.tag_re.pattern, re.DOTALL)

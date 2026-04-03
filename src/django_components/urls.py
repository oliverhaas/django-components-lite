from django.urls import include, path

from django_components.dependencies import urlpatterns as dependencies_urlpatterns

urlpatterns = [
    path(
        "components/",
        include(
            [
                *dependencies_urlpatterns,
            ],
        ),
    ),
]

__all__ = ["urlpatterns"]

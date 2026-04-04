from django.urls import path

from myproject.views import index

urlpatterns = [
    path("", index),
]

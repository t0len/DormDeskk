from django.urls import path

from apps.passes.views import (
    PassCancelView,
    PassCreateView,
    PassDetailView,
    PassListView,
    SecurityTodayPassesView,
)

app_name = "passes"

urlpatterns = [
    path("", PassListView.as_view(), name="list"),
    path("create/", PassCreateView.as_view(), name="create"),
    path("<int:pk>/", PassDetailView.as_view(), name="detail"),
    path("<int:pk>/cancel/", PassCancelView.as_view(), name="cancel"),
    path("today/", SecurityTodayPassesView.as_view(), name="today"),
]

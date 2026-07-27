from django.urls import path

from apps.web.views import DashboardView

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
]

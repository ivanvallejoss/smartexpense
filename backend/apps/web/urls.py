from django.urls import path

from apps.web.views import DashboardExpensesView, DashboardView

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("gastos/", DashboardExpensesView.as_view(), name="dashboard-gastos"),
]

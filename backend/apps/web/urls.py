from django.urls import path

from apps.web.views import (
    DashboardDeleteExpenseView,
    DashboardExpensesView,
    DashboardResultsView,
    DashboardView,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("gastos/", DashboardExpensesView.as_view(), name="dashboard-gastos"),
    path("resultados/", DashboardResultsView.as_view(), name="dashboard-resultados"),
    path(
        "gastos/<int:expense_id>/eliminar/",
        DashboardDeleteExpenseView.as_view(),
        name="dashboard-gasto-eliminar",
    ),
]

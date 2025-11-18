"""
API URL Configuration
"""
from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ExpenseViewSet

# Router de DRF para viewset
router = DefaultRouter()
router.register(r"expenses", ExpenseViewSet, basename="expense")
router.register(r"categories", CategoryViewSet, basename="category")

urlpatterns = [
    path("", include(router.urls)),
]

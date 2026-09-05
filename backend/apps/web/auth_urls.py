"""
Rutas de acceso, a nivel raiz y no bajo /dashboard/.

Entrar no es una vista del dashboard: se visita sin sesion, que es exactamente
lo que el prefijo del dashboard no admite. Colgarlas ahi obligaria a exceptuar
esas dos rutas del guard de sesion de apps/web/views.py.
"""
from django.urls import path

from apps.web.auth_views import EntrarView, PedirAccesoView

urlpatterns = [
    path("entrar/<str:token>/", EntrarView.as_view(), name="entrar"),
    path("pedir-acceso/", PedirAccesoView.as_view(), name="pedir-acceso"),
]

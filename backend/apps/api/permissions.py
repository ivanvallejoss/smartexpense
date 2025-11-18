"""
Custom permissions para la API de SmartExpense.
"""
from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Permission que solo permite a los usuarios acceder a sus propios objetos.

    Funciona con cualquier modelo que tenga un campo 'user'.
    """

    message = "No tienes permiso para acceder a este recurso."

    def has_object_permission(self, request, view, obj):
        """
        Verificar que el objeto pertenezca al usuario actual.
        """
        # Si el objeto tiene un campo 'user', verificar que sea el owner
        if hasattr(obj, "user"):
            return obj.user == request.user

        # Si no tiene campo 'user', denegar acceso
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission que permite lectura a todos, pero solo el owner puede modificar.
    """

    def has_object_permission(self, request, view, obj):
        # Permitir GET, HEAD, OPTIONS a todos
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions solo para el owner
        if hasattr(obj, "user"):
            return obj.user == request.user

        return False

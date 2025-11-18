"""
Views para la API REST de SmartExpense.
"""
from datetime import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Count, Q, Sum

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import Category, DeletedObject, Expense

from .permissions import IsOwner
from .serializers import CategorySerializer, ExpenseCreateUpdateSerializer, ExpenseSerializer, ExpenseStatsSerializer


class ExpenseViewSet(viewsets.ModelViewSet):
    """
    ViewSet para manejar CRUD completo de Expenses.

    Endpoints:
    - GET /api/expenses/ - Listar expenses del usuario (con filtros)
    - POST /api/expenses/ - Crear nuevo expense
    - GET /api/expenses/{id}/ - Obtener detalle de un expense
    - PATCH /api/expenses/{id}/ - Actualizar expense parcialmente
    - PUT /api/expenses/{id}/ - Actualizar expense completamente
    - DELETE /api/expenses/{id}/ - Eliminar expense (soft delete)
    - GET /api/expenses/stats/ - Obtener estadísticas de gastos

    Filtros disponibles (query params):
    - date_from: Fecha inicio (YYYY-MM-DD)
    - date_to: Fecha fin (YYYY-MM-DD)
    - category_id: ID de categoría
    """

    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        """
        Retorna expenses del usuario actual con filtros opcionales.
        """
        user = self.request.user
        queryset = Expense.objects.filter(user=user).select_related("category", "user")

        # Aplicar filtros
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        category_id = self.request.query_params.get("category_id")

        if date_from:
            try:
                date_from_parsed = datetime.strptime(date_from, "%Y-%m-%d")
                queryset = queryset.filter(date__gte=date_from_parsed)
            except ValueError:
                pass  # Ignorar formato inválido

        if date_to:
            try:
                date_to_parsed = datetime.strptime(date_to, "%Y-%m-%d")
                # Incluir todo el día hasta las 23:59:59
                date_to_parsed = date_to_parsed.replace(hour=23, minute=59, second=59)
                queryset = queryset.filter(date__lte=date_to_parsed)
            except ValueError:
                pass

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        return queryset

    def get_serializer_class(self):
        """
        Usar diferentes serializers para read vs write.
        """
        if self.action in ["create", "update", "partial_update"]:
            return ExpenseCreateUpdateSerializer
        return ExpenseSerializer

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete: mueve el expense a DeletedObject en lugar de eliminarlo.
        """
        instance = self.get_object()

        # Crear snapshot del objeto
        snapshot = {
            "id": instance.id,
            "user_id": instance.user.id,
            "user_username": instance.user.username,
            "amount": str(instance.amount),
            "description": instance.description,
            "category_id": instance.category.id if instance.category else None,
            "category_name": instance.category.name if instance.category else None,
            "date": instance.date.isoformat(),
            "raw_message": instance.raw_message,
            "created_at": instance.created_at.isoformat(),
        }

        # Guardar en DeletedObject
        DeletedObject.objects.create(
            content_type=ContentType.objects.get_for_model(Expense),
            object_id=instance.id,
            object_data=snapshot,
            deleted_by=request.user,
            reason=request.data.get("reason", ""),
        )

        # Eliminar el objeto original
        instance.delete()

        return Response(
            {"detail": "Expense eliminado. Se guardó en papelera por 30 días."},
            status=status.HTTP_204_NO_CONTENT,
        )

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        Endpoint para estadísticas de gastos.

        GET /api/expenses/stats/?date_from=2024-01-01&date_to=2024-12-31

        Retorna:
        - total_amount: Suma total de gastos
        - expense_count: Cantidad de gastos
        - average_per_day: Promedio diario
        - by_category: Lista de totales por categoría
        - date_range: Rango de fechas usado
        """
        queryset = self.get_queryset()

        # Calcular totales
        aggregation = queryset.aggregate(total=Sum("amount"), count=Count("id"), average=Avg("amount"))

        total_amount = aggregation["total"] or Decimal("0.00")
        expense_count = aggregation["count"] or 0

        # Calcular promedio por día
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if date_from and date_to:
            try:
                start = datetime.strptime(date_from, "%Y-%m-%d")
                end = datetime.strptime(date_to, "%Y-%m-%d")
                days = (end - start).days + 1
            except ValueError:
                days = 1
        else:
            # Si no hay rango, usar el rango real de los gastos
            dates = queryset.values_list("date", flat=True)
            if dates:
                start = min(dates)
                end = max(dates)
                days = (end - start).days + 1
            else:
                days = 1

        average_per_day = total_amount / days if days > 0 else Decimal("0.00")

        # Totales por categoría
        by_category = queryset.values("category__name").annotate(total=Sum("amount"), count=Count("id")).order_by("-total")
        # Formatear by_category
        category_stats = []
        for item in by_category:
            category_stats.append(
                {
                    "category_name": item["category__name"] or "Sin categoría",
                    "total": item["total"],
                    "count": item["count"],
                }
            )

        # Preparar respuesta
        stats_data = {
            "total_amount": total_amount,
            "expense_count": expense_count,
            "average_per_day": round(average_per_day, 2),
            "by_category": category_stats,
            "date_range": {"start": date_from, "end": date_to},
        }

        serializer = ExpenseStatsSerializer(stats_data)
        return Response(serializer.data)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet para manejar CRUD completo de Categories.

    Endpoints:
    - GET /api/categories/ - Listar categorías del usuario + globales
    - POST /api/categories/ - Crear nueva categoría
    - GET /api/categories/{id}/ - Obtener detalle de una categoría
    - PATCH /api/categories/{id}/ - Actualizar categoría parcialmente
    - PUT /api/categories/{id}/ - Actualizar categoría completamente
    - DELETE /api/categories/{id}/ - Eliminar categoría (solo si no tiene expenses)
    """

    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        """
        Retorna categorías del usuario actual + categorías globales.
        """
        user = self.request.user
        return Category.objects.filter(Q(user=user) | Q(is_default=True)).prefetch_related("expenses")

    def destroy(self, request, *args, **kwargs):
        """
        Eliminar categoría solo si NO tiene expenses asociados.
        """
        instance = self.get_object()

        # Verificar si tiene expenses
        expense_count = instance.expenses.count()
        if expense_count > 0:
            return Response(
                {"detail": f"No puedes eliminar esta categoría porque tiene {expense_count} gasto(s) asociado(s)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Si no tiene categorías globales no se pueden eliminar
        if instance.is_default:
            return Response(
                {"detail": "No puedes eliminar una categoría global."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Verificar que sea del usuario
        if instance.user != request.user:
            return Response(
                {"detail": "No tienes permiso para eliminar esta categoría."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Soft delete (igual que expenses)
        snapshot = {
            "id": instance.id,
            "name": instance.name,
            "user_id": instance.user.id if instance.user else None,
            "keywords": instance.keywords,
            "color": instance.color,
            "created_at": instance.created_at.isoformat(),
        }

        DeletedObject.objects.create(
            content_type=ContentType.objects.get_for_model(Category),
            object_id=instance.id,
            object_data=snapshot,
            deleted_by=request.user,
            reason=request.data.get("reason", ""),
        )

        instance.delete()

        return Response(
            {"detail": "Categoría eliminada. Se guardó en papelera por 30 días."},
            status=status.HTTP_204_NO_CONTENT,
        )

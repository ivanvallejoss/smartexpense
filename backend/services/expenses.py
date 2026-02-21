"""
Service Layer
Logic that creates or deletes expenses
"""

from apps.core.models import Expense
from asgiref.sync import sync_to_async
from django.db import transaction
from django.utils import timezone
from typing import Optional

@sync_to_async
def create_expense(user, amount, description, category, raw_message, date=None):
    """Helper sincrónico para crear expense con categoría."""
    if not date:
        date = timezone.now()

    with transaction.atomic():
        expense = Expense.objects.create(
            user=user,
            amount=amount,
            description=description,
            category=category,
            date=date,
            raw_message=raw_message,
        )
    return expense


@sync_to_async
def delete_expense(expense_id, user_telegram_id):
    try:
        # Get the expense_id object that match with the user_id
        expense = Expense.objects.get(id=expense_id, user__telegram_id=user_telegram_id)
        # Delete the expense
        expense.delete()
        return True
    except Expense.DoesNotExist:
        return False

@sync_to_async
def get_filtered_expenses(
    telegram_id: int,
    limit: int=15,
    offset: int=0,
    month: Optional[int] = None,
    year: Optional[int] = None
):
    """
    Obtiene gastos con soporte para paginacion y filtros por fecha.
    """
    # Join con category
    qs = Expense.objects.filter(
        user__telegram_id=telegram_id
    ).select_related(category)

    if month:
        qs = qs.filter(date__month=month)
    if year:
        qs = qs.filter(date__year=year)
    
    # offset=10, limit=10 -> qs[10:20] (Pagina 2)
    qs = qs.order_by('-date')[offset : offset + limit]

    # Forzamos el calculo para evitar error de sincronia
    return list(qs)
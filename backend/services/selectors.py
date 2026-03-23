"""
Service Layer
Logic to show data related to expenses
"""

from apps.core.models import Expense, Category
from django.core.exceptions import ObjectDoesNotExist

from services.constants import SPANISH_MONTHS

from asgiref.sync import sync_to_async

from django.utils import timezone

from django.db.models import Count, Sum, Q
from decimal import Decimal
from typing import Optional

from zoneinfo import ZoneInfo

# ---------------------------------------
#           EXPENSES
# ---------------------------------------

@sync_to_async
def get_expenses(
    user, 
    limit:int=7,
    offset:int=0,
    month:Optional[int]=None,
    year:Optional[int]=None
    ):
    """
    Gets a LIST of expenses for a user
    """
    expenses = Expense.objects.filter(
        user=user,
        status=Expense.STATUS_CONFIRMED
        ).select_related('category')

    if month:
        expenses = expenses.filter(date__month=month)
    if year:
        expenses = expenses.filter(date__year=year)
    
    # filtering by offset & limit
    expenses = expenses.order_by('-date')[offset: offset + limit]
    
    # We need to return a list so we force Django to evaluate the queryset
    # Otherwise we can get an error for SychronousOnlyOperation
    return list(expenses)


@sync_to_async
def get_single_expense(
    user,
    expense_id: int,
):
    """
    Get a single expense + select_related to Category
    """
    try:
        expense = Expense.objects.get(
            user=user, id=expense_id
        )
        return expense
    except Expense.DoesNotExist:
        raise ObjectDoesNotExist(
            f"The expense ID: {expense_id} does not belong to any of your expenses."
            )


@sync_to_async
def get_balance(user, month: int=None, year: int=None) -> float:
    """
    Getting the balance of the user.
    It filters by month or year if applied.
    """
    expenses = Expense.objects.filter(user=user, status=Expense.STATUS_CONFIRMED)
    
    if month:
        expenses = expenses.filter(date__month=month)
    if year:
        expenses = expenses.filter(date__year=year)

    resultado = expenses.aggregate(total_spent=Sum('amount'))

    # Devolvemos la propiedad especifica del diccionario
    # o 0.0 si no hay nada
    return resultado['total_spent'] or 0.0


# ---------------------------------------
#               STATS
# ---------------------------------------

@sync_to_async
def get_month_stats(user):
    """
    Function that returns last month expenses.
    """

    user_tz = ZoneInfo("America/Argentina/Buenos_Aires")
    now = timezone.now()
    # We convert the timezone to Buenos Aires to get the correct month start for the User
    local_now = now.astimezone(user_tz)
    local_month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # it used the server timezone
    expenses = Expense.objects.filter(
        user=user, 
        status=Expense.STATUS_CONFIRMED,
        date__gte=local_month_start, 
        date__lte=now
        )

    total_amount = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_count = expenses.count()

    by_category = list(
        expenses.values("category__name", "category__color")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
        )
    
    # We use the local month name
    local_month_name = local_now.strftime("%B %Y")
    local_month_name = f"{SPANISH_MONTHS[local_now.month]} {local_now.year}"

    return {
        "total_amount": total_amount, 
        "total_count": total_count, 
        "by_category": by_category, 
        "month_name": local_month_name}


# -------------------------------------
#              CATEGORY
# -------------------------------------

def get_category_by_id(category_id):
    """
    Obtiene una categoria por su ID.
    """
    try:
        return Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        raise ObjectDoesNotExist(
            f"La categoria con id {category_id} no existe."
            )


@sync_to_async
def get_user_categories_or_defaults(user):
    """
    Retorna todas las categorías disponibles para un usuario:
    sus propias categorías + las globales del sistema.
    """
    categories = list(
        Category.objects.filter(
            Q(user=user) | Q(is_default=True)
        ).order_by('name')
    )
    return categories

@sync_to_async
def get_category_by_id_or_default(user, category_id):
    """
    Busca la categoria por su ID.
    Filtra por si le pertenece al usuario o si es default del sistema.
    """
    try:
        return Category.objects.get(
            Q(id=category_id, user=user) | Q(id=category_id, is_default=True)
            )
    except Category.DoesNotExist:
        raise ObjectDoesNotExist(
            f"The ID category: {category_id} does not belong to any known category or it belongs to another user"
        )
"""
Service Layer
Logic to show data related to expenses
"""

from apps.core.models import Expense, Category
from django.core.exceptions import ObjectDoesNotExist

from asgiref.sync import sync_to_async

from django.utils import timezone
from django.db.models import Count, Sum
from decimal import Decimal
from typing import Optional

from zoneinfo import ZoneInfo



@sync_to_async
def get_expenses(
    user, 
    limit:int=7,
    offset:int=0,
    month:Optional[int]=None,
    year:Optional[int]=None
    ):
    """
    Gets the last n expenses for a user.
    """
    expenses = Expense.objects.filter(
        user=user,
        status=Expense.STATUS_CONFIRMED
        ).select_related('category')

    if month:
        expenses = expenses.filter(date__month=month)
    if year:
        expenses = expenses.filter(date__year=year)
    
    # Implementing the offset and limit
    expenses = expenses.order_by('-date')[offset: offset + limit]
    
    # We need to return a list so we force Django to evaluate the queryset
    # Otherwise we can get an error for SychronousOnlyOperation
    return list(expenses)



@sync_to_async
def get_balance(user, month: int=None, year: int=None) -> float:
    """
    Calcula la suma total de gastos delegando el calculo a la BBDD
    """
    expenses = Expense.objects.filter(user=user, status=STATUS_CONFIRMED)
    # Aplicamos filtros opcionales si el frontend quiere el total de un mes especifico
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

    # We dont need to get the exact timezone of the user for this query
    # So, we use the timezone of the server for accuracy
    expenses = Expense.objects.filter(
        user=user, 
        status=STATUS_CONFIRMED,
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

    return {
        "total_amount": total_amount, 
        "total_count": total_count, 
        "by_category": by_category, 
        "month_name": local_month_name}


# Still needs to figured it out how to implement this
# Not sure how to handle yet
@sync_to_async
def get_week_stats(user):
    """
    Helper async to get week stats.
    We calculate the week start for the user timezone and get the expenses for that week.
    """
    from datetime import timedelta
    
    now = timezone.now()
    user_tz = ZoneInfo("America/Argentina/Buenos_Aires")
    local_now = now.astimezone(user_tz)

    # We calculate the day of the week the user is rn
    days_to_calculate = local_now.weekday()
    # Calculating the start of the week from the current day
    week_start = local_now - timedelta(days=days_to_calculate)

    # So the query gets the expenses from the monday of this week to now
    expenses = Expense.objects.filter(
        user=user, 
        status=STATUS_CONFIRMED,
        date__gte=week_start, 
        date__lte=now
        )

    total_amount = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_count = expenses.count()

    by_category = list(expenses
    .values("category__name", "category__color")
    .annotate(total=Sum("amount"), count=Count("id"))
    .order_by("-total"))

    return {
        "total_amount": total_amount, 
        "total_count": total_count, 
        "by_category": by_category, 
        # Returned the start of the week for the user
        "start_date": week_start.strftime("%d/%m")
        }


# -------------------------------------
#              CATEGORY
# -------------------------------------
#
def get_category_by_id(category_id):
    """
    Obtiene una categoria por su ID.
    """
    try:
        return Category.objects.get(id=category_id)
    except ObjectDoesNotExist:
        raise ObjectDoesNotExist(f"La categoria con id {category_id} no existe.")
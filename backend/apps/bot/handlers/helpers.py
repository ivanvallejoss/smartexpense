"""
Helpers for handlers
En este momento solo estan los helpers del handler /stats pero planeo tener una separacion mas clara a medida que crezcan los handlers
"""
from decimal import Decimal
from django.db.models import Count, Sum
from django.utils import timezone
from asgiref.sync import sync_to_async
from apps.core.models import Expense
from zoneinfo import ZoneInfo


# Helper async para queries de DB
@sync_to_async
def get_month_stats(user):
    """Helper async to get month stats."""

    user_tz = ZoneInfo("America/Argentina/Buenos_Aires")
    now = timezone.now()
    # We convert the timezone to Buenos Aires to get the correct month start for the User
    local_now = now.astimezone(user_tz)
    local_month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # We dont need to get the exact timezone of the user for this query
    # So, we use the timezone of the server for accuracy
    expenses = Expense.objects.filter(
        user=user, 
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
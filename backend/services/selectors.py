"""
Service Layer
Logic to show data related to expenses
"""

from apps.core import Expense
from asgiref import sync_to_async

@sync_to_async
def get_lasts_expenses(telegram_id, limit=5):
    """
    Gets the last n expenses for a user.
    """
    expenses = Expense.objects.filter(
        user__telegram_id=telegram_id
        ).select_related('category').order_by('-date')[:limit]
    
    # We need to return a list so we force Django to evaluate the queryset
    # Otherwise we can get an error for SychronousOnlyOperation
    return list(expenses)
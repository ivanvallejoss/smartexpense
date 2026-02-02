"""
Function to create the expense object.
ATOMIC: True
Data: Not sure how to implement this but -for now- if not date is provided, it will use the current time.
Later I'll do something so it can be uploaded past dates.
"""

from apps.core.models import Expense
from asgiref.sync import sync_to_async
from django.db import transaction
from django.utils import timezone

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
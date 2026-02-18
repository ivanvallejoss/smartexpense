"""
Service Layer
Logic that creates or deletes expenses
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
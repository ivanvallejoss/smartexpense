"""
Function to create the expense object.
ATOMIC: True
"""

from apps.core.models import Expense
from asgiref.sync import sync_to_async
from django.db import transaction

@sync_to_async
def create_expense(user, amount, description, category, raw_message, date):
    """Helper sincrónico para crear expense con categoría."""
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
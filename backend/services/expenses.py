"""
Service Layer
Logic that creates or deletes expenses
"""

from apps.core.models import Expense, Category
from asgiref.sync import sync_to_async
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from typing import Optional

@sync_to_async
def create_expense(user, amount:float, description:string, category_id:int, date=None, raw_message=None):
    """Helper sincrónico para crear expense con categoría."""
    if not date:
        date = timezone.now()
    
    # I will keep like this just for now,
    # not sure how to fix this for the web cases.
    if not raw_message:
        raw_message = description

    # This line should be modify if 
    # we add a functionality 
    # to create personalized categories
    category = Category.objects.get(id=category_id)

    with transaction.atomic():
        expense = Expense.objects.create(
            user=user,
            amount=amount,
            description=description,
            category=category,
            date=date,
            raw_message=raw_message
        )
    return expense



@sync_to_async
def update_expense(user, expense_id: int, amount: float, description: str, category_id: int):
    """
    Actualiza un gasto asegurado que le pertenezca al usuario.
    """
    # This line should be modify if 
    # we add a functionality 
    # to create personalized categories
    category = Category.objects.get(id=category_id)
    
    filas_actualizadas = Expense.objects.filter(id=expense_id, user=user).update(
        amount=amount,
        description=description,
        category=category
    )

    if filas_actualizadas == 0:
        raise ObjectDoesNotExist("El gasto no existe o no tienes permisos.")
    
    expense = Expense.objects.select_related('category').get(id=expense_id, user=user)

    return expense



@sync_to_async
def delete_expense(user, expense_id):
    """
    Elimina la expense, cruzando user con expense 
    """
    filas_borradas, _ = Expense.objects.filter(id=expense_id, user=user).delete()
    
    if filas_borradas == 0:
        raise ObjectDoesNotExist("El gasto que intentas borrar no existe o no te pertenece.")

    return True


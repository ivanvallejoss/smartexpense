"""
Service Layer
Logic that creates or deletes expenses
"""

from apps.core.models import Expense, Category, DeletedObject
from .selectors import get_category_by_id

from services.ml.categorizer import ExpenseCategorizer

from asgiref.sync import sync_to_async
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from datetime import datetime

from decimal import Decimal
from typing import Optional

@sync_to_async
def create_expense(
    user, 
    amount:float, 
    description:str, 
    category=None, 
    date=None, 
    raw_message=None,
    status=None
    ):
    """
    Create a new Expense for the user.
    """
    if not date:
        date = timezone.now()
    if not raw_message:
        raw_message = description
    if not status:
        status = Expense.STATUS_CONFIRMED
    
    with transaction.atomic():
        expense = Expense.objects.create(
            user=user,
            amount=amount,
            description=description,
            category=category,
            date=date,
            raw_message=raw_message,
            status=status,
        )
    return expense



@sync_to_async
def update_expense(
    user,
    expense, 
    amount: float, 
    description: str, 
    category=None
    ):
    """
    Update the user's expense.
    If previous_category is not None, it means we have to register the change with the ML object.
    """
    with transaction.atomic():    
        previous_category = expense.category
        
        expense.amount = amount
        expense.description = description
        expense.category = category
        # realizamos la actualizacion solo en las columnas necesarias
        expense.save(update_fields=['amount', 'description', 'category', 'updated_at'])

        # Reportamos a ML si nueva_categoria != previous_categoria para alimentarlo
        if previous_category != category:
            categorizer = ExpenseCategorizer(user)
            categorizer.record_feedback(
                expense=expense,
                suggested_category=previous_category,
                accepted=False,
                final_category=category,
            )

    return expense



@sync_to_async
def delete_expense(user, expense_id):
    """
    Soft-delete the expense
    Sends the expense to DeletedObject (as a JSON) table 
    and Hard Delete the expense from the original table
    return:
        object_id -> with this ID we can restore the delete
    """
    with transaction.atomic():
        try:
            expense = Expense.objects.get(id=expense_id, user=user)
        except Expense.DoesNotExist:
            raise ObjectDoesNotExist("El gasto que intentas borrar no existe")

        # Serializamos los datos para guardarlos en el JSONfield
        category = expense.category.id if expense.category else None
        expense_data = {
            "amount": str(expense.amount),
            "description": expense.description,
            "category": category,
            "date": expense.date.isoformat(),
            "raw_message": expense.raw_message
        }

        # Creamos el registro en la papelera usando GenericForeignKey
        content_type = ContentType.objects.get_for_model(Expense)
        deleted_obj = DeletedObject.objects.create(
            content_type=content_type,
            object_id=expense.id,
            object_data=expense_data,
            deleted_by=user,
            reason="Eliminado por el usuario via bot/web"
        )

        # Hard delete
        expense.delete()

        return deleted_obj.id

@sync_to_async
def restore_expense(user, deleted_object_id: int):
    """
    Restore an expense from being deleted
    Sends the expense from DeletedObject to the expense table
    """
    with transaction.atomic():
        try:
            deleted_obj = DeletedObject.objects.get(id=deleted_object_id, deleted_by=user)
        except DeletedObject.DoesNotExist:
            raise ObjectDoesNotExist("El registro en la papelera ya no existe, expiro o no te pertenece")

        # Extraccion del JSON
        data = deleted_obj.object_data

        # Verificamos si el category que se guardo es un id o un null.
        # obtenemos el objeto si es un id
        if isinstance(data["category"], int):
            category = get_category_by_id(data["category"])
        else:
            category = None

        expense = Expense.objects.create(
            user=user,
            amount=Decimal(data["amount"]),
            description=data["description"],
            category=category,
            date=datetime.fromisoformat(data["date"]),
            raw_message=data["raw_message"],
        )

        # Hard delete
        deleted_obj.delete()

        return expense


"""
Service Layer
Logic that creates or deletes expenses
"""

from apps.core.models import Expense, Category, DeletedObject
from .selectors import get_category_by_id

from asgiref.sync import sync_to_async
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from decimal import Decimal
from typing import Optional

@sync_to_async
def create_expense(user, amount:float, description:str, category_id:int, date=None, raw_message=None):
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
    category = get_category_by_id(category_id=category_id)
    
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
    Realiza un soft-delete de la expense.
    Eliminamos la expense de la tabla original y lo mandamos a la papelera (DeletedObject).
    return:
        object_id -> permite deshacer la eliminacion del objeto
    """
    with transaction.atomic():
        # 1. Buscar el registro en la tabla de gastos
        try:
            expense = Expense.objects.get(id=expense_id, user=user)
        except Expense.DoesNotExist:
            raise ObjectDoesNotExist("El gasto que intentas borrar no existe")

        # 2. Serializamos los datos para guardarlos en el JSONfield
        expense_data = {
            "amount": str(expense.amount),
            "description": expense.description,
            "category_id": expense.category_id,
            "date": expense.date.isoformat(),
            "raw_message": expense.raw_message
        }

        # 3. Creamos el registro en la papeleara usando GenericForeignKey
        content_type = ContentType.objects.get_for_model(Expense)
        deleted_obj = DeletedObject.objects.create(
            content_type=content_type,
            object_id=expense.id,
            object_data=expense_data,
            deleted_by=user,
            reason="Eliminado por el usuario via bot/web"
        )

        # 4.Hard Delete en la tabla original
        expense.delete()

        return deleted_obj.id

@sync_to_async
def restore_expense(user, deleted_object_id: int):
    """
    Restaura un gasto desde la papelera a la tabla original.
    """
    with transaction.atomic():
        # Buscamos el registro en la papelera
        try:
            deleted_obj = DeletedObject.objects.get(id=deleted_object_id, deleted_by=user)
        except DeletedObject.DoesNotExist:
            raise ObjectDoesNotExist("El registro en la papelera ya no existe, expiro o no te pertenece")

        # Extraccion del JSON
        data = deleted_obj.object_data
        # Obtenemos la categoria a la que apunta
        category_id = int(data["category_id"])
        category = get_category_by_id(category_id=category_id)

        # 2. Re-creacion del gasto original
        expense = Expense.objects.create(
            user=user,
            amount=Decimal(data["amount"]),
            description=data["description"],
            category=category,
            date=timezone.datetime.fromisoformat(data["date"]),
            raw_message=data["raw_message"],
        )

        # 3. Eliminamos el registro de la papelera para no tener duplicados
        deleted_obj.delete()

        return expense


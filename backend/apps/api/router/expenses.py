from ninja import Router, Query
from typing import List, Optional

from django.db.models import Q

from apps.core.models import Expense, Category
from apps.api.schemas import ExpenseOut, ExpenseIn

from services.expenses import create_expense, delete_expense, update_expense
from services.selectors import get_expenses, get_single_expense, get_category_by_id_or_default

# Enrutador especifico para gastos
router = Router(tags=["Gastos"])

#  Ninja automaticamente toma la lista de objetos de Django y los pase por el molde de ExpenseOut
@router.get("/", response=List[ExpenseOut])
async def list_expenses(
    request, 
    limit: int = Query(default=15, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    year: Optional[int] = Query(default=None, ge=2025, le=2100),
    ):
    """
    Lista los gastos del usuario autenticado.
    Soporta paginacion (?limiti=15&offset=0) y filtros por fecha (?month=2&year=2026)
    """
    user = request.auth
    
    expenses = await get_expenses(
        user=user,
        limit=limit,
        offset=offset,
        month=month,
        year=year
        )
    
    return expenses



@router.post("/", response={201: ExpenseOut})
async def create_expense_endpoint(request, payload: ExpenseIn):
    """
    Crea un nuevo gasto.
    Espera un JSON con amount, description y category_id
    """
    user = request.auth
    category = await get_category_by_id_or_default(user=user, category_id=payload.category_id)

    expense = await create_expense(
        user=user,
        amount=payload.amount,
        description=payload.description,
        category=category
    )
    return expense


@router.put("/{expense_id}/", response=ExpenseOut)
async def update_expense_endpoint(request, expense_id: int, payload: ExpenseIn):
    """
    Edita un gasto existente.
    La URL debe contener el ID del gasto (ej: /api/expenses/6)
    """
    user = request.auth

    # Enviamos la expense actual completa al servcicio update
    current_expense = await get_single_expense(user=user, expense_id=expense_id)
    new_category = await get_category_by_id_or_default(user=user, category_id=payload.category_id)

    expense = await update_expense(
        user=user,
        expense=current_expense,
        amount=payload.amount,
        description=payload.description,
        category=new_category
    )
    return expense




@router.delete("/{expense_id}/", response={204: None})
async def delete_expense_endpoint(request, expense_id: int):
    """
    Borra un gasto de forma permanente
    """
    user = request.auth

    await delete_expense(
        user=user,
        expense_id=expense_id
    )
    return None
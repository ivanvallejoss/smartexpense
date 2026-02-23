from ninja import Router
from typing import List, Optional
from apps.api.schemas import ExpenseOut, ExpenseIn
from services.selectors import get_lasts_expenses
from services.expenses import create_expense
from services.users import get_user_by_telegram_id

# Enrutador especifico para gastos
router = Router(tags=["Gastos"])

#  Ninja automaticamente toma la lista de objetos de Django y los pase por el molde de ExpenseOut
@router.get("/", response=List[ExpenseOut])
async def list_expenses(
    request, 
    limit: int=15,
    offset: int=0,
    month: Optional[int]=None,
    year: Optional[int]=None
    ):
    """
    Lista los gastos del usuario autenticado.
    Soporta paginacion (?limiti=15&offset=0) y filtros por fecha (?month=2&year=2026)
    """
    user = request.auth
    
    expenses = await get_lasts_expenses(
        telegram_id=user.telegram_id,
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

    expense = await create_expense(
        user=user,
        amount=payload.amount,
        description=payload.description,
        category_id=payload.category_id
    )
    
    return expense
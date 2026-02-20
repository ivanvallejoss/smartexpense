from ninja import Router
from typing import List
from apps.api.schemas import ExpenseOut
from services.selectors import get_lasts_expenses

# Enrutador especifico para gastos
router = Router(tags=["Gastos"])

#  Ninja automaticamente toma la lista de objetos de Django y los pase por el molde de ExpenseOut
@router.get("/", response=List[ExpenseOut])
async def list_expenses(request, limit: int=50):
    user = request.auth
    expenses = await get_lasts_expenses(telegram_id=user.telegram_id, limit=limit)
    return expenses
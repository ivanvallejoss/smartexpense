from ninja import Router
from apps.api.schemas import BalanceOut
from services.selectors import get_balance

router = Router(tags=["Balances"])

@router.get("/", response=BalanceOut)
async def get_balance_endpoint(request, month: int=None, year: int=None):
    """
    Obtiene el balance total de gastos.
    Se puede filtrar opcionalmente por mes y year.
    """
    user = request.auth

    total_spent = await get_balance(
        user=user,
        month=month,
        year=year
    )

    balance = {"total_spent": total_spent, "currency": "ARS"}

    return balance
from ninja import NinjaAPI
from typing import List
from .schemas import ExpenseOut
from .auth import GlobalAuth
from services.selectors import get_lasts_expenses

# Instanciamos la API y la envolvemos con el candado global.
api = NinjaAPI(title="SmartExpense API", auth=GlobalAuth())

#  Ninja automaticamente toma la lista de objetos de Django y los pase por el molde de ExpenseOut
@api.get("/expenses/", response=List[ExpenseOut])
async def list_expenses(request, limit:int = 50):
    """
    Obtiene los ultimos 10 gastos del usuario.
    """
    # Obtenemos al usuario mediante el candado global
    user = request.auth
    expenses = await get_lasts_expenses(telegram_id=user.telegram_id, limit=limit)

    # Ninja se encarga de serializar la lista de objetos a JSON automaticamente
    return expenses


# @api.post("/expenses/", )
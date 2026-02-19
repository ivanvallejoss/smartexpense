from ninja import NinjaAPI
from typing import List
from apps.api.schemas import ExpenseOut
from services.selectors import get_lasts_expenses

# Instanciamos la API. Esto es como el router principal
api = NinjaAPI(title="SmartExpense API")

# Definimos el endpoint.
# Nota: 'response=List[ExpenseOut]' es la clave. le dice a Ninja que:
#  tome la lista de objetos de Django y los pase por el molde de ExpenseOut
@api.get("/expenses/", response=List[ExpenseOut])
async def list_expenses(request, telegram_id: int, limit:int = 10):
    """
    Obtiene los ultimos gastos de un usuario.
    Por ahora pedimos el 'telegram_id' como parametro en la URL para poder probarlo.
    Mas adelante, esto vendra oculto y seguro en el token JWT
    """
    # Llamamos al MISMO servicio que usa el bot.
    expenses = await get_lasts_expenses(telegram_id=telegram_id, limit=limit)

    # Ninja se encarga de serializar la lista de objetos a JSON automaticamente
    return expenses
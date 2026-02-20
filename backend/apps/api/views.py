from ninja import NinjaAPI
from .auth import GlobalAuth
from .router.expenses import router as expense_router

# Instanciamos la API y la envolvemos con el candado global.
api = NinjaAPI(
    title="SmartExpense API", 
    version="1.0.0",
    auth=GlobalAuth()
    )

api.add_router("/expenses/", expense_router)


# @api.post("/expenses/", )
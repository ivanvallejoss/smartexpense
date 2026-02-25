import logging
from django.http import Http404
from django.core.exceptions import ObjectDoesNotExist
from ninja import NinjaAPI
from .auth import GlobalAuth
from .router.expenses import router as expense_router
from .router.balances import router as balance_router

logger = logging.getLogger(__name__)

# Instanciamos la API y la envolvemos con el candado global.
api = NinjaAPI(
    title="SmartExpense API", 
    version="1.0.0",
    auth=GlobalAuth()
    )

api.add_router("/expenses/", expense_router)
api.add_router("/balances/", balance_router)

@api.exception_handler(Http404)
@api.exception_handler(ObjectDoesNotExist)
def handle_not_found(request, exc):
    """
    Atrapa cualquier busqueda de un objeto que no existe en la base de datso
    """
    return api.create_response(
        request,
        {
            "error": "NOT_FOUND",
            "message": "El recurso que intentas buscar, editar o borrar no existe."
        },
        status=404,
    )

@api.exception_handler(Exception)
def handle_server_error(request, exc):
    """
    Atrapa CUALQUIER error inesperado de Python.
    Ej: calculos matematicos, errores de conexion a DB, fallos de logica.
    """
    logger.error(
        "Error interno del servidor capturado por la API",
        exc_info=True
    )

    return api.create_response(
        request,
        {
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Ocurrio un error inesperado en el servidor. Por favor, intenta mas tarde"
        },
        status=500
    )
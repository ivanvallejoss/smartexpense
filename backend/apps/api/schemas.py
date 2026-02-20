from ninja import Schema
from datetime import datetime
from typing import Optional


# ------- CATEGORY SCHEMA -------
class CategoryOut(Schema):
    id: int
    name: str
    color: str



# ------- EXPENSES SCHEMA -------
class ExpenseIn(Schema):
    """
    Lo que recibimos del frontend al crear un gasto.
    No necesitamos el objeto Category completo, solo su ID.
    No necesitamos la fecha ni el ID del gasto porque los genera la base de datos.
    """
    amount: float
    description: str
    category_id: int

class ExpenseOut(Schema):
    """ 
    Lo que enviamos al Frontend al consultar gastos.
    Incluye los metadatos generados y el objeto Category anidado.
    """
    id: int
    amount: float
    description: str
    category: Optional[CategoryOut] = None     # se anida el schema de salida de la categoria
    date: datetime                             # Django Ninja convierte esto automaticamente a ISO 8061 (2026-02-19T14:30:00z)
    
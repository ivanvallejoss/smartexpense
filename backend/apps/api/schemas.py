from ninja import Schema
from datetime import datetime
from typing import Optional
from pydantic import Field


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
    amount: float = Field(gt=0, description="Monto del gasto, debe ser mayor a 0")
    description: str = Field(min_length=1, max_length=150)
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
    

# ------- BALANCE SCHEMA -------
class BalanceOut(Schema):
    totalSpent: float
    currency: str

    class Config:
        populate_by_name = True
    # trend: trend de los gastos (raro, hay que revisar esto)
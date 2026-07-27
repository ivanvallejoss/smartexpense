"""
Parseo del estado del dashboard que viaja en la querystring (B4).

Helper unico: lo consumen tanto la vista completa como la parcial. Todo lo que
sepa leer o escribir ?cat= y ?rango= vive aca y en ningun otro lado.
"""
from dataclasses import dataclass, replace
from urllib.parse import urlencode

from services.constants import RANGO_DEFAULT, RANGOS


@dataclass(frozen=True)
class DashboardFilters:
    categorias: tuple = ()
    rango: str = RANGO_DEFAULT
    page: int = 1
    avisos: tuple = ()

    def querystring(self) -> str:
        """
        Serializa el estado. El default se omite y el estado vacio devuelve la
        cadena vacia: la URL desnuda de B4-S3 es /dashboard/, sin cola.
        Los templates la concatenan a {% url 'dashboard' %}.
        """
        params = [("cat", cat_id) for cat_id in self.categorias]
        if self.rango != RANGO_DEFAULT:
            params.append(("rango", self.rango))
        if self.page > 1:
            params.append(("page", self.page))
        return f"?{urlencode(params)}" if params else ""

    def toggle_categoria(self, category_id: int) -> "DashboardFilters":
        """Estado resultante de tocar un chip. Vuelve a la pagina 1: el conjunto cambio."""
        if category_id in self.categorias:
            nuevas = tuple(c for c in self.categorias if c != category_id)
        else:
            nuevas = tuple(sorted(self.categorias + (category_id,)))
        return replace(self, categorias=nuevas, page=1, avisos=())

    def con_pagina(self, page: int) -> "DashboardFilters":
        return replace(self, page=page, avisos=())

    @property
    def esta_desnudo(self) -> bool:
        return not self.categorias and self.rango == RANGO_DEFAULT


def parse_dashboard_filters(request) -> DashboardFilters:
    """
    Lee la querystring y devuelve el estado. Nunca falla: lo invalido cae al
    default y deja un aviso para la franja global (B4-S5 + B5 clase 2).
    """
    avisos = []

    categorias = []
    for crudo in request.GET.getlist("cat"):
        try:
            valor = int(crudo)
        except (TypeError, ValueError):
            avisos.append("Se ignoro un filtro de categoria invalido.")
            continue
        if valor > 0 and valor not in categorias:
            categorias.append(valor)

    rango = request.GET.get("rango", RANGO_DEFAULT)
    if rango not in RANGOS:
        avisos.append("Ese rango no existe. Se muestra el mes en curso.")
        rango = RANGO_DEFAULT

    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    return DashboardFilters(
        categorias=tuple(sorted(categorias)),
        rango=rango,
        page=page,
        avisos=tuple(avisos),
    )

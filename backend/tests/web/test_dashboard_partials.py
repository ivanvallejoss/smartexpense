"""
Tests del endpoint de partial del dashboard (Fase C, capa C2).

El centinela "Cargar mas" es un link normal que ademas lleva hx-get. Los tests
verifican las dos caras: que el fragmento sea fragmento, y que la paginacion
sea estable aunque todos los gastos compartan la misma fecha.
"""
from datetime import timedelta
from decimal import Decimal

import pytest

from apps.core.models import Category, Expense, User
from services.selectors import DASHBOARD_PAGE_SIZE, rango_bounds

pytestmark = pytest.mark.django_db


def cargar_gastos(user, cantidad, misma_fecha=False):
    categoria = Category.objects.create(name="Comida", user=user)
    desde_mes, _ = rango_bounds("mes")
    base = desde_mes + timedelta(days=1)
    for i in range(cantidad):
        Expense.objects.create(
            user=user,
            amount=Decimal("100"),
            description=f"Gasto {i}",
            category=categoria,
            date=base if misma_fecha else base + timedelta(minutes=i),
        )


def test_el_parcial_devuelve_fragmento_no_documento(client_logueado, ivan):
    cargar_gastos(ivan, 3)
    cuerpo = client_logueado.get("/dashboard/gastos/").content.decode()
    assert "<li" in cuerpo
    assert "<html" not in cuerpo
    assert 'id="results"' not in cuerpo


def test_el_parcial_exige_sesion(client):
    respuesta = client.get("/dashboard/gastos/")
    assert respuesta.status_code == 302


def test_el_centinela_aparece_solo_si_hay_mas_paginas(client_logueado, ivan):
    cargar_gastos(ivan, DASHBOARD_PAGE_SIZE + 5)

    primera = client_logueado.get("/dashboard/gastos/").content.decode()
    assert "cargar-mas" in primera
    assert 'hx-trigger="revealed"' in primera
    assert "/dashboard/gastos/?page=2" in primera

    ultima = client_logueado.get("/dashboard/gastos/?page=2").content.decode()
    assert "cargar-mas" not in ultima


def test_el_centinela_arrastra_los_filtros(client_logueado, ivan):
    cargar_gastos(ivan, DASHBOARD_PAGE_SIZE + 1)
    categoria = Category.objects.get(name="Comida")

    cuerpo = client_logueado.get(f"/dashboard/gastos/?cat={categoria.id}").content.decode()
    assert f"cat={categoria.id}" in cuerpo
    assert "page=2" in cuerpo


def test_sin_centinela_cuando_entra_todo_en_una_pagina(client_logueado, ivan):
    cargar_gastos(ivan, 3)
    cuerpo = client_logueado.get("/dashboard/gastos/").content.decode()
    assert "cargar-mas" not in cuerpo


def test_el_estado_vacio_no_se_repite_en_paginas_siguientes(client_logueado, ivan):
    cuerpo = client_logueado.get("/dashboard/gastos/?page=2").content.decode()
    assert "Todavía no registraste gastos" not in cuerpo


def test_paginacion_estable_con_gastos_de_la_misma_fecha(client_logueado, ivan):
    """
    Sin el desempate por -id, dos gastos con la misma fecha pueden repetirse o
    perderse entre paginas. Recorrer todo tiene que dar ids unicos y completos.
    """
    total = DASHBOARD_PAGE_SIZE + 5
    cargar_gastos(ivan, total, misma_fecha=True)

    vistos = []
    pagina = 1
    while True:
        cuerpo = client_logueado.get(f"/dashboard/gastos/?page={pagina}").content.decode()
        vistos += [
            linea.split('id="expense-')[1].split('"')[0]
            for linea in cuerpo.splitlines()
            if 'id="expense-' in linea
        ]
        if "cargar-mas" not in cuerpo:
            break
        pagina += 1
        assert pagina < 10, "el centinela no termina nunca"

    assert len(vistos) == total
    assert len(set(vistos)) == total
    assert set(vistos) == {str(pk) for pk in Expense.objects.values_list("id", flat=True)}

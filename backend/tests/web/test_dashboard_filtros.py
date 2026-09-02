"""
Tests del endpoint de filtros del dashboard (Fase C, capa C3).

Lo que se verifica es el contrato de B2 y B4: un swap por interaccion sobre
#results, y la URL canonica escrita por el server, no por los templates.
"""
from datetime import timedelta
from decimal import Decimal

import pytest

from apps.core.models import Category, Expense, User
from services.selectors import rango_bounds

pytestmark = pytest.mark.django_db


@pytest.fixture
def datos(ivan):
    comida = Category.objects.create(name="Comida", user=ivan)
    transporte = Category.objects.create(name="Transporte", user=ivan)
    desde_mes, _ = rango_bounds("mes")

    Expense.objects.create(
        user=ivan,
        amount=Decimal("10000"),
        description="Verduleria",
        category=comida,
        date=desde_mes + timedelta(days=1),
    )
    Expense.objects.create(
        user=ivan,
        amount=Decimal("2500"),
        description="Subte",
        category=transporte,
        date=desde_mes + timedelta(days=2),
    )
    Expense.objects.create(
        user=ivan,
        amount=Decimal("99999"),
        description="Mes anterior",
        category=comida,
        date=desde_mes - timedelta(days=40),
    )
    return {"comida": comida, "transporte": transporte}


def test_devuelve_el_wrapper_y_no_el_documento(client_logueado, datos):
    cuerpo = client_logueado.get("/dashboard/resultados/").content.decode()
    assert 'id="results"' in cuerpo
    assert "<html" not in cuerpo


def test_exige_sesion(client):
    assert client.get("/dashboard/resultados/").status_code == 302


def test_un_solo_swap_trae_balance_chips_y_lista(client_logueado, datos, monto):
    cuerpo = client_logueado.get(
        f"/dashboard/resultados/?cat={datos['comida'].id}"
    ).content.decode()
    assert monto("10000") in cuerpo
    assert 'class="chip chip--activo"' in cuerpo
    assert "Verduleria" in cuerpo
    assert "Subte" not in cuerpo


def test_la_url_canonica_la_escribe_el_server(client_logueado, datos):
    respuesta = client_logueado.get(f"/dashboard/resultados/?cat={datos['comida'].id}&rango=3m")
    canonica = respuesta["HX-Replace-Url"]
    assert canonica.startswith("/dashboard/")
    assert "resultados" not in canonica
    assert f"cat={datos['comida'].id}" in canonica
    assert "rango=3m" in canonica


def test_la_url_canonica_del_estado_vacio_es_la_desnuda(client_logueado, datos):
    respuesta = client_logueado.get("/dashboard/resultados/")
    assert respuesta["HX-Replace-Url"] == "/dashboard/"


def test_el_chip_activo_apunta_a_la_url_desnuda(client_logueado, datos):
    cuerpo = client_logueado.get(
        f"/dashboard/resultados/?cat={datos['comida'].id}"
    ).content.decode()
    assert 'href="/dashboard/"' in cuerpo
    assert 'hx-get="/dashboard/resultados/"' in cuerpo


def test_categoria_y_rango_se_combinan(client_logueado, datos, monto):
    url = f"/dashboard/resultados/?cat={datos['comida'].id}&rango=3m"
    cuerpo = client_logueado.get(url).content.decode()
    assert monto("109999") in cuerpo
    assert "Mes anterior" in cuerpo
    assert "Subte" not in cuerpo


def test_el_form_arrastra_las_categorias_activas(client_logueado, datos):
    cuerpo = client_logueado.get(
        f"/dashboard/resultados/?cat={datos['comida'].id}"
    ).content.decode()
    assert f'<input type="hidden" name="cat" value="{datos["comida"].id}">' in cuerpo


def test_el_endpoint_de_filtros_no_reescribe_la_url_del_de_gastos(client_logueado, datos):
    """La paginacion no toca la barra de direcciones: solo #results lo hace."""
    respuesta = client_logueado.get("/dashboard/gastos/")
    assert "HX-Replace-Url" not in respuesta

    completa = client_logueado.get("/dashboard/")
    assert "HX-Replace-Url" not in completa

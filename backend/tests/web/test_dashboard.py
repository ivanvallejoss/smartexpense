"""
Tests de la vista del dashboard (Fase C, capa C1: SSR sin HTMX).

Cubren el baseline de progressive enhancement: todo lo que se testea aca tiene
que funcionar con JavaScript deshabilitado, porque no hay una sola linea de JS.
"""
from datetime import datetime, timedelta
from datetime import timezone as tz_utc
from decimal import Decimal
from unittest.mock import patch

from django.test import Client

import pytest

from apps.core.models import Category, Expense, User
from services.selectors import rango_bounds

pytestmark = pytest.mark.django_db


@pytest.fixture
def datos(ivan):
    """Un mes en curso con dos categorias, un mes anterior y un gasto en el borde."""
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
        date=desde_mes - timedelta(days=5),
    )
    Expense.objects.create(
        user=ivan,
        amount=Decimal("777"),
        description="Borde 23hs",
        category=comida,
        date=desde_mes - timedelta(hours=1),
    )
    Expense.objects.create(
        user=ivan,
        amount=Decimal("50"),
        description="Sin confirmar",
        category=comida,
        date=desde_mes + timedelta(days=1),
        status=Expense.STATUS_PENDING,
    )
    return {"comida": comida, "transporte": transporte, "desde_mes": desde_mes}


def test_anonimo_redirige_al_login(client):
    respuesta = client.get("/dashboard/")
    assert respuesta.status_code == 302
    assert respuesta["Location"] == "/pedir-acceso/?next=/dashboard/"


def test_balance_es_el_del_mes_en_curso(client_logueado, datos, monto):
    cuerpo = client_logueado.get("/dashboard/").content.decode()
    assert monto("12500") in cuerpo
    assert "99999" not in cuerpo


def test_excluye_gastos_sin_confirmar(client_logueado, datos):
    cuerpo = client_logueado.get("/dashboard/").content.decode()
    assert "Sin confirmar" not in cuerpo


def test_borde_del_mes_se_calcula_en_hora_de_buenos_aires(client_logueado, datos):
    """
    El gasto del ultimo dia del mes a las 23:00 de Buenos Aires se guarda como
    dia 1 en UTC. Con date__month habria entrado al mes equivocado.
    """
    cuerpo = client_logueado.get("/dashboard/").content.decode()
    assert "Borde 23hs" not in cuerpo


def test_filtro_por_categoria_recalcula_lista_y_balance(client_logueado, datos, monto):
    cuerpo = client_logueado.get(f"/dashboard/?cat={datos['comida'].id}").content.decode()
    assert monto("10000") in cuerpo
    assert "Verduleria" in cuerpo
    assert "Subte" not in cuerpo


def test_multiples_categorias_se_suman(client_logueado, datos, monto):
    url = f"/dashboard/?cat={datos['comida'].id}&cat={datos['transporte'].id}"
    cuerpo = client_logueado.get(url).content.decode()
    assert monto("12500") in cuerpo
    assert "Verduleria" in cuerpo and "Subte" in cuerpo


def test_rango_amplio_incluye_meses_previos(client_logueado, datos, monto):
    cuerpo = client_logueado.get("/dashboard/?rango=3m").content.decode()
    assert monto("113276") in cuerpo


def test_rango_invalido_cae_al_default_con_aviso(client_logueado, datos, monto):
    cuerpo = client_logueado.get("/dashboard/?rango=basura").content.decode()
    assert "Ese rango no existe" in cuerpo
    assert monto("12500") in cuerpo


def test_paginacion_parte_la_lista(client_logueado, ivan, datos):
    for i in range(22):
        Expense.objects.create(
            user=ivan,
            amount=Decimal("100"),
            description=f"Relleno {i}",
            category=datos["transporte"],
            date=datos["desde_mes"] + timedelta(days=3, minutes=i),
        )

    primera = client_logueado.get("/dashboard/").content.decode()
    assert primera.count('class="expense-item"') == 20
    assert "page=2" in primera

    segunda = client_logueado.get("/dashboard/?page=2").content.decode()
    assert segunda.count('class="expense-item"') == 4


def test_estado_vacio_absoluto(client_logueado):
    cuerpo = client_logueado.get("/dashboard/").content.decode()
    assert "Todavía no registraste gastos" in cuerpo


def test_estado_vacio_por_filtro_ofrece_limpiar(client_logueado, ivan, datos):
    vacia = Category.objects.create(name="Vacia", user=ivan)
    cuerpo = client_logueado.get(f"/dashboard/?cat={vacia.id}").content.decode()
    assert "Ningún gasto en este rango" in cuerpo
    assert "Limpiar filtros" in cuerpo


def test_el_dashboard_muestra_los_gastos_el_primer_dia_del_mes(client_logueado, ivan, monto):
    """
    Candado de la regresion que motivo reloj_fijo.

    El 1ro a las 00:00:05 la ventana del rango "mes" mide cinco segundos. Un
    gasto cargado dentro de esa ventana tiene que aparecer igual: si el filtro
    se corriera aunque sea un segundo, el usuario que abre el dashboard el
    primer dia del mes lo veria vacio.

    Se congela el reloj adentro del test, pisando a reloj_fijo, porque es el
    unico caso que quiere medir el borde en vez de esquivarlo. La fecha elegida
    cae antes que RELOJ_DE_TEST a proposito: la sesion de client_logueado se
    crea con el reloj de la fixture y adelantarse un mes la venceria.
    """
    arranque = datetime(2026, 3, 1, 3, 0, 5, tzinfo=tz_utc.utc)  # 00:00:05 en Buenos Aires
    comida = Category.objects.create(name="Comida", user=ivan)

    with patch("django.utils.timezone.now", return_value=arranque):
        desde_mes, _ = rango_bounds("mes")
        Expense.objects.create(
            user=ivan,
            amount=Decimal("4200"),
            description="Recien cargado",
            category=comida,
            date=desde_mes + timedelta(seconds=1),
        )
        # Treinta segundos despues del corte. Fija el ancho real de la ventana:
        # sin el reloj de adentro la ventana llegaria hasta RELOJ_DE_TEST y este
        # gasto tambien entraria, con lo cual el test no probaria nada.
        Expense.objects.create(
            user=ivan,
            amount=Decimal("888"),
            description="Todavia no ocurrio",
            category=comida,
            date=desde_mes + timedelta(seconds=30),
        )
        cuerpo = client_logueado.get("/dashboard/").content.decode()

    assert "Recien cargado" in cuerpo
    assert monto("4200") in cuerpo
    assert "Todavia no ocurrio" not in cuerpo


def test_no_ve_gastos_de_otro_usuario(datos):
    otro = User.objects.create_user(username="otro", password="x")
    client = Client()
    client.force_login(otro)
    cuerpo = client.get("/dashboard/").content.decode()
    assert "Verduleria" not in cuerpo

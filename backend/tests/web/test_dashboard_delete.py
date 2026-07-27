"""
Tests del borrado inline (Fase C, capa C4).

Las dos caras: con htmx devuelve #results recalculado, sin htmx redirige
conservando los filtros. Y la clase 2 de B5: la falla tecnica no se lleva
puesta la vista que estabas leyendo.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from apps.core.models import Category, DeletedObject, Expense, User
from services.selectors import rango_bounds

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def datos(ivan):
    comida = Category.objects.create(name="Comida", user=ivan)
    desde_mes, _ = rango_bounds("mes")
    verduleria = Expense.objects.create(user=ivan, amount=Decimal("10000"),
                                        description="Verduleria", category=comida,
                                        date=desde_mes + timedelta(days=1))
    kiosco = Expense.objects.create(user=ivan, amount=Decimal("2500"),
                                    description="Kiosco", category=comida,
                                    date=desde_mes + timedelta(days=2))
    return {"comida": comida, "verduleria": verduleria, "kiosco": kiosco}



def url_borrar(expense_id, cola=""):
    return f"/dashboard/gastos/{expense_id}/eliminar/{cola}"


def test_borra_y_el_mismo_response_ya_trae_el_balance_nuevo(client_logueado, datos, monto):
    respuesta = client_logueado.post(url_borrar(datos["verduleria"].id), **HTMX)
    cuerpo = respuesta.content.decode()

    assert respuesta.status_code == 200
    assert 'id="results"' in cuerpo
    assert monto("2500") in cuerpo
    assert monto("12500") not in cuerpo
    assert "Verduleria" not in cuerpo
    assert "Kiosco" in cuerpo


def test_el_borrado_queda_registrado_en_la_papelera(client_logueado, datos):
    expense_id = datos["verduleria"].id
    client_logueado.post(url_borrar(expense_id), **HTMX)

    assert not Expense.objects.filter(id=expense_id).exists()
    registro = DeletedObject.objects.get(
        content_type=ContentType.objects.get_for_model(Expense),
        object_id=expense_id,
    )
    assert registro.object_data["description"] == "Verduleria"


def test_sin_htmx_redirige_conservando_los_filtros(client_logueado, datos):
    cola = f"?cat={datos['comida'].id}&rango=3m"
    respuesta = client_logueado.post(url_borrar(datos["verduleria"].id, cola))

    assert respuesta.status_code == 302
    assert respuesta["Location"] == f"/dashboard/{cola}"


def test_el_swap_respeta_los_filtros_activos(client_logueado, ivan, datos, monto):
    otra = Category.objects.create(name="Transporte", user=ivan)
    desde_mes, _ = rango_bounds("mes")
    Expense.objects.create(user=ivan, amount=Decimal("900"), description="Subte",
                           category=otra, date=desde_mes + timedelta(days=3))

    cola = f"?cat={datos['comida'].id}"
    cuerpo = client_logueado.post(url_borrar(datos["verduleria"].id, cola), **HTMX).content.decode()

    assert monto("2500") in cuerpo
    assert "Subte" not in cuerpo


def test_gasto_de_otro_usuario_no_se_puede_borrar(client_logueado, datos):
    otro = User.objects.create_user(username="otro", password="x")
    desde_mes, _ = rango_bounds("mes")
    ajeno = Expense.objects.create(user=otro, amount=Decimal("500"),
                                   description="Ajeno", date=desde_mes + timedelta(days=1))

    respuesta = client_logueado.post(url_borrar(ajeno.id), **HTMX)

    assert respuesta.status_code == 404
    assert Expense.objects.filter(id=ajeno.id).exists()


def test_el_error_va_a_la_franja_y_no_toca_results(client_logueado, datos):
    respuesta = client_logueado.post(url_borrar(999999), **HTMX)
    cuerpo = respuesta.content.decode()

    assert respuesta.status_code == 404
    assert respuesta["HX-Retarget"] == "#avisos"
    assert 'id="avisos"' in cuerpo
    assert 'id="results"' not in cuerpo
    assert "ya no existe" in cuerpo


def test_borrar_dos_veces_el_mismo_gasto_avisa_y_no_rompe(client_logueado, datos):
    expense_id = datos["verduleria"].id
    primera = client_logueado.post(url_borrar(expense_id), **HTMX)
    segunda = client_logueado.post(url_borrar(expense_id), **HTMX)

    assert primera.status_code == 200
    assert segunda.status_code == 404
    assert segunda["HX-Retarget"] == "#avisos"


def test_el_borrado_exige_sesion(client, datos):
    respuesta = client.post(url_borrar(datos["verduleria"].id))
    assert respuesta.status_code == 302
    assert Expense.objects.filter(id=datos["verduleria"].id).exists()


def test_el_form_de_borrado_viaja_en_la_lista(client_logueado, datos):
    cuerpo = client_logueado.get("/dashboard/").content.decode()
    assert url_borrar(datos["verduleria"].id) in cuerpo
    assert "csrfmiddlewaretoken" in cuerpo
    assert "hx-confirm" in cuerpo


def test_get_al_endpoint_de_borrado_devuelve_405(client_logueado, datos):
    """
    Heredar de la familia de lectura le daba un get() que no aceptaba el
    argumento de URL: 500 en vez de 405. El borrado solo acepta POST.
    """
    respuesta = client_logueado.get(url_borrar(datos["verduleria"].id))
    assert respuesta.status_code == 405
    assert Expense.objects.filter(id=datos["verduleria"].id).exists()

"""Fixtures compartidas por los tests del dashboard web (Fase C)."""
from datetime import datetime, timezone as tz_utc
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import Client

from apps.core.models import User

# 15 de marzo a las 12:00 de Buenos Aires. Mitad de mes a proposito: ver reloj_fijo.
RELOJ_DE_TEST = datetime(2026, 3, 15, 15, 0, tzinfo=tz_utc.utc)


@pytest.fixture(autouse=True)
def reloj_fijo():
    """
    Congela el reloj a mitad de mes para todos los tests del dashboard.

    La ventana del rango "mes" va del 1ro a las 00:00 en hora de Buenos Aires
    hasta ahora, asi que su ancho depende del dia en que corras la suite: 31
    dias el ultimo del mes, cinco segundos el 1ro a las 00:00:05. Los fixtures
    ubican los gastos con offsets absolutos hacia adelante (desde_mes + 1 dia,
    espaciados de a un minuto), que solo entran si la ventana ya es ancha. Los
    primeros tres dias de cada mes esos gastos caian en el futuro, date__lte
    los excluia, y 14 tests se ponian rojos: invisibles los otros 27 dias.

    Fijar el reloj vuelve determinista al calendario, que es justamente la
    variable que estos tests no querian medir. El borde angosto no se pierde,
    se cubre explicitamente en el candado de test_dashboard.py.

    No alcanza para tests que construyan gastos con ExpenseFactory: su
    LazyFunction se liga a timezone.now al importar y este patch no la toca.
    """
    with patch("django.utils.timezone.now", return_value=RELOJ_DE_TEST):
        yield


@pytest.fixture
def ivan():
    return User.objects.create_user(username="ivan", password="secreta")


@pytest.fixture
def client_logueado(ivan):
    client = Client()
    client.force_login(ivan)
    return client


@pytest.fixture
def monto():
    """El locale es es-ar: los decimales van con coma."""
    def formatear(valor) -> str:
        return f"${Decimal(valor):.2f}".replace(".", ",")
    return formatear

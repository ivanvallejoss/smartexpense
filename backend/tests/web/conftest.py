"""Fixtures compartidas por los tests del dashboard web (Fase C)."""
from decimal import Decimal

import pytest
from django.test import Client

from apps.core.models import User


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

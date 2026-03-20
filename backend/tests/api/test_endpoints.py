"""
Tests de integración para la API Web (Endpoints de Gastos y Balances).
"""
import jwt
import pytest
from datetime import datetime, timedelta, timezone
from django.conf import settings
from django.utils import timezone as djangotz
from ninja.testing import TestAsyncClient

# Importamos la instancia central de tu API
from apps.api.views import api 
from apps.core.models import Expense, User, Category
from tests.factories import UserFactory, CategoryFactory, ExpenseFactory

# Todos los tests necesitan DB y transacciones asíncronas
pytestmark = pytest.mark.django_db(transaction=True)

# ============================================
# HELPER DE AUTENTICACIÓN
# ============================================

def get_auth_headers(user):
    """
    Genera un JWT válido para el usuario simulando el proceso de login.
    Retorna el diccionario de headers listo para inyectar en el TestClient.
    """
    payload = {
        "sub": str(user.telegram_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=1)
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


ninja_client = TestAsyncClient(api)

@pytest.fixture
def client():
    """Fixture para obtener el cliente asíncrono de Ninja."""
    return ninja_client


# ============================================
# TESTS DE AUTENTICACIÓN GLOBAL
# ============================================

class TestGlobalAuth:
    async def test_unauthorized_request_is_rejected(self, client):
        """Un request sin token debe fallar en cualquier ruta."""
        response = await client.get("/expenses/")
        assert response.status_code == 401


# ============================================
# TESTS DE GASTOS (/expenses/)
# ============================================

class TestExpensesEndpoints:

    @pytest.mark.skip(reason="Refactoring in progress")
    async def test_list_expenses(self, client):
        user = await User.objects.acreate(telegram_id=1234, username="api_user")
        category = await Category.objects.acreate(name="Food", is_default=True)
        
        # Creamos 2 gastos para este usuario
        await Expense.objects.acreate(user=user, category=category, amount=100, description="1", date=djangotz.now())
        await Expense.objects.acreate(user=user, category=category, amount=200, description="2", date=djangotz.now())

        headers = get_auth_headers(user)
        response = await client.get("/expenses/", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Verificamos que el schema ExpenseOut se esté aplicando correctamente
        assert "category" in data[0]
        assert data[0]["amount"] in [100.0, 200.0]

    @pytest.mark.skip(reason="Refactoring in progress")
    async def test_create_expense(self, client):
        user = await User.objects.acreate(telegram_id=555, username="creator")
        category = await Category.objects.acreate(name="Transport", is_default=True)
        headers = get_auth_headers(user)

        payload = {
            "amount": 1500.50,
            "description": "Viaje en Uber",
            "category": category.id
        }

        response = await client.post("/expenses/", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == 1500.50
        assert data["description"] == "Viaje en Uber"
        assert data["category"]["id"] == category.id

    @pytest.mark.skip(reason="Refactoring in progress")
    async def test_update_expense(self, client):
        user = await User.objects.acreate(telegram_id=777, username="updater")
        cat_old = await Category.objects.acreate(name="Old", is_default=True)
        cat_new = await Category.objects.acreate(name="New", is_default=True)
        expense = await Expense.objects.acreate(user=user, category=cat_old, amount=100, description="A", date=djangotz.now())

        headers = get_auth_headers(user)
        payload = {
            "amount": 500.0,
            "description": "Actualizado",
            "category_id": cat_new.id
        }

        response = await client.put(f"/expenses/{expense.id}/", json=payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == 500.0
        assert data["description"] == "Actualizado"

    @pytest.mark.skip(reason="Refactoring in progress")
    async def test_update_expense_not_found_returns_404(self, client):
        """Verifica que el exception_handler global capture el ObjectDoesNotExist."""
        user = await User.objects.acreate(telegram_id=888, username="hacker")
        cat = await Category.objects.acreate(name="Test", is_default=True)
        headers = get_auth_headers(user)
        
        payload = {"amount": 100, "description": "Hack", "category_id": cat.id}

        # Intentamos actualizar un ID que no existe (9999)
        response = await client.put("/expenses/9999/", json=payload, headers=headers)

        assert response.status_code == 404
        assert response.json()["error"] == "NOT_FOUND"

    @pytest.mark.skip(reason="Refactoring in progress")
    async def test_delete_expense(self, client):
        user = await User.objects.acreate(telegram_id=999, username="deleter")
        cat = await Category.objects.acreate(name="Del", is_default=True)
        expense = await Expense.objects.acreate(user=user, category=cat, amount=100, description="Borrar", date=djangotz.now())

        headers = get_auth_headers(user)
        response = await client.delete(f"/expenses/{expense.id}/", headers=headers)

        # 204 No Content no devuelve JSON
        assert response.status_code == 204
        # Verificamos que realmente se borró de la DB
        count = await Expense.objects.filter(id=expense.id).acount()
        assert count == 0


# ============================================
# TESTS DE BALANCES (/balances/)
# ============================================

class TestBalancesEndpoints:

    async def test_get_balance(self, client):
        user = await User.objects.acreate(telegram_id=1010, username="balance_user")
        cat = await Category.objects.acreate(name="Test", is_default=True)
        
        # Gastos que suman 300.75
        await Expense.objects.acreate(user=user, category=cat, amount=100.50, description="1", date=djangotz.now())
        await Expense.objects.acreate(user=user, category=cat, amount=200.25, description="2", date=djangotz.now())

        headers = get_auth_headers(user)
        response = await client.get("/balances/", headers=headers)

        assert response.status_code == 200
        data = response.json()
        
        # Verificamos el 'alias' de Pydantic (total_spent -> totalSpent)
        assert "totalSpent" in data
        assert data["totalSpent"] == 300.75
        assert data["currency"] == "ARS"
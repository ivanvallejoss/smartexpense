# tests/api/test_endpoints.py

import jwt
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from asgiref.sync import sync_to_async

from django.conf import settings
from ninja.testing import TestAsyncClient

from apps.api.views import api
from apps.core.models import Expense, CategorySuggestionFeedback, DeletedObject
from tests.factories import UserFactory, CategoryFactory, ExpenseFactory

pytestmark = pytest.mark.django_db(transaction=True)


# ============================================
# HELPER DE AUTENTICACIÓN
# ============================================

def get_auth_headers(user):
    payload = {
        "sub": str(user.telegram_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=1)
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

client = TestAsyncClient(api)


# ============================================
# AUTENTICACIÓN GLOBAL
# ============================================

class TestGlobalAuth:

    async def test_unauthorized_request_is_rejected(self):
        response = await client.get("/expenses/")
        assert response.status_code == 401


# ============================================
# GET /expenses/
# ============================================

class TestListExpenses:

    async def test_returns_only_own_confirmed_expenses(self):
        """
        Aislamiento por usuario y por status en un solo test.
        Razón: son dos filtros del mismo queryset — testearlos juntos
        verifica que no se interfieran entre sí.
        """
        user = await sync_to_async(UserFactory)()
        other_user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(is_default=True, user=None)

        # Deben aparecer
        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            status=Expense.STATUS_CONFIRMED
        )
        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            status=Expense.STATUS_CONFIRMED
        )
        # No debe aparecer — pendiente
        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            status=Expense.STATUS_PENDING
        )
        # No debe aparecer — otro usuario
        await sync_to_async(ExpenseFactory)(
            user=other_user, category=category,
            status=Expense.STATUS_CONFIRMED
        )

        response = await client.get("/expenses/", headers=get_auth_headers(user))

        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_filter_by_month_and_year(self):
        """
        Fechas explícitas para evitar flakiness por timezone.
        """
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(is_default=True, user=None)

        # Fecha fija en marzo 2026 — debe aparecer con ?month=3&year=2026
        march_date = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        # Fecha en mes distinto — no debe aparecer
        february_date = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)

        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            date=march_date, status=Expense.STATUS_CONFIRMED
        )
        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            date=february_date, status=Expense.STATUS_CONFIRMED
        )

        response = await client.get(
            "/expenses/?month=3&year=2026",
            headers=get_auth_headers(user)
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    async def test_pagination_limit_and_offset(self):
        """
        Crea 5 gastos y verifica que limit y offset recorten correctamente.
        """
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(is_default=True, user=None)

        for i in range(5):
            await sync_to_async(ExpenseFactory)(
                user=user, category=category,
                status=Expense.STATUS_CONFIRMED
            )

        # Página 1: primeros 2
        response_p1 = await client.get(
            "/expenses/?limit=2&offset=0",
            headers=get_auth_headers(user)
        )
        # Página 2: siguientes 2
        response_p2 = await client.get(
            "/expenses/?limit=2&offset=2",
            headers=get_auth_headers(user)
        )

        assert len(response_p1.json()) == 2
        assert len(response_p2.json()) == 2

        # Verificamos que sean gastos distintos
        ids_p1 = {e["id"] for e in response_p1.json()}
        ids_p2 = {e["id"] for e in response_p2.json()}
        assert ids_p1.isdisjoint(ids_p2)


# ============================================
# POST /expenses/
# ============================================

class TestCreateExpense:

    async def test_creates_expense_and_returns_201(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(is_default=True, user=None)

        payload = {
            "amount": 1500.50,
            "description": "Viaje en Uber",
            "category_id": category.id
        }

        response = await client.post(
            "/expenses/",
            json=payload,
            headers=get_auth_headers(user)
        )

        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == 1500.50
        assert data["description"] == "Viaje en Uber"
        assert data["category"]["id"] == category.id

        # Verificamos persistencia real en DB
        count = await Expense.objects.filter(user=user).acount()
        assert count == 1

    async def test_rejects_amount_zero_or_negative(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(is_default=True, user=None)

        for invalid_amount in [0, -100]:
            payload = {
                "amount": invalid_amount,
                "description": "Test",
                "category_id": category.id
            }
            response = await client.post(
                "/expenses/",
                json=payload,
                headers=get_auth_headers(user)
            )
            # Pydantic/Django validator rechaza el monto
            assert response.status_code == 422, \
                f"Esperaba 422 para amount={invalid_amount}"


# ============================================
# PUT /expenses/{id}/
# ============================================

class TestUpdateExpense:

    async def test_updates_expense_correctly(self):
        user = await sync_to_async(UserFactory)()
        cat_old = await sync_to_async(CategoryFactory)(name="Comida", user=None, is_default=True)
        cat_new = await sync_to_async(CategoryFactory)(name="Transporte", user=None, is_default=True)
        expense = await sync_to_async(ExpenseFactory)(
            user=user, category=cat_old,
            status=Expense.STATUS_CONFIRMED
        )

        payload = {
            "amount": 999.0,
            "description": "Actualizado",
            "category_id": cat_new.id
        }

        response = await client.put(
            f"/expenses/{expense.id}/",
            json=payload,
            headers=get_auth_headers(user)
        )

        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == 999.0
        assert data["description"] == "Actualizado"
        assert data["category"]["id"] == cat_new.id

    async def test_category_change_records_feedback(self):
        """
        Verifica el side effect más importante del update:
        que el cambio de categoría alimenta al categorizador.
        """
        user = await sync_to_async(UserFactory)()
        cat_old = await sync_to_async(CategoryFactory)(name="Comida", user=None, is_default=True)
        cat_new = await sync_to_async(CategoryFactory)(name="Transporte", user=None, is_default=True)
        expense = await sync_to_async(ExpenseFactory)(
            user=user, category=cat_old,
            status=Expense.STATUS_CONFIRMED
        )

        count_before = await CategorySuggestionFeedback.objects.acount()

        payload = {
            "amount": expense.amount,
            "description": expense.description,
            "category_id": cat_new.id
        }

        await client.put(
            f"/expenses/{expense.id}/",
            json=payload,
            headers=get_auth_headers(user)
        )

        count_after = await CategorySuggestionFeedback.objects.acount()
        assert count_after == count_before + 1

        feedback = await CategorySuggestionFeedback.objects.select_related(
            'suggested_category', 'final_category'
        ).alatest('created_at')
        assert feedback.suggested_category.id == cat_old.id
        assert feedback.final_category.id == cat_new.id
        assert feedback.was_accepted is False

    async def test_cannot_update_other_users_expense(self):
        owner = await sync_to_async(UserFactory)()
        intruder = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(is_default=True, user=None)
        expense = await sync_to_async(ExpenseFactory)(user=owner, category=category)

        payload = {
            "amount": 1.0,
            "description": "Hack",
            "category_id": category.id
        }

        response = await client.put(
            f"/expenses/{expense.id}/",
            json=payload,
            headers=get_auth_headers(intruder)
        )

        assert response.status_code == 404


# ============================================
# DELETE /expenses/{id}/
# ============================================

class TestDeleteExpense:

    async def test_returns_204_and_removes_from_main_table(self):
        user = await sync_to_async(UserFactory)()
        expense = await sync_to_async(ExpenseFactory)(user=user)

        response = await client.delete(
            f"/expenses/{expense.id}/",
            headers=get_auth_headers(user)
        )

        assert response.status_code == 204
        count = await Expense.objects.filter(id=expense.id).acount()
        assert count == 0

    async def test_soft_delete_creates_deleted_object(self):
        """
        El gasto no desaparece del sistema — queda en la papelera.
        Este test verifica que el contrato de restauración sea posible.
        """
        user = await sync_to_async(UserFactory)()
        expense = await sync_to_async(ExpenseFactory)(
            user=user, description="Gasto a borrar"
        )
        expense_id = expense.id

        await client.delete(
            f"/expenses/{expense_id}/",
            headers=get_auth_headers(user)
        )

        deleted = await DeletedObject.objects.filter(
            object_id=expense_id
        ).aexists()
        assert deleted is True

    async def test_cannot_delete_other_users_expense(self):
        owner = await sync_to_async(UserFactory)()
        intruder = await sync_to_async(UserFactory)()
        expense = await sync_to_async(ExpenseFactory)(user=owner)

        response = await client.delete(
            f"/expenses/{expense.id}/",
            headers=get_auth_headers(intruder)
        )

        assert response.status_code == 404
        # El gasto del owner sigue intacto
        count = await Expense.objects.filter(id=expense.id).acount()
        assert count == 1
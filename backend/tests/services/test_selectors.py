# tests/services/test_selectors.py

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from asgiref.sync import sync_to_async

from apps.core.models import Expense, Category
from services.selectors import (
    get_expenses,
    get_balance,
    get_month_stats,
    get_user_categories_or_defaults,
)
from tests.factories import UserFactory, CategoryFactory, ExpenseFactory

pytestmark = pytest.mark.django_db(transaction=True)


# ============================================
# GET EXPENSES
# ============================================

class TestGetExpenses:

    async def test_returns_confirmed_expenses_for_user(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(is_default=True, user=None)

        await sync_to_async(ExpenseFactory)(
            user=user, category=category, status=Expense.STATUS_CONFIRMED
        )
        await sync_to_async(ExpenseFactory)(
            user=user, category=category, status=Expense.STATUS_CONFIRMED
        )

        result = await get_expenses(user=user)

        assert len(result) == 2

    async def test_excludes_pending_expenses(self):
        """
        Los gastos pendientes de categorización no deben aparecer
        en el listado — son invisibles para el usuario hasta confirmarse.
        """
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(is_default=True, user=None)

        await sync_to_async(ExpenseFactory)(
            user=user, category=category, status=Expense.STATUS_CONFIRMED
        )
        await sync_to_async(ExpenseFactory)(
            user=user, category=category, status=Expense.STATUS_PENDING
        )

        result = await get_expenses(user=user)

        assert len(result) == 1
        assert result[0].status == Expense.STATUS_CONFIRMED

    async def test_returns_empty_list_when_no_expenses(self):
        user = await sync_to_async(UserFactory)()

        result = await get_expenses(user=user)

        assert result == []

    async def test_filter_by_month_and_year(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(is_default=True, user=None)

        march_date = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        february_date = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)

        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            date=march_date, status=Expense.STATUS_CONFIRMED
        )
        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            date=february_date, status=Expense.STATUS_CONFIRMED
        )

        result = await get_expenses(user=user, month=3, year=2026)

        assert len(result) == 1
        assert result[0].date.month == 3


# ============================================
# GET BALANCE
# ============================================

class TestGetBalance:

    async def test_returns_correct_sum(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(is_default=True, user=None)

        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            amount=Decimal("1000"), status=Expense.STATUS_CONFIRMED
        )
        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            amount=Decimal("500.50"), status=Expense.STATUS_CONFIRMED
        )

        result = await get_balance(user=user)

        assert result == Decimal("1500.50")

    async def test_returns_zero_when_no_expenses(self):
        user = await sync_to_async(UserFactory)()

        result = await get_balance(user=user)

        assert result == 0.0

    async def test_balance_is_never_negative(self):
        """
        Invariante del sistema: el balance siempre es >= 0.
        El modelo rechaza amounts negativos, pero lo verificamos
        también a nivel de selector.
        """
        user = await sync_to_async(UserFactory)()

        result = await get_balance(user=user)

        assert result >= 0

    async def test_filter_by_month_and_year(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(is_default=True, user=None)

        march_date = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        february_date = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)

        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            amount=Decimal("1000"), date=march_date,
            status=Expense.STATUS_CONFIRMED
        )
        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            amount=Decimal("500"), date=february_date,
            status=Expense.STATUS_CONFIRMED
        )

        result = await get_balance(user=user, month=3, year=2026)

        assert result == Decimal("1000")


# ============================================
# GET MONTH STATS
# ============================================

class TestGetMonthStats:

    async def test_returns_all_four_fields(self):
        user = await sync_to_async(UserFactory)()

        result = await get_month_stats(user=user)

        assert "total_amount" in result
        assert "total_count" in result
        assert "by_category" in result
        assert "month_name" in result

    async def test_month_name_is_in_spanish(self):
        """
        Con LANGUAGE_CODE = 'es-ar', strftime('%B') devuelve el mes en español.
        Este test documenta ese comportamiento explícitamente para evitar
        confusión futura si alguien cambia el locale.
        """
        user = await sync_to_async(UserFactory)()

        result = await get_month_stats(user=user)

        # El nombre del mes debe estar en español
        spanish_months = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]
        month_name_lower = result["month_name"].lower()
        assert any(month in month_name_lower for month in spanish_months)

    async def test_totals_are_correct(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(
            name="Comida", is_default=True, user=None
        )

        # Usamos el mes actual para que el filtro de get_month_stats los incluya
        from django.utils import timezone
        now = timezone.now()

        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            amount=Decimal("1000"), date=now,
            status=Expense.STATUS_CONFIRMED
        )
        await sync_to_async(ExpenseFactory)(
            user=user, category=category,
            amount=Decimal("500"), date=now,
            status=Expense.STATUS_CONFIRMED
        )

        result = await get_month_stats(user=user)

        assert result["total_count"] == 2
        assert result["total_amount"] == Decimal("1500")
        assert len(result["by_category"]) == 1
        assert result["by_category"][0]["category__name"] == "Comida"


# ============================================
# GET USER CATEGORIES OR DEFAULTS
# ============================================

class TestGetUserCategoriesOrDefaults:

    async def test_returns_own_and_global_categories(self):
        user = await sync_to_async(UserFactory)()

        # Categoría global — disponible para todos
        await sync_to_async(CategoryFactory)(
            name="Global", is_default=True, user=None
        )
        # Categoría propia del usuario
        await sync_to_async(CategoryFactory)(
            name="Personal", is_default=False, user=user
        )

        result = await get_user_categories_or_defaults(user=user)

        names = {cat.name for cat in result}
        assert "Global" in names
        assert "Personal" in names

    async def test_does_not_return_other_users_categories(self):
        user = await sync_to_async(UserFactory)()
        other_user = await sync_to_async(UserFactory)()

        await sync_to_async(CategoryFactory)(
            name="Ajena", is_default=False, user=other_user
        )

        result = await get_user_categories_or_defaults(user=user)

        names = {cat.name for cat in result}
        assert "Ajena" not in names

    async def test_user_with_no_own_categories_still_gets_globals(self):
        """
        Un usuario nuevo sin ninguna categoría propia igual debe
        recibir las categorías globales del sistema.
        """
        user = await sync_to_async(UserFactory)()
        await sync_to_async(CategoryFactory)(
            name="Comida", is_default=True, user=None
        )

        result = await get_user_categories_or_defaults(user=user)

        assert len(result) >= 1
        assert all(cat.is_default for cat in result)
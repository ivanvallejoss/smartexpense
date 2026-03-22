"""
Tests del módulo de machine learning.
Cubre suggest(), record_feedback y get_category_suggestion.
"""
import pytest
from decimal import Decimal
from asgiref.sync import sync_to_async
from unittest.mock import patch

from apps.core.models import Category, CategorySuggestionFeedback, Expense
from services.ml.categorizer import ExpenseCategorizer, create_category_for_user
from services.ml.helper import get_category_suggestion
from tests.factories import UserFactory, CategoryFactory, ExpenseFactory

pytestmark = pytest.mark.django_db(transaction=True)


# ============================================
# SUGGEST — CONTRATO DE FUNCIÓN PURA
# ============================================

class TestSuggestIsPure:

    async def test_suggest_does_not_create_categories_as_side_effect(self):
        """
        suggest() nunca escribe en DB independientemente del camino que tome.
        """
        user = await sync_to_async(UserFactory)()

        count_before = await Category.objects.filter(user=user).acount()

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        await sync_to_async(categorizer.suggest)("pizza")

        count_after = await Category.objects.filter(user=user).acount()
        assert count_before == count_after

    async def test_suggest_returns_suggested_category_name_when_no_user_category(self):
        """
        Para un usuario sin historial ni categorías propias,
        suggest() retorna suggested_category_name pero category=None.
        """
        user = await sync_to_async(UserFactory)()

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        suggestion = await sync_to_async(categorizer.suggest)("pizza")

        assert suggestion.category is None
        assert suggestion.suggested_category_name == "Comida"
        assert suggestion.confidence == 0.8

    async def test_suggest_returns_category_object_from_user_history(self):
        """
        Si el usuario tiene historial, suggest() retorna el objeto Category.
        """
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(name="Comida", user=user)
        await sync_to_async(ExpenseFactory)(
            user=user, category=category, description="pizza"
        )

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        suggestion = await sync_to_async(categorizer.suggest)("pizza")

        assert suggestion.category is not None
        assert suggestion.category.id == category.id
        assert suggestion.confidence >= 0.9

    async def test_suggest_returns_no_match_for_unknown_description(self):
        user = await sync_to_async(UserFactory)()

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        suggestion = await sync_to_async(categorizer.suggest)("xyzabc")

        assert suggestion.category is None
        assert suggestion.suggested_category_name is None
        assert suggestion.confidence == 0.0
        assert suggestion.reason == "no_match"


# ============================================
# CONFIDENCE LEVELS
# ============================================

class TestConfidenceLevels:

    async def test_exact_history_match_returns_max_confidence(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(user=user)
        await sync_to_async(ExpenseFactory)(
            user=user, category=category, description="uber"
        )

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        suggestion = await sync_to_async(categorizer.suggest)("uber")

        assert suggestion.confidence == 1.0
        assert suggestion.reason == "user_history"

    async def test_keyword_match_returns_08_confidence(self):
        user = await sync_to_async(UserFactory)()

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        suggestion = await sync_to_async(categorizer.suggest)("pizza")

        assert suggestion.confidence == 0.8
        assert suggestion.reason == "keyword_match"


# ============================================
# GET_CATEGORY_SUGGESTION — HELPER
# ============================================

class TestGetCategorySuggestionHelper:

    async def test_creates_category_when_suggested_name_is_populated(self):
        """
        get_category_suggestion crea la categoría si suggested_category_name
        viene poblado y el usuario no la tiene todavía.
        """
        user = await sync_to_async(UserFactory)()

        count_before = await Category.objects.filter(user=user).acount()

        suggestion = await get_category_suggestion(user, "pizza")

        count_after = await Category.objects.filter(user=user).acount()
        assert count_after == count_before + 1
        assert suggestion.category is not None
        assert suggestion.category.name == "Comida"

    async def test_does_not_duplicate_category_on_repeated_calls(self):
        """
        Llamar dos veces con la misma descripción no crea dos categorías.
        """
        user = await sync_to_async(UserFactory)()

        await get_category_suggestion(user, "pizza")
        await get_category_suggestion(user, "pizza")

        count = await Category.objects.filter(user=user, name="Comida").acount()
        assert count == 1

    async def test_returns_none_category_for_unknown_description(self):
        user = await sync_to_async(UserFactory)()

        suggestion = await get_category_suggestion(user, "xyzabc")

        assert suggestion.category is None
        assert suggestion.confidence == 0.0


# ============================================
# RECORD FEEDBACK
# ============================================

class TestRecordFeedback:

    async def test_creates_feedback_record(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(user=user)
        expense = await sync_to_async(ExpenseFactory)(user=user, category=category)

        count_before = await CategorySuggestionFeedback.objects.acount()

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        await sync_to_async(categorizer.record_feedback)(
            expense=expense,
            suggested_category=category,
            accepted=True,
        )

        count_after = await CategorySuggestionFeedback.objects.acount()
        assert count_after == count_before + 1

    async def test_feedback_is_attached_to_correct_user(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(user=user)
        expense = await sync_to_async(ExpenseFactory)(user=user, category=category)

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        await sync_to_async(categorizer.record_feedback)(
            expense=expense,
            suggested_category=category,
            accepted=True,
        )

        feedback = await CategorySuggestionFeedback.objects.select_related(
            'expense__user'
        ).alatest('created_at')
        assert feedback.expense.user.id == user.id


# ============================================
# CREATE_CATEGORY_FOR_USER
# ============================================

class TestCreateCategoryForUser:

    async def test_creates_category_with_correct_defaults(self):
        user = await sync_to_async(UserFactory)()

        category = await sync_to_async(create_category_for_user)(
            user=user, name="Comida"
        )

        assert category.name == "Comida"
        assert category.user.id == user.id
        assert category.color == "#FF5733"
        assert "pizza" in category.keywords

    async def test_returns_existing_category_without_duplicate(self):
        user = await sync_to_async(UserFactory)()

        cat1 = await sync_to_async(create_category_for_user)(user=user, name="Comida")
        cat2 = await sync_to_async(create_category_for_user)(user=user, name="Comida")

        assert cat1.id == cat2.id
        count = await Category.objects.filter(user=user, name="Comida").acount()
        assert count == 1
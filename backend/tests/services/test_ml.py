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


# ============================================
# GET_ACCUCACY_STATS FROM USER
# ============================================

class TestGetAccuracyStats:

    async def test_returns_zero_accuracy_when_no_feedback(self):
        """
        Un usuario nuevo sin historial de feedback debe recibir
        0.0 de accuracy — no un error ni un division by zero.
        """
        user = await sync_to_async(UserFactory)()

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        stats = await sync_to_async(categorizer.get_accuracy_stats)()

        assert stats["total_suggestions"] == 0
        assert stats["accepted"] == 0
        assert stats["rejected"] == 0
        assert stats["accuracy"] == 0.0
        assert stats["by_category"] == []

    async def test_calculates_global_accuracy_correctly(self):
        """
        2 aceptados de 3 totales → accuracy 0.67.
        Verificamos el cálculo matemático explícitamente.
        """
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(
            name="Comida", user=user, is_default=False
        )

        # Creamos 3 feedbacks: 2 aceptados, 1 rechazado
        for accepted in [True, True, False]:
            expense = await sync_to_async(ExpenseFactory)(
                user=user, category=category
            )
            await sync_to_async(CategorySuggestionFeedback.objects.create)(
                expense=expense,
                suggested_category=category,
                was_accepted=accepted,
                final_category=category,
            )

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        stats = await sync_to_async(categorizer.get_accuracy_stats)()

        assert stats["total_suggestions"] == 3
        assert stats["accepted"] == 2
        assert stats["rejected"] == 1
        assert stats["accuracy"] == 0.67

    async def test_rejected_is_always_total_minus_accepted(self):
        """
        Invariante: rejected = total - accepted.
        Si este invariante falla, las estadísticas son inconsistentes.
        """
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(
            name="Transporte", user=user, is_default=False
        )

        for accepted in [True, False, False, True]:
            expense = await sync_to_async(ExpenseFactory)(
                user=user, category=category
            )
            await sync_to_async(CategorySuggestionFeedback.objects.create)(
                expense=expense,
                suggested_category=category,
                was_accepted=accepted,
                final_category=category,
            )

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        stats = await sync_to_async(categorizer.get_accuracy_stats)()

        assert stats["rejected"] == stats["total_suggestions"] - stats["accepted"]

    async def test_by_category_reflects_per_category_stats(self):
        """
        Las estadísticas por categoría son independientes entre sí.
        Comida con 1/1 y Transporte con 0/1 deben aparecer separadas.
        """
        user = await sync_to_async(UserFactory)()
        cat_comida = await sync_to_async(CategoryFactory)(
            name="Comida", user=user, is_default=False
        )
        cat_transporte = await sync_to_async(CategoryFactory)(
            name="Transporte", user=user, is_default=False
        )

        # Comida: 1 aceptado → accuracy 1.0
        expense_a = await sync_to_async(ExpenseFactory)(
            user=user, category=cat_comida
        )
        await sync_to_async(CategorySuggestionFeedback.objects.create)(
            expense=expense_a,
            suggested_category=cat_comida,
            was_accepted=True,
            final_category=cat_comida,
        )

        # Transporte: 1 rechazado → accuracy 0.0
        expense_b = await sync_to_async(ExpenseFactory)(
            user=user, category=cat_transporte
        )
        await sync_to_async(CategorySuggestionFeedback.objects.create)(
            expense=expense_b,
            suggested_category=cat_transporte,
            was_accepted=False,
            final_category=cat_comida,
        )

        categorizer = await sync_to_async(ExpenseCategorizer)(user)
        stats = await sync_to_async(categorizer.get_accuracy_stats)()

        by_category = {
            item["category_name"]: item
            for item in stats["by_category"]
        }

        assert by_category["Comida"]["accuracy"] == 1.0
        assert by_category["Comida"]["total"] == 1

        assert by_category["Transporte"]["accuracy"] == 0.0
        assert by_category["Transporte"]["total"] == 1
"""
Tests para ExpenseCategorizer.
Coverage objetivo: >90%
"""
from decimal import Decimal

from django.utils import timezone

import pytest

from apps.core.models import Category, CategorySuggestionFeedback, Expense, User
from apps.ml.categorizer import ExpenseCategorizer, TextNormalizer

# ============================================
# FIXTURES
# ============================================


@pytest.fixture
def user(db):
    """Usuario base para tests."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        telegram_id=12345,
    )


@pytest.fixture
def user_with_categories(user):
    """Usuario con categorías creadas (con keywords)."""
    Category.objects.create(
        name="Comida",
        user=user,
        keywords=["pizza", "hamburguesa", "almuerzo", "cafe", "café"],
        color="#FF5733",
    )
    Category.objects.create(
        name="Transporte",
        user=user,
        keywords=["uber", "taxi", "subte", "colectivo", "nafta"],
        color="#3366FF",
    )
    Category.objects.create(
        name="Supermercado",
        user=user,
        keywords=["super", "supermercado", "carrefour", "coto"],
        color="#33FF57",
    )
    Category.objects.create(
        name="Delivery",
        user=user,
        keywords=["rappi", "pedidosya", "delivery"],
        color="#FF33F5",
    )
    return user


@pytest.fixture
def user_with_expenses(user_with_categories):
    """Usuario con expenses previos categorizados."""
    user = user_with_categories
    comida = Category.objects.get(user=user, name="Comida")
    transporte = Category.objects.get(user=user, name="Transporte")

    Expense.objects.create(
        user=user,
        amount=Decimal("2000"),
        description="Pizza con amigos",
        category=comida,
        date=timezone.now(),
    )
    Expense.objects.create(
        user=user,
        amount=Decimal("1500"),
        description="Uber al trabajo",
        category=transporte,
        date=timezone.now(),
    )
    # Usuario categorizó Rappi como Comida (no Delivery)
    Expense.objects.create(
        user=user,
        amount=Decimal("3000"),
        description="Rappi hamburguesas",
        category=comida,
        date=timezone.now(),
    )

    return user


@pytest.fixture
def user_with_feedback(user_with_expenses):
    """Usuario con feedback de sugerencias."""
    user = user_with_expenses
    comida = Category.objects.get(user=user, name="Comida")
    transporte = Category.objects.get(user=user, name="Transporte")

    expenses = Expense.objects.filter(user=user)

    CategorySuggestionFeedback.objects.create(
        expense=expenses[0],
        suggested_category=comida,
        was_accepted=True,
        final_category=comida,
    )
    CategorySuggestionFeedback.objects.create(
        expense=expenses[1],
        suggested_category=transporte,
        was_accepted=True,
        final_category=transporte,
    )
    CategorySuggestionFeedback.objects.create(
        expense=expenses[2],
        suggested_category=Category.objects.get(user=user, name="Delivery"),
        was_accepted=False,
        final_category=comida,
    )

    return user


@pytest.fixture
def global_category(db):
    """Categoría global (sin usuario)."""
    return Category.objects.create(
        name="Servicios",
        is_default=True,
        keywords=["luz", "gas", "agua", "internet", "netflix"],
        color="#999999",
    )


# ============================================
# TESTS DE TEXT NORMALIZER
# ============================================


class TestTextNormalizer:
    """Tests para TextNormalizer."""

    def test_remove_accents(self):
        assert TextNormalizer.remove_accents("café") == "cafe"
        assert TextNormalizer.remove_accents("teléfono") == "telefono"
        assert TextNormalizer.remove_accents("médico") == "medico"

    def test_normalize(self):
        assert TextNormalizer.normalize("  CAFÉ  ") == "cafe"
        assert TextNormalizer.normalize("TELÉFONO") == "telefono"

    def test_extract_significant_words(self):
        words = TextNormalizer.extract_significant_words("Pizza con amigos en el centro")
        assert "pizza" in words
        assert "amigos" in words
        assert "con" not in words
        assert "el" not in words

    def test_extract_significant_words_with_diminutives(self):
        words = TextNormalizer.extract_significant_words("Cafecito con medialunas")
        assert "cafecito" in words


# ============================================
# TESTS DE KEYWORD MATCHING
# ============================================


@pytest.mark.django_db
class TestKeywordMatching:
    """Tests de matching por keywords."""

    def test_keyword_exact_match(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        suggestion = categorizer.suggest("Pizza con amigos")

        assert suggestion.category is not None
        assert suggestion.category.name == "Comida"
        assert suggestion.confidence >= 0.8
        assert suggestion.reason == "keyword_match"

    def test_keyword_exact_match_uber(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        suggestion = categorizer.suggest("Uber al centro")

        assert suggestion.category.name == "Transporte"
        assert suggestion.confidence >= 0.8

    def test_keyword_partial_match(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        suggestion = categorizer.suggest("Compras en supermercado chino")

        assert suggestion.category is not None
        assert suggestion.category.name == "Supermercado"
        assert suggestion.confidence >= 0.6

    def test_no_match_returns_none(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        suggestion = categorizer.suggest("xyz random thing 123")

        assert suggestion.category is None
        assert suggestion.confidence == 0.0
        assert suggestion.reason == "no_match"

    def test_case_insensitive(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)

        s1 = categorizer.suggest("PIZZA")
        s2 = categorizer.suggest("pizza")
        s3 = categorizer.suggest("PiZzA")

        assert s1.category.name == "Comida"
        assert s2.category.name == "Comida"
        assert s3.category.name == "Comida"

    def test_accent_handling(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)

        s1 = categorizer.suggest("cafe con leche")
        s2 = categorizer.suggest("café con leche")

        assert s1.category.name == "Comida"
        assert s2.category.name == "Comida"

    def test_diminutive_handling(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        suggestion = categorizer.suggest("cafecito de la tarde")

        assert suggestion.category is not None
        assert suggestion.category.name == "Comida"


# ============================================
# TESTS DE USER HISTORY
# ============================================


@pytest.mark.django_db
class TestUserHistory:
    """Tests de prioridad del historial del usuario."""

    def test_user_history_exact_match(self, user_with_expenses):
        categorizer = ExpenseCategorizer(user_with_expenses)
        suggestion = categorizer.suggest("Pizza con amigos")

        assert suggestion.category.name == "Comida"
        assert suggestion.confidence == 1.0
        assert suggestion.reason == "user_history"

    def test_user_history_partial_match(self, user_with_expenses):
        categorizer = ExpenseCategorizer(user_with_expenses)
        suggestion = categorizer.suggest("Pizza familiar")

        assert suggestion.category.name == "Comida"
        assert suggestion.confidence >= 0.8
        assert suggestion.reason == "keyword_match"

    def test_user_history_overrides_default_keywords(self, user_with_expenses):
        categorizer = ExpenseCategorizer(user_with_expenses)
        suggestion = categorizer.suggest("Rappi hamburguesas")

        assert suggestion.category.name == "Comida"
        assert suggestion.reason == "user_history"

    def test_no_history_uses_keywords(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        suggestion = categorizer.suggest("Rappi comida")

        assert suggestion.category.name == "Delivery"
        assert suggestion.reason == "keyword_match"


# ============================================
# TESTS DE FEEDBACK
# ============================================


@pytest.mark.django_db
class TestFeedbackRecording:
    """Tests de grabación de feedback."""

    def test_feedback_recording_accepted(self, user_with_categories):
        user = user_with_categories
        comida = Category.objects.get(user=user, name="Comida")

        expense = Expense.objects.create(
            user=user,
            amount=Decimal("500"),
            description="Test expense",
            date=timezone.now(),
        )

        categorizer = ExpenseCategorizer(user)
        feedback = categorizer.record_feedback(
            expense=expense,
            suggested_category=comida,
            accepted=True,
        )

        assert feedback.expense == expense
        assert feedback.suggested_category == comida
        assert feedback.was_accepted is True
        assert feedback.final_category == comida

    def test_feedback_recording_rejected(self, user_with_categories):
        user = user_with_categories
        comida = Category.objects.get(user=user, name="Comida")
        transporte = Category.objects.get(user=user, name="Transporte")

        expense = Expense.objects.create(
            user=user,
            amount=Decimal("500"),
            description="Test expense",
            date=timezone.now(),
        )

        categorizer = ExpenseCategorizer(user)
        feedback = categorizer.record_feedback(
            expense=expense,
            suggested_category=comida,
            accepted=False,
            final_category=transporte,
        )

        assert feedback.was_accepted is False
        assert feedback.suggested_category == comida
        assert feedback.final_category == transporte


# ============================================
# TESTS DE ACCURACY STATS
# ============================================


@pytest.mark.django_db
class TestAccuracyStats:
    """Tests de estadísticas de accuracy."""

    def test_accuracy_stats_calculation(self, user_with_feedback):
        categorizer = ExpenseCategorizer(user_with_feedback)
        stats = categorizer.get_accuracy_stats()

        assert stats["total_suggestions"] == 3
        assert stats["accepted"] == 2
        assert stats["rejected"] == 1
        assert stats["accuracy"] == round(2 / 3, 2)

    def test_accuracy_stats_empty(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        stats = categorizer.get_accuracy_stats()

        assert stats["total_suggestions"] == 0
        assert stats["accepted"] == 0
        assert stats["accuracy"] == 0.0

    def test_accuracy_stats_by_category(self, user_with_feedback):
        categorizer = ExpenseCategorizer(user_with_feedback)
        stats = categorizer.get_accuracy_stats()

        assert "by_category" in stats
        assert len(stats["by_category"]) > 0


# ============================================
# TESTS DE GLOBAL CATEGORIES
# ============================================


@pytest.mark.django_db
class TestGlobalCategories:
    """Tests de categorías globales."""

    def test_user_category_priority_over_global(self, user, global_category):
        Category.objects.create(
            name="Mi Streaming",
            user=user,
            keywords=["netflix", "disney"],
            color="#123456",
        )

        categorizer = ExpenseCategorizer(user)
        suggestion = categorizer.suggest("Netflix mensual")

        assert suggestion.category.name == "Mi Streaming"
        assert suggestion.category.user == user


# ============================================
# EDGE CASES
# ============================================


@pytest.mark.django_db
class TestEdgeCases:
    """Tests de casos extremos."""

    def test_empty_description(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        suggestion = categorizer.suggest("")

        assert suggestion.category is None
        assert suggestion.confidence == 0.0

    def test_only_stopwords(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        suggestion = categorizer.suggest("de la el en con")

        assert suggestion.category is None
        assert suggestion.confidence == 0.0

    def test_whitespace_only(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        suggestion = categorizer.suggest("   ")

        assert suggestion.category is None
        assert suggestion.confidence == 0.0

    def test_numbers_in_description(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        suggestion = categorizer.suggest("2 pizzas grandes")

        assert suggestion.category.name == "Comida"

    def test_special_characters(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        suggestion = categorizer.suggest("Pizza!!! 🍕")

        assert suggestion.category.name == "Comida"

    def test_long_description(self, user_with_categories):
        categorizer = ExpenseCategorizer(user_with_categories)
        long_desc = "Compré una pizza muy grande con muchos ingredientes " * 10 + "pizza"
        suggestion = categorizer.suggest(long_desc)

        assert suggestion.category.name == "Comida"

"""
Helper functions for machine learning.
"""
from asgiref.sync import sync_to_async
from apps.core.models import Category
from services.ml.categorizer import ExpenseCategorizer, create_category_for_user

import logging
logger = logging.getLogger(__name__)


@sync_to_async
def get_category_suggestion(user, description):
    """
    Obtiene sugerencia de categoría para una descripción.
    Si la sugerencia implica crear una categoría nueva, la crea aquí.
    Este es el único lugar donde esa decisión se toma.
    """
    categorizer = ExpenseCategorizer(user)
    suggestion = categorizer.suggest(description)

    # Si el categorizador sugiere un nombre pero no tiene objeto Category,
    # es porque la categoría no existe aún para este usuario.
    # La creamos aquí, una sola vez, explícitamente.
    if suggestion.category is None and suggestion.suggested_category_name:
        suggestion.category = create_category_for_user(
            user=user,
            name=suggestion.suggested_category_name
        )

    logger.info(
        "Category suggestion",
        extra={
            "user_id": user.id,
            "category": suggestion.category.name if suggestion.category else None,
            "confidence": suggestion.confidence,
            "reason": suggestion.reason,
            "matched_keyword": suggestion.matched_keyword,
        }
    )

    return suggestion


@sync_to_async
def is_autocategorized(suggestion, user) -> bool:
    """
    Determina si la confianza es suficiente para auto-categorizar.
    """
    if suggestion.confidence >= 0.8:
        logger.info(
            "Auto-categorized expense",
            extra={
                "user_id": user.id,
                "category": suggestion.category.name if suggestion.category else None,
                "confidence": suggestion.confidence,
            },
        )
        return True
    return False


@sync_to_async
def record_categorization_feedback(expense, suggested_category, accepted: bool, final_category=None):
    """
    Registra feedback de categorización para aprendizaje futuro.
    Debe llamarse en toda corrección de categoría, desde cualquier superficie.
    """
    categorizer = ExpenseCategorizer(expense.user)
    categorizer.record_feedback(
        expense=expense,
        suggested_category=suggested_category,
        accepted=accepted,
        final_category=final_category if not accepted else suggested_category,
    )

    logger.info(
        "Categorization feedback recorded",
        extra={
            "expense_id": expense.id,
            "user_id": expense.user.id,
            "accepted": accepted,
            "suggested": suggested_category.name if suggested_category else None,
            "final": final_category.name if final_category else None,
        }
    )
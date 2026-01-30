"""
Helper functions for machine learning.
"""

from apps.core.models import Expense
from .categorizer import ExpenseCategorizer
from asgiref.sync import sync_to_async

import logging
logger = logging.getLogger(__name__)


@sync_to_async
def record_categorization_feedback(expense, suggested_category, accepted):
    """Helper sincrónico para guardar feedback de categorización."""

    categorizer = ExpenseCategorizer(expense.user)
    categorizer.record_feedback(
        expense=expense,
        suggested_category=suggested_category,
        accepted=accepted,
        final_category=suggested_category if accepted else None,
    )


@sync_to_async
def get_category_suggestion(user, description):
    """Helper sincrónico para obtener sugerencia de categoría."""

    categorizer = ExpenseCategorizer(user)

    # # DEBUG: Ver qué categorías tiene el usuario
    # categories = categorizer._get_user_categories()
    # print(f"[DEBUG] Usuario {user.username} tiene {len(categories)} categorías")
    # for cat in categories:
    #     print(f"  - {cat.name}: keywords={cat.keywords}")

    # # DEBUG: Ver keyword map
    # keyword_map = categorizer._get_keyword_map()
    # print(f"[DEBUG] Keyword map tiene {len(keyword_map)} keywords")
    # print(f"[DEBUG] Primeros 10 keywords: {list(keyword_map.keys())}")

    suggestion = categorizer.suggest(description)

    # DEBUG: Ver resultado
    print(f"[DEBUG] Sugerencia para '{description}':")
    print(f"  - category: {suggestion.category.name if suggestion.category else None}")
    print(f"  - confidence: {suggestion.confidence}")
    print(f"  - reason: {suggestion.reason}")
    print(f"  - matched_keyword: {suggestion.matched_keyword}")

    return suggestion

@sync_to_async
def is_autocategorized(suggestion, user):
    # Determinar categoría basándose en confidence
    auto_categorized = False

    if suggestion.confidence >= 0.8:
        # Alta confianza: auto-categorizar sin preguntar
        category = suggestion.category
        auto_categorized = True
        logger.info(
            "Auto-categorized expense",
            extra={
                "user_id": user.id,
                "category": category.name,
                "confidence": suggestion.confidence,
                "reason": suggestion.reason,
            },
        )
    # else..
    # Still working on this logic

    # TODO: Guardar feedback si se auto-categorizó
    # TODO: Necesito obtener tmb la expense para guardar el feedback
    # if auto_categorized:
    #     await record_categorization_feedback(
    #         expense=expense,
    #         suggested_category=suggestion.category,
    #         accepted=True,
    #     )
    
    return auto_categorized
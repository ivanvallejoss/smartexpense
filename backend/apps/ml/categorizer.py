"""
Categorizador de expenses basado en keywords y aprendizaje del usuario.

Estrategia de matching (en orden de prioridad):
1. Historial del usuario: Si el usuario ya categorizó "pizza" como "Delivery",
   sugerir "Delivery" para futuros "pizza"
2. Keywords exactos: Match directo con keywords de categoría
3. Keywords parciales: Substring matching
4. Sin match: Retornar None con confidence 0
"""
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from django.db.models import Count, Q

from apps.core.models import Category, CategorySuggestionFeedback, Expense, User

from .default_keywords import DEFAULT_CATEGORY_KEYWORDS, SPANISH_STOPWORDS


@dataclass
class CategorySuggestion:
    """Resultado de una sugerencia de categoría."""

    category: Optional[Category]
    confidence: float  # 0.0 a 1.0
    reason: str  # "user_history", "keyword_match", "partial_match", "no_match"
    matched_keyword: Optional[str] = None


class TextNormalizer:
    """
    Utilidades para normalizar texto para matching.
    Maneja acentos, diminutivos y variaciones comunes en español argentino.
    """

    # Sufijos de diminutivos comunes en español
    DIMINUTIVE_SUFFIXES = [
        "ito",
        "ita",
        "itos",
        "itas",
        "cito",
        "cita",
        "citos",
        "citas",
        "illo",
        "illa",
        "illos",
        "illas",
    ]

    @staticmethod
    def remove_accents(text: str) -> str:
        """
        Remueve acentos de un texto.
        "café" -> "cafe", "teléfono" -> "telefono"
        """
        normalized = unicodedata.normalize("NFD", text)
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")

    @classmethod
    def normalize(cls, text: str) -> str:
        """
        Normalización completa de texto:
        1. Lowercase
        2. Remover acentos
        3. Strip espacios
        """
        text = text.lower().strip()
        text = cls.remove_accents(text)
        return text

    @classmethod
    def extract_significant_words(cls, text: str) -> Set[str]:
        """
        Extrae palabras significativas de un texto, ignorando stopwords.
        Retorna tanto la palabra original como su versión sin diminutivo.
        """
        normalized = cls.normalize(text)
        words = re.findall(r"\b[a-z]+\b", normalized)

        significant = set()

        for word in words:
            if word in SPANISH_STOPWORDS or len(word) < 3:
                continue

            significant.add(word)

        return significant


class ExpenseCategorizer:
    """
    Categorizador de expenses basado en keywords y aprendizaje.

    Niveles de confianza:
    - 1.0 (100%): Match exacto en historial del usuario (misma descripción)
    - 0.9 (90%): Match parcial en historial (palabra clave coincide)
    - 0.8 (80%): Match exacto de keyword en categoría
    - 0.6 (60%): Match parcial de keyword (substring)
    - 0.0 (0%): Sin match
    """

    CONFIDENCE_HISTORY_EXACT = 1.0
    CONFIDENCE_HISTORY_PARTIAL = 0.9
    CONFIDENCE_KEYWORD_EXACT = 0.8
    CONFIDENCE_KEYWORD_PARTIAL = 0.6
    CONFIDENCE_NO_MATCH = 0.0

    def __init__(self, user: User):
        self.user = user
        self.normalizer = TextNormalizer()
        self._categories: Optional[List[Category]] = None
        self._keyword_map: Optional[Dict[str, Category]] = None

    def _get_user_categories(self) -> List[Category]:
        """Carga categorías del usuario + globales."""
        if self._categories is None:
            self._categories = list(Category.objects.filter(Q(user=self.user) | Q(is_default=True)).order_by("-user", "name"))
        return self._categories

    def _get_keyword_map(self) -> Dict[str, Category]:
        """
        Construye mapa keyword -> Category para búsqueda rápida.

        Prioridad:
        1. Categorías del usuario (con keywords propios o defaults por nombre)
        2. Categorías globales (solo si keyword no está usado por usuario)
        """
        if self._keyword_map is not None:
            return self._keyword_map

        self._keyword_map = {}

        # 1. Intentamos obtener las categorias del usuario en caso de que exista.
        user_categories = Category.objects.filter(user=self.user)

        for category in user_categories:
            keywords = category.keywords or []

            # Fallback a defaults si no tiene keywords propios
            if not keywords and category.name in DEFAULT_CATEGORY_KEYWORDS:
                keywords = DEFAULT_CATEGORY_KEYWORDS[category.name]

            for keyword in keywords:
                self._keyword_map[keyword] = category

        return self._keyword_map

    def suggest(self, description: str) -> CategorySuggestion:
        """Sugiere categoría para una descripción."""
        if not description or not description.strip():
            return CategorySuggestion(
                category=None,
                confidence=self.CONFIDENCE_NO_MATCH,
                reason="no_match",
            )

        description_normalized = self.normalizer.normalize(description)
        description_words = self.normalizer.extract_significant_words(description)

        # 1. Buscar en historial del usuario
        suggestion = self._check_user_history(description_normalized, description_words)
        if suggestion and suggestion.confidence >= self.CONFIDENCE_HISTORY_PARTIAL:
            return suggestion

        # 2. Buscar en keywords
        suggestion = self._check_keywords(description_words)
        if suggestion:
            return suggestion

        # 3. No match
        return CategorySuggestion(
            category=None,
            confidence=self.CONFIDENCE_NO_MATCH,
            reason="no_match",
        )

    def _check_user_history(self, description_normalized: str, description_words: Set[str]) -> Optional[CategorySuggestion]:
        """Busca en historial de expenses del usuario."""
        past_expenses = Expense.objects.filter(user=self.user, category__isnull=False).exclude(description="").select_related("category").order_by("-date")[:100]

        if not past_expenses:
            return None

        best_match: Optional[CategorySuggestion] = None

        for expense in past_expenses:
            # POR QUE NROMALIZO UN TEXTO YA GUARDADO
            past_normalized = self.normalizer.normalize(expense.description)
            past_words = self.normalizer.extract_significant_words(expense.description)

            # Match exacto 100%
            if description_normalized == past_normalized:
                return CategorySuggestion(
                    category=expense.category,
                    confidence=self.CONFIDENCE_HISTORY_EXACT,
                    reason="user_history",
                    matched_keyword=expense.description,
                )

            # Match parcial
            # Estamos haciendo una interseccion de sets
            common_words = description_words & past_words
            if common_words and len(common_words) >= 1:
                # Chequeamos el porcentaje de match que existe entre la interseccion de sets y la cantidad de palabras en la descripcion actual
                overlap_ratio = len(common_words) / max(len(description_words), 1)  # overlap_ratio = %

                # Buscamos un overlap_ratio >= 0.5 para comenzar a comparar o, utilizar desde la historia del usuario.
                if overlap_ratio >= 0.5:
                    suggestion = CategorySuggestion(
                        category=expense.category,
                        # Utilzamos el match entre la descipcion y el historico para marcar el grado de confianza en el match
                        confidence=overlap_ratio,
                        reason="user_history",
                        matched_keyword=list(common_words)[0],
                    )

                    if best_match is None or suggestion.confidence > best_match.confidence:
                        best_match = suggestion

        return best_match

    def _check_keywords(self, description_words: Set[str]) -> Optional[CategorySuggestion]:
        """
        Match con keywords de categorías.
        Si el usuario no tiene la categoría, la crea automáticamente.
        """
        keyword_map = self._get_keyword_map()

        # 1. Match exacto
        for word in description_words:
            if word in keyword_map:
                return CategorySuggestion(
                    category=keyword_map[word],
                    confidence=self.CONFIDENCE_KEYWORD_EXACT,
                    reason="keyword_match",
                    matched_keyword=word,
                )

        # 2. Match parcial
        for keyword, category in keyword_map.items():
            for word in description_words:
                # Hacemos busqueda parcial de una palabra dentro de la otra
                # Cubre casos de abreviaciones en la descripcion.
                if keyword in word or word in keyword:
                    return CategorySuggestion(
                        category=category,
                        confidence=self.CONFIDENCE_KEYWORD_PARTIAL,
                        reason="partial_match",
                        matched_keyword=keyword,
                    )

        # 3. Si no hay match buscar en DEFAULT_CATEGORY_KEYWORDS y auto-crear
        # Antes solo sucedia si no existian categorias dentro del usuario pero, evitaba crear cualquier otra categoria.
        return self._check_and_create_from_defaults(description_words)

    def record_feedback(
        self,
        expense: Expense,
        suggested_category: Optional[Category],
        accepted: bool,
        final_category: Optional[Category] = None,
    ) -> CategorySuggestionFeedback:
        """Guarda feedback para aprendizaje futuro."""
        if accepted and final_category is None:
            final_category = suggested_category

        feedback = CategorySuggestionFeedback.objects.create(
            expense=expense,
            suggested_category=suggested_category,
            was_accepted=accepted,
            final_category=final_category,
        )

        return feedback

    def get_accuracy_stats(self) -> Dict:
        """Retorna estadísticas de accuracy del categorizador."""
        feedbacks = CategorySuggestionFeedback.objects.filter(expense__user=self.user)

        total = feedbacks.count()
        accepted = feedbacks.filter(was_accepted=True).count()
        rejected = total - accepted

        accuracy = accepted / total if total > 0 else 0.0

        by_category = (
            feedbacks.values("suggested_category__name")
            .annotate(
                total=Count("id"),
                accepted_count=Count("id", filter=Q(was_accepted=True)),
            )
            .order_by("-total")
        )

        category_stats = []
        for item in by_category:
            cat_name = item["suggested_category__name"] or "Sin categoría"
            cat_total = item["total"]
            cat_accepted = item["accepted_count"]
            cat_accuracy = cat_accepted / cat_total if cat_total > 0 else 0.0

            category_stats.append(
                {
                    "category_name": cat_name,
                    "total": cat_total,
                    "accepted": cat_accepted,
                    "accuracy": round(cat_accuracy, 2),
                }
            )

        return {
            "total_suggestions": total,
            "accepted": accepted,
            "rejected": rejected,
            "accuracy": round(accuracy, 2),
            "by_category": category_stats,
        }

    def _check_and_create_from_defaults(self, description_words: Set[str]) -> Optional[CategorySuggestion]:
        """
        Busca en DEFAULT_CATEGORY_KEYWORDS y auto-crea la categoría para el usuario.
        Solo se ejecuta si el usuario NO tiene categorías propias.
        """
        # Colores por defecto para cada categoría
        DEFAULT_COLORS = {
            "Comida": "#FF5733",
            "Supermercado": "#33FF57",
            "Transporte": "#3366FF",
            "Delivery": "#FF33F5",
            "Servicios": "#FFC300",
            "Salud": "#F38181",
            "Entretenimiento": "#C70039",
            "Ropa": "#900C3F",
            "Hogar": "#581845",
            "Educación": "#1E8449",
        }

        # Buscar match en DEFAULT_CATEGORY_KEYWORDS
        for category_name, keywords in DEFAULT_CATEGORY_KEYWORDS.items():
            # 1. Match exacto
            for word in description_words:
                if word in keywords:
                    # AUTO-CREAR categoría para el usuario
                    category = self._create_user_category(
                        name=category_name,
                        keywords=keywords,
                        color=DEFAULT_COLORS.get(category_name, "#6B7280"),
                    )

                    # Invalidar cache para que la use inmediatamente
                    self._keyword_map = None
                    self._categories = None

                    return CategorySuggestion(
                        category=category,
                        confidence=self.CONFIDENCE_KEYWORD_EXACT,
                        reason="keyword_match",
                        matched_keyword=word,
                    )

            # 2. Match parcial (substring)
            for keyword in keywords:
                for word in description_words:
                    if keyword in word or word in keyword:
                        category = self._create_user_category(
                            name=category_name,
                            keywords=keywords,
                            color=DEFAULT_COLORS.get(category_name, "#6B7280"),
                        )

                        self._keyword_map = None
                        self._categories = None

                        return CategorySuggestion(
                            category=category,
                            confidence=self.CONFIDENCE_KEYWORD_PARTIAL,
                            reason="partial_match",
                            matched_keyword=keyword,
                        )

        return None

    def _create_user_category(self, name: str, keywords: List[str], color: str) -> Category:
        """
        Crea una categoría para el usuario si no existe.
        """
        category, created = Category.objects.get_or_create(
            name=name,
            user=self.user,
            defaults={
                "keywords": keywords,
                "color": color,
            },
        )

        if created:
            # Log para debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Auto-created category '{name}' for user {self.user.username} " f"with {len(keywords)} keywords")

        return category

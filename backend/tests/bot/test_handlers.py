"""
Tests de integración de los handlers, ya agnósticos al canal.
Cubre los tres caminos de handle_message y los comandos principales.
"""
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from django.utils import timezone

from apps.bot.handlers.handlers import (
    start_command, help_command, stats_command,
    history_command, link_command, handle_message
)
from apps.core.models import User, Category, Expense

from tests.constants import EXTERNAL_USER_ID

pytestmark = pytest.mark.django_db(transaction=True)


def make_suggestion(confidence, category=None, suggested_name=None):
    """Mock de CategorySuggestion con el nivel de confianza deseado."""
    suggestion = MagicMock()
    suggestion.confidence = confidence
    suggestion.category = category
    suggestion.suggested_category_name = suggested_name
    return suggestion


# ============================================
# COMANDOS BÁSICOS
# ============================================

class TestBasicCommands:

    async def test_start_replies_with_welcome(self, make_event, user, sender):
        """
        El handler ya no crea el usuario: eso lo hace el router (Fase 4b).
        Acá solo se verifica la respuesta.
        """
        await start_command(make_event("/start"), user, sender)

        assert len(sender.replies) == 1
        assert "Bienvenido a SmartExpense" in sender.last_reply["text"]

    async def test_help_replies_with_formats(self, make_event, user, sender):
        await help_command(make_event("/help"), user, sender)

        assert len(sender.replies) == 1
        assert "Formatos soportados" in sender.last_reply["text"]

    @patch("apps.bot.handlers.handlers.get_month_stats")
    async def test_stats_shows_month_summary(self, mock_stats, make_event, user, sender):
        mock_stats.return_value = {
            "month_name": "Marzo 2026",
            "total_amount": Decimal("1500"),
            "total_count": 1,
            "by_category": []
        }

        await stats_command(make_event("/stats"), user, sender)

        assert "Resumen de Marzo 2026" in sender.last_reply["text"]

    @patch("apps.bot.handlers.handlers.get_month_stats")
    async def test_stats_failure_shows_friendly_error(
        self, mock_stats, make_event, user, sender
    ):
        mock_stats.side_effect = Exception("Fallo de DB")

        await stats_command(make_event("/stats"), user, sender)

        assert "Ocurrió un error al obtener las estadísticas" in sender.last_reply["text"]

    async def test_history_no_expenses(self, make_event, user, sender):
        """
        Manda DOS mensajes cuando no hay gastos: es un bug preexistente
        (falta un return) que este refactor preserva a propósito.
        """
        await history_command(make_event("/history"), user, sender)

        assert len(sender.replies) == 2
        assert "No encontramos gastos" in sender.replies[0]["text"]
        assert "No tienes gastos registrados" in sender.replies[1]["text"]

    async def test_history_parses_limit_from_command_args(
        self, make_event, user, sender
    ):
        """Reemplaza a context.args de PTB."""
        with patch("apps.bot.handlers.handlers.get_expenses") as mock_get:
            mock_get.return_value = []
            await history_command(make_event("/history 15"), user, sender)

        assert mock_get.await_args.args[1] == 15

    async def test_history_caps_limit_at_22(self, make_event, user, sender):
        with patch("apps.bot.handlers.handlers.get_expenses") as mock_get:
            mock_get.return_value = []
            await history_command(make_event("/history 999"), user, sender)

        assert mock_get.await_args.args[1] == 22

    async def test_history_uses_html_parse_mode(self, make_event, user, sender):
        await history_command(make_event("/history"), user, sender)
        assert sender.last_reply["parse_mode"] == "HTML"

    @patch("apps.bot.handlers.handlers.generate_magic_link_token")
    async def test_link_contains_token(self, mock_token, make_event, user, sender):
        mock_token.return_value = "token-secreto-123"

        await link_command(make_event("/link"), user, sender)

        respuesta = sender.last_reply["text"]
        assert "token-secreto-123" in respuesta
        assert "Ir al dashboard" in respuesta
        assert mock_token.call_args.kwargs == {"user_id": user.id}


# ============================================
# HANDLE MESSAGE — TRES CAMINOS
# ============================================

class TestHandleMessageThreePaths:

    @patch("apps.bot.handlers.handlers.get_category_suggestion")
    async def test_high_confidence_autocategorizes(
        self, mock_suggestion, make_event, user, sender
    ):
        category = await Category.objects.acreate(name="Comida", is_default=True)
        mock_suggestion.return_value = make_suggestion(confidence=1.0, category=category)

        await handle_message(make_event("Pizza 2000"), user, sender)

        expense = await Expense.objects.select_related("category").afirst()
        assert expense is not None
        assert expense.status == Expense.STATUS_CONFIRMED
        assert expense.amount == Decimal("2000")
        assert expense.category.id == category.id

        assert sender.callback_ids(sender.last_reply) == [f"del:{expense.id}"]

    @patch("apps.bot.handlers.handlers.get_category_suggestion")
    async def test_medium_confidence_asks_for_confirmation(
        self, mock_suggestion, make_event, user, sender
    ):
        category = await Category.objects.acreate(name="Comida", is_default=True)
        mock_suggestion.return_value = make_suggestion(confidence=0.6, category=category)

        await handle_message(make_event("Comi algo 500"), user, sender)

        expense = await Expense.objects.select_related("category").afirst()
        assert expense is not None
        assert expense.status == Expense.STATUS_CONFIRMED
        assert expense.category.id == category.id

        assert "¿La categoría es correcta?" in sender.last_reply["text"]

        ids = sender.callback_ids(sender.last_reply)
        assert any("cat_confirm" in cb for cb in ids)
        assert any("cat_list" in cb for cb in ids)

    @patch("apps.bot.handlers.handlers.get_category_suggestion")
    async def test_low_confidence_saves_as_pending(
        self, mock_suggestion, make_event, user, sender
    ):
        mock_suggestion.return_value = make_suggestion(confidence=0.0, category=None)

        await handle_message(make_event("xyzabc 1000"), user, sender)

        expense = await Expense.objects.afirst()
        assert expense is not None
        assert expense.status == Expense.STATUS_PENDING
        assert expense.category is None

        assert "A qué categoría pertenece" in sender.last_reply["text"]
        assert any("cat_new" in cb for cb in sender.callback_ids(sender.last_reply))


# ============================================
# HANDLE MESSAGE — ESTADO PENDIENTE EN REDIS
# ============================================

class TestHandleMessagePendingState:

    async def test_pending_state_triggers_category_creation_flow(
        self, make_event, user, sender, mock_redis_state
    ):
        expense = await Expense.objects.acreate(
            user=user,
            amount=1000,
            description="xyzabc",
            date=timezone.now(),
            status=Expense.STATUS_PENDING,
            category=None,
        )

        mock_redis_state["get"].return_value = expense.id

        await handle_message(make_event("Mascotas"), user, sender)

        # El estado se limpia con el id del canal, ya como string
        mock_redis_state["clear"].assert_called_once_with("telegram", EXTERNAL_USER_ID)

        expense = await Expense.objects.select_related("category").aget(id=expense.id)
        assert expense.status == Expense.STATUS_CONFIRMED
        assert expense.category is not None
        assert expense.category.name == "Mascotas"

    async def test_empty_category_name_shows_error_and_keeps_state(
        self, make_event, user, sender, mock_redis_state
    ):
        """Nombre vacío o muy largo: no se limpia el estado y se avisa."""
        mock_redis_state["get"].return_value = 999

        await handle_message(make_event("a" * 101), user, sender)

        assert "entre 1 y 100 caracteres" in sender.last_reply["text"]
        mock_redis_state["clear"].assert_not_called()

    async def test_redis_caido_no_rompe_el_flujo(
        self, make_event, user, sender, mock_redis_state
    ):
        """Si Redis no responde, el mensaje se procesa como gasto normal."""
        mock_redis_state["get"].side_effect = Exception("Redis connection refused")

        await handle_message(make_event("Pizza 2000"), user, sender)

        assert await Expense.objects.acount() == 1


# ============================================
# HANDLE MESSAGE — EXCEPCIONES
# ============================================

class TestHandleMessageExceptions:

    async def test_invalid_message_format_shows_error(self, make_event, user, sender):
        await handle_message(make_event("Hola bot cómo estás"), user, sender)

        assert await Expense.objects.acount() == 0
        assert "No pude detectar el monto" in sender.last_reply["text"]

    @patch("apps.bot.handlers.handlers.get_category_suggestion")
    async def test_db_failure_shows_friendly_error(
        self, mock_suggestion, make_event, user, sender
    ):
        mock_suggestion.side_effect = Exception("Fallo de DB")

        await handle_message(make_event("Pizza 2000"), user, sender)

        assert "Ocurrió un error al guardar tu gasto" in sender.last_reply["text"]
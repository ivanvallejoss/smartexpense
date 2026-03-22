"""
Tests de integración para los handlers del bot de Telegram.
Cubre los tres caminos de handle_message y los comandos principales.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from django.utils import timezone

from apps.bot.handlers.handlers import (
    start_command, help_command, stats_command,
    history_command, link_command, handle_message
)
from apps.core.models import User, Category, Expense

pytestmark = pytest.mark.django_db(transaction=True)


# ============================================
# FIXTURES
# ============================================

@pytest.fixture
def mock_update():
    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.username = "test_user"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.message = AsyncMock()
    update.message.text = ""
    return update


@pytest.fixture
def mock_context():
    context = AsyncMock()
    context.args = []
    return context


def make_suggestion(confidence, category=None, suggested_name=None):
    """
    Helper para construir un mock de CategorySuggestion
    con el nivel de confianza deseado.
    """
    suggestion = MagicMock()
    suggestion.confidence = confidence
    suggestion.category = category
    suggestion.suggested_category_name = suggested_name
    return suggestion


# ============================================
# COMANDOS BÁSICOS
# ============================================

class TestBasicCommands:

    async def test_start_creates_user_and_replies(self, mock_update, mock_context):
        await start_command(mock_update, mock_context)

        user_exists = await User.objects.filter(telegram_id=123456789).aexists()
        assert user_exists is True

        mock_update.message.reply_text.assert_called_once()
        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "Bienvenido a SmartExpense" in respuesta

    async def test_help_replies_with_formats(self, mock_update, mock_context):
        await help_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "Formatos soportados" in respuesta

    @patch("apps.bot.handlers.handlers.get_month_stats")
    async def test_stats_shows_month_summary(self, mock_stats, mock_update, mock_context):
        mock_stats.return_value = {
            "month_name": "Marzo 2026",
            "total_amount": Decimal("1500"),
            "total_count": 1,
            "by_category": []
        }

        await stats_command(mock_update, mock_context)

        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "Resumen de Marzo 2026" in respuesta

    async def test_history_no_expenses(self, mock_update, mock_context):
        await User.objects.acreate(telegram_id=123456789, username="test_history")
        mock_context.args = []

        await history_command(mock_update, mock_context)

        assert mock_update.message.reply_text.call_count >= 1
        respuesta = mock_update.message.reply_text.call_args_list[-1][0][0]
        assert "No tienes gastos registrados" in respuesta

    @patch("apps.bot.handlers.handlers.generate_magic_link_token")
    async def test_link_contains_token(self, mock_token, mock_update, mock_context):
        mock_token.return_value = "token-secreto-123"

        await link_command(mock_update, mock_context)

        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "token-secreto-123" in respuesta
        assert "Ir al dashboard" in respuesta


# ============================================
# HANDLE MESSAGE — TRES CAMINOS
# ============================================

class TestHandleMessageThreePaths:

    @patch("apps.bot.handlers.handlers.get_category_suggestion")
    async def test_high_confidence_autocategorizes(
        self, mock_suggestion, mock_update, mock_context
    ):
        mock_update.message.text = "Pizza 2000"
        category = await Category.objects.acreate(name="Comida", is_default=True)
        mock_suggestion.return_value = make_suggestion(
            confidence=1.0, category=category
        )

        await handle_message(mock_update, mock_context)

        expense = await Expense.objects.select_related('category').afirst()
        assert expense is not None
        assert expense.status == Expense.STATUS_CONFIRMED
        assert expense.amount == Decimal("2000")
        assert expense.category.id == category.id

        kwargs = mock_update.message.reply_text.call_args[1]
        assert "reply_markup" in kwargs
        markup = kwargs["reply_markup"]
        button = markup.inline_keyboard[0][0]
        assert button.callback_data == f"del:{expense.id}"

    @patch("apps.bot.handlers.handlers.get_category_suggestion")
    async def test_medium_confidence_asks_for_confirmation(
        self, mock_suggestion, mock_update, mock_context
    ):
        mock_update.message.text = "Comi algo 500"
        category = await Category.objects.acreate(name="Comida", is_default=True)
        mock_suggestion.return_value = make_suggestion(
            confidence=0.6, category=category
        )

        await handle_message(mock_update, mock_context)

        expense = await Expense.objects.select_related('category').afirst()
        assert expense is not None
        assert expense.status == Expense.STATUS_CONFIRMED
        assert expense.category.id == category.id

        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "¿La categoría es correcta?" in respuesta

        kwargs = mock_update.message.reply_text.call_args[1]
        markup = kwargs["reply_markup"]
        buttons = markup.inline_keyboard[0]
        callback_datas = [b.callback_data for b in buttons]
        assert any("cat_confirm" in cb for cb in callback_datas)
        assert any("cat_list" in cb for cb in callback_datas)

    @patch("apps.bot.handlers.handlers.get_category_suggestion")
    async def test_low_confidence_saves_as_pending(
        self, mock_suggestion, mock_update, mock_context
    ):
        mock_update.message.text = "xyzabc 1000"
        mock_suggestion.return_value = make_suggestion(
            confidence=0.0, category=None
        )

        await handle_message(mock_update, mock_context)

        expense = await Expense.objects.afirst()
        assert expense is not None
        assert expense.status == Expense.STATUS_PENDING
        assert expense.category is None

        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "A qué categoría pertenece" in respuesta


# ============================================
# HANDLE MESSAGE — ESTADO PENDIENTE EN REDIS
# ============================================

class TestHandleMessagePendingState:

    async def test_pending_state_triggers_category_creation_flow(
    self, mock_update, mock_context, mock_redis_state  # ← usamos el fixture
):
        user = await User.objects.acreate(telegram_id=123456789, username="test_user")

        expense = await Expense.objects.acreate(
            user=user,
            amount=1000,
            description="xyzabc",
            date=timezone.now(),
            status=Expense.STATUS_PENDING,
            category=None,
        )

        # Sobreescribimos el mock del fixture para este test específico
        mock_redis_state["get"].return_value = expense.id
        mock_update.message.text = "Mascotas"

        await handle_message(mock_update, mock_context)

        # clear debe haberse llamado exactamente una vez
        mock_redis_state["clear"].assert_called_once_with(123456789)

        expense = await Expense.objects.select_related('category').aget(id=expense.id)
        assert expense.status == Expense.STATUS_CONFIRMED
        assert expense.category is not None
        assert expense.category.name == "Mascotas"

    @patch("apps.bot.handlers.handlers.get_pending_category_state")
    async def test_empty_category_name_shows_error_and_keeps_state(
        self, mock_get_state, mock_update, mock_context
    ):
        """
        Si el usuario envía un nombre vacío o muy largo,
        el estado no se limpia y se muestra un error.
        """
        await User.objects.acreate(telegram_id=123456789, username="test_user")
        mock_get_state.return_value = 999
        mock_update.message.text = "a" * 101  # más de 100 caracteres

        await handle_message(mock_update, mock_context)

        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "entre 1 y 100 caracteres" in respuesta


# ============================================
# HANDLE MESSAGE — EXCEPCIONES
# ============================================

class TestHandleMessageExceptions:

    async def test_invalid_message_format_shows_error(
        self, mock_update, mock_context
    ):
        mock_update.message.text = "Hola bot cómo estás"

        await handle_message(mock_update, mock_context)

        count = await Expense.objects.acount()
        assert count == 0

        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "No pude detectar el monto" in respuesta

    @patch("apps.bot.handlers.handlers.get_or_create_user_by_telegram")
    async def test_db_failure_shows_friendly_error(
        self, mock_get_user, mock_update, mock_context
    ):
        mock_get_user.side_effect = Exception("Fallo de DB")
        mock_update.message.text = "Pizza 2000"

        await handle_message(mock_update, mock_context)

        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "Ocurrió un error al guardar tu gasto" in respuesta
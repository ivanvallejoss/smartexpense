"""
Tests para los handlers del bot de Telegram.
"""
import logging
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

from django.utils import timezone

import pytest
from asgiref.sync import sync_to_async

from apps.bot.handlers import handle_message, help_command, start_command, stats_command
from apps.core.models import Category, Expense, User


@pytest.fixture
def mock_update():
    """Fixture para mock de Telegram Update."""
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.message = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Fixture para mock de ContextTypes."""
    context = Mock()
    return context


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestStartCommand:
    """Tests para /start command."""

    async def test_creates_user_if_not_exists(self, mock_update, mock_context, caplog):
        """Test que /start crea un nuevo usuario si no existe."""
        caplog.set_level(logging.ERROR)

        # Verificar que no existe - WRAPPED
        exists = await sync_to_async(User.objects.filter(telegram_id=12345).exists)()
        assert not exists

        # Ejecutar comando
        await start_command(mock_update, mock_context)

        # Verificar que se creó el usuario - WRAPPED
        user = await sync_to_async(User.objects.get)(telegram_id=12345)
        assert user.username == "testuser"
        assert user.first_name == "Test"

        # Verificar que se envió mensaje
        mock_update.message.reply_text.assert_called_once()
        args = mock_update.message.reply_text.call_args[0]
        assert "Bienvenido" in args[0]

    async def test_does_not_duplicate_existing_user(self, mock_update, mock_context):
        """Test que /start no duplica usuario si ya existe."""
        # Crear usuario existente - WRAPPED
        await sync_to_async(User.objects.create)(telegram_id=12345, username="existing", first_name="Existing")

        initial_count = await sync_to_async(User.objects.count)()

        # Ejecutar comando
        await start_command(mock_update, mock_context)

        # Verificar que no se duplicó - WRAPPED
        final_count = await sync_to_async(User.objects.count)()
        assert final_count == initial_count

        user_count = await sync_to_async(User.objects.filter(telegram_id=12345).count)()
        assert user_count == 1

        # Verificar mensaje enviado
        mock_update.message.reply_text.assert_called_once()

    async def test_handles_error_gracefully(self, mock_update, mock_context):
        """Test que /start maneja errores correctamente."""
        # Forzar error en get_or_create
        with patch("apps.bot.handlers.get_or_create_user_from_telegram") as mock_get:
            mock_get.side_effect = Exception("Database error")

            await start_command(mock_update, mock_context)

            # Verificar mensaje de error
            mock_update.message.reply_text.assert_called_once()
            args = mock_update.message.reply_text.call_args[0]
            assert "error" in args[0]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestHelpCommand:
    """Tests para /help command."""

    async def test_sends_help_message(self, mock_update, mock_context):
        """Test que /help envía mensaje de ayuda."""
        await help_command(mock_update, mock_context)

        # Verificar mensaje
        mock_update.message.reply_text.assert_called_once()
        args = mock_update.message.reply_text.call_args[0]
        assert "Formatos soportados" in args[0]
        assert "/stats" in args[0]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestStatsCommand:
    """Tests para /stats command."""

    async def test_shows_stats_with_expenses(self, mock_update, mock_context):
        """Test que /stats muestra estadísticas correctas."""
        # Crear usuario y expenses - TODO WRAPPED
        user = await sync_to_async(User.objects.create)(telegram_id=12345, username="testuser", first_name="Test")

        category = await sync_to_async(Category.objects.create)(name="Comida")

        await sync_to_async(Expense.objects.create)(user=user, amount=Decimal("2000"), description="Pizza", category=category, date=timezone.now())

        await sync_to_async(Expense.objects.create)(user=user, amount=Decimal("1500"), description="Café", date=timezone.now())

        await stats_command(mock_update, mock_context)

        # Verificar mensaje
        mock_update.message.reply_text.assert_called_once()
        args = mock_update.message.reply_text.call_args[0]
        assert "$3.500" in args[0]  # Total
        assert "2" in args[0]  # Count

    async def test_handles_no_expenses(self, mock_update, mock_context, caplog):
        """Test que /stats maneja caso sin expenses."""
        from datetime import datetime

        caplog.set_level(logging.ERROR)
        # Crear usuario sin expenses - WRAPPED
        await sync_to_async(User.objects.create)(telegram_id=12345, username="testuser", first_name="Test")
        # Mock de timezone.now() para asegurar fecha consistente
        with patch("apps.bot.handlers.timezone.now") as mock_now:
            mock_now.return_value = timezone.make_aware(datetime(2024, 11, 20, 12, 0, 0))

            await stats_command(mock_update, mock_context)

        if caplog.records:
            for record in caplog.records:
                print(f"\nERROR: {record.message}")
                if hasattr(record, "exc_info") and record.exc_info:
                    import traceback

                    print("".join(traceback.format_exception(*record.exc_info)))

        # Verificar mensaje
        mock_update.message.reply_text.assert_called_once()
        args = mock_update.message.reply_text.call_args[0]
        assert "No tenés gastos" in args[0]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestHandleMessage:
    """Tests para handler de mensajes normales."""

    async def test_saves_valid_expense(self, mock_update, mock_context):
        """Test que mensaje válido guarda expense correctamente."""
        # Crear usuario - WRAPPED
        user = await sync_to_async(User.objects.create)(telegram_id=12345, username="testuser", first_name="Test")

        # Mensaje válido
        mock_update.message.text = "Pizza 2000"

        await handle_message(mock_update, mock_context)

        # Verificar que se guardó - WRAPPED
        expense = await sync_to_async(Expense.objects.get)(user=user)
        assert expense.amount == Decimal("2000")
        assert expense.description == "Pizza"

        # Verificar confirmación
        mock_update.message.reply_text.assert_called_once()
        args = mock_update.message.reply_text.call_args[0]
        assert "$2.000" in args[0]

    async def test_handles_invalid_format(self, mock_update, mock_context):
        """Test que mensaje inválido devuelve error amigable."""
        # Crear usuario - WRAPPED
        await sync_to_async(User.objects.create)(telegram_id=12345, username="testuser", first_name="Test")

        # Mensaje inválido
        mock_update.message.text = "esto no es un expense"

        await handle_message(mock_update, mock_context)

        # Verificar que no se guardó - WRAPPED
        count = await sync_to_async(Expense.objects.count)()
        assert count == 0

        # Verificar mensaje de error
        mock_update.message.reply_text.assert_called_once()
        args = mock_update.message.reply_text.call_args[0]
        assert "No pude detectar" in args[0]

    async def test_associates_expense_to_correct_user(self, mock_update, mock_context):
        """Test que expense se asocia al usuario correcto."""
        # Crear dos usuarios - WRAPPED
        user1 = await sync_to_async(User.objects.create)(telegram_id=12345, username="user1", first_name="User1")
        user2 = await sync_to_async(User.objects.create)(telegram_id=67890, username="user2", first_name="User2")

        # Mensaje de user1
        mock_update.effective_user.id = 12345
        mock_update.message.text = "Pizza 2000"

        await handle_message(mock_update, mock_context)

        # Verificar asociación correcta - WRAPPED
        expense = await sync_to_async(Expense.objects.get)()

        # Comparar IDs en lugar de objetos directamente
        assert expense.user_id == user1.id
        assert expense.user_id != user2.id

    async def test_handles_parser_exception(self, mock_update, mock_context):
        """Test que maneja excepciones del parser."""
        # Crear usuario - WRAPPED
        await sync_to_async(User.objects.create)(telegram_id=12345, username="testuser", first_name="Test")

        mock_update.message.text = "Pizza 2000"

        # Forzar error en parser
        with patch("apps.bot.handlers.ExpenseParser") as MockParser:
            MockParser.return_value.parse.side_effect = Exception("Parser error")

            await handle_message(mock_update, mock_context)

            # Verificar que no se guardó - WRAPPED
            count = await sync_to_async(Expense.objects.count)()
            assert count == 0

            # Verificar mensaje de error
            mock_update.message.reply_text.assert_called_once()
            args = mock_update.message.reply_text.call_args[0]
            assert "error" in args[0]

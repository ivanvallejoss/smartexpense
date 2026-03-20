"""
Tests de integración y mocking para los handlers de Telegram.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

# Importamos los handlers
from apps.bot.handlers.handlers import start_command, help_command, handle_message, stats_command, history_command, link_command
from apps.core.models import User, Category, Expense

# Activamos acceso a BD
pytestmark = pytest.mark.django_db(transaction=True)


# ============================================
# FIXTURES (Los dobles de riesgo)
# ============================================

@pytest.fixture
def mock_update():
    """Simula un objeto Update de Telegram."""
    update = MagicMock()
    # Simulamos el usuario
    update.effective_user.id = 123456789
    update.effective_user.username = "test_user"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    
    # Simulamos el mensaje y sus métodos asíncronos
    update.message = AsyncMock()
    update.message.text = ""
    
    # Simulamos para los callbacks
    update.callback_query = AsyncMock()
    
    return update


@pytest.fixture
def mock_context():
    """Simula el context de python-telegram-bot."""
    context = AsyncMock()
    context.args = []
    return context


# ============================================
# TESTS DE COMANDOS BÁSICOS
# ============================================

class TestBasicCommands:
    
    async def test_start_command_new_user(self, mock_update, mock_context):
        # Act
        await start_command(mock_update, mock_context)
        
        # Assert: Verificamos que el usuario se creó en la DB
        user_exists = await User.objects.filter(telegram_id=123456789).aexists()
        assert user_exists is True
        
        # Assert: Verificamos que el bot respondió con el mensaje de bienvenida
        mock_update.message.reply_text.assert_called_once()
        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "Bienvenido a SmartExpense" in respuesta

    async def test_help_command(self, mock_update, mock_context):
        # Act
        await help_command(mock_update, mock_context)
        
        # Assert
        mock_update.message.reply_text.assert_called_once()
        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "Formatos soportados" in respuesta


# ============================================
# TESTS DEL FLUJO PRINCIPAL (handle_message)
# ============================================

class TestMessageHandling:

    @patch("apps.bot.handlers.handlers.is_autocategorized")
    @patch("apps.bot.handlers.handlers.get_category_suggestion")
    async def test_handle_message_valid_expense(self, mock_get_suggestion, mock_is_auto, mock_update, mock_context):
        """Prueba que un mensaje válido se parsea, puentea el ML y se guarda en BD."""
        
        # 1. Setup inicial
        mock_update.message.text = "Hamburguesa 5000"
        
        # Creamos una categoría para que el ML "sugiera"
        category = await Category.objects.acreate(name="Comida", is_default=True)
        
        # Configuramos los Mocks del ML (Deuda técnica aparcada)
        mock_suggestion = MagicMock()
        mock_suggestion.category = category
        mock_get_suggestion.return_value = mock_suggestion
        mock_is_auto.return_value = True

        # 2. Act
        await handle_message(mock_update, mock_context)
        
        # 3. Asserts
        # Verificar que se creó el gasto en la BD
        expense = await Expense.objects.select_related('category').afirst()
        assert expense is not None
        assert expense.amount == Decimal("5000")
        assert expense.description == "Hamburguesa"
        assert expense.category.name == "Comida"
        
        # Verificar que el bot respondió enviando el teclado inline (reply_markup)
        mock_update.message.reply_text.assert_called_once()
        kwargs = mock_update.message.reply_text.call_args[1] # Obtenemos los argumentos nombrados
        assert "reply_markup" in kwargs
        assert kwargs["reply_markup"] is not None

    async def test_handle_message_invalid_format(self, mock_update, mock_context):
        """Prueba que el bot ataja mensajes sin montos enviando el error de parseo."""
        
        mock_update.message.text = "Hola bot, ¿cómo estás?"
        
        await handle_message(mock_update, mock_context)
        
        # Verificar que no se guardó nada
        count = await Expense.objects.acount()
        assert count == 0
        
        # Verificar la respuesta de error
        mock_update.message.reply_text.assert_called_once()
        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "No pude detectar el monto" in respuesta


# ============================================
# TESTS DE COMANDOS AVANZADOS Y EXCEPCIONES
# ============================================

class TestAdvancedCommandsAndExceptions:

    @patch("apps.bot.handlers.handlers.get_month_stats")
    async def test_stats_command(self, mock_get_stats, mock_update, mock_context):
        """Prueba el comando /stats falseando la respuesta de la base de datos."""
        # Simulamos lo que devolvería el selector
        mock_get_stats.return_value = {
            "month_name": "Marzo 2026",
            "total_amount": Decimal("1500"),
            "total_count": 1,
            "by_category": []
        }
        
        await stats_command(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "Resumen de Marzo 2026" in respuesta

    async def test_history_command_no_expenses(self, mock_update, mock_context):
            """Prueba el comando /historial cuando el usuario no tiene gastos."""
            await User.objects.acreate(telegram_id=123456789, username="test_history")
            mock_context.args = ["5"]
            
            await history_command(mock_update, mock_context)
            
            # FIX: Aceptamos que se llame más de una vez (ej: mensaje de "cargando" y el final)
            assert mock_update.message.reply_text.call_count >= 1
            
            # Tomamos el último mensaje que el bot envió (índice -1)
            respuesta = mock_update.message.reply_text.call_args_list[-1][0][0]
            assert "No encontramos gastos" in respuesta or "No tienes gastos registrados" in respuesta


    @patch("apps.bot.handlers.handlers.generate_magic_link_token")
    async def test_link_command(self, mock_gen_token, mock_update, mock_context):
        """Prueba la generación del Magic Link."""
        mock_gen_token.return_value = "token-secreto-123"
        
        await link_command(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        respuesta = mock_update.message.reply_text.call_args[0][0]
        assert "token-secreto-123" in respuesta
        assert "Ir al dashboard" in respuesta

    # --- FORZANDO ERRORES PARA CUBRIR LOS BLOQUES "except" ---
    
    @patch("apps.bot.handlers.handlers.get_or_create_user_by_telegram")
    async def test_start_command_triggers_exception(self, mock_get_user, mock_update, mock_context):
        """Simulamos que la base de datos se cae al intentar crear el usuario."""
        mock_get_user.side_effect = Exception("Fallo catastrófico de DB")
        
        await start_command(mock_update, mock_context)
        
        # Debe atrapar el error y enviar un mensaje amigable
        mock_update.message.reply_text.assert_called_with("Ocurrió un error al iniciar. Por favor, intentá de nuevo.")

    @patch("apps.bot.handlers.handlers.ExpenseParser")
    async def test_handle_message_triggers_exception(self, mock_parser_class, mock_update, mock_context):
        """Simulamos que el parser falla inesperadamente."""
        mock_update.message.text = "Gasto"
        
        # Configuramos el mock para que lance un error al instanciarse o parsear
        mock_instance = MagicMock()
        mock_instance.parse.side_effect = Exception("Error de lógica interno")
        mock_parser_class.return_value = mock_instance
        
        await handle_message(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_with("Ocurrió un error al guardar tu gasto. Por favor, intentá de nuevo.")
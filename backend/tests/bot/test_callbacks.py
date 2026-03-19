"""
Tests para los eventos de botones (callbacks) del bot.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from django.core.exceptions import ObjectDoesNotExist

from apps.bot.handlers.callbacks import central_callback_handler, on_delete_click, on_restore_click

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
def mock_update_cb():
    """Simula un Update que proviene de un toque en un botón inline."""
    update = MagicMock()
    update.effective_user.id = 123456789
    update.callback_query = AsyncMock()
    return update

class TestCallbacks:

    async def test_central_callback_invalid_format(self, mock_update_cb):
        """Prueba cuando el botón tiene data corrupta sin los dos puntos (':')."""
        mock_update_cb.callback_query.data = "boton_roto"
        
        await central_callback_handler(mock_update_cb, AsyncMock())
        
        mock_update_cb.callback_query.answer.assert_called_with(
            "❌ Error: Formato de botón inválido", show_alert=True
        )

    async def test_central_callback_unknown_action(self, mock_update_cb):
        """Prueba cuando el botón manda una acción que no está en las rutas."""
        mock_update_cb.callback_query.data = "hack:99"
        
        await central_callback_handler(mock_update_cb, AsyncMock())
        
        mock_update_cb.callback_query.answer.assert_called_with("⚠️ Acción desconocida")

    @patch("apps.bot.handlers.callbacks.delete_expense")
    @patch("apps.bot.handlers.callbacks.get_user_by_telegram_id")
    async def test_on_delete_click_success(self, mock_get_user, mock_delete, mock_update_cb):
        """Prueba borrar un gasto exitosamente mediante botón y ofrecer deshacer."""
        # get_or_create devuelve una tupla (user, created)
        mock_get_user.return_value = (MagicMock(), False)
        # delete_expense ahora devuelve el ID de la papelera (un entero)
        mock_delete.return_value = 99 
        
        await on_delete_click(mock_update_cb, AsyncMock(), "55")
        
        mock_update_cb.callback_query.answer.assert_called_with("🗑️ Gasto eliminado")
        
        # Verificamos que el texto haya cambiado para incluir la pregunta y el teclado
        call_args = mock_update_cb.callback_query.edit_message_text.call_args
        assert "🗑️ Gasto eliminado de tu historial" in call_args[0][0]
        assert "¿Te equivocaste?" in call_args[0][0]
        assert "reply_markup" in call_args[1]

    @patch("apps.bot.handlers.callbacks.delete_expense")
    @patch("apps.bot.handlers.callbacks.get_user_by_telegram_id")
    async def test_on_delete_click_failure(self, mock_get_user, mock_delete, mock_update_cb):
        """Prueba intentar borrar un gasto que ya no existe y atrapar la excepción."""
        mock_get_user.return_value = (MagicMock(), False)
        # delete_expense ahora lanza una excepción si falla
        mock_delete.side_effect = ObjectDoesNotExist("No existe") 
        
        await on_delete_click(mock_update_cb, AsyncMock(), "55")
        
        mock_update_cb.callback_query.answer.assert_called_with("⚠️ Error", show_alert=True)
        mock_update_cb.callback_query.edit_message_text.assert_called_with(
            "⚠️ No se pudo borrar el gasto (quizás ya no existe)."
        )

    @patch("apps.bot.handlers.callbacks.format_expense_confirmation")
    @patch("apps.bot.handlers.callbacks.restore_expense")
    @patch("apps.bot.handlers.callbacks.get_user_by_telegram_id")
    async def test_on_restore_click_success(self, mock_get_user, mock_restore, mock_format, mock_update_cb):
        """Prueba restaurar un gasto y mostrar su tarjeta formateada original."""
        mock_get_user.return_value = (MagicMock(), False)
        
        # Simulamos el objeto gasto que nos devuelve el servicio
        mock_expense = MagicMock()
        mock_expense.id = 55
        mock_restore.return_value = mock_expense
        
        # Simulamos lo que devuelve tu utilería visual
        mock_format.return_value = "✅ Mensaje de prueba formateado"
        
        await on_restore_click(mock_update_cb, AsyncMock(), "99")
        
        mock_update_cb.callback_query.answer.assert_called_with("✅ Gasto restaurado")
        mock_update_cb.callback_query.edit_message_text.assert_called_with(
            "✅ Mensaje de prueba formateado",
            reply_markup=ANY # Ignoramos el chequeo exacto del teclado, solo nos importa que esté
        )

    @patch("apps.bot.handlers.callbacks.restore_expense")
    @patch("apps.bot.handlers.callbacks.get_user_by_telegram_id")
    async def test_on_restore_click_failure(self, mock_get_user, mock_restore, mock_update_cb):
        """Prueba el fallo al intentar restaurar un gasto que ya expiró."""
        mock_get_user.return_value = (MagicMock(), False)
        # Simulamos que el objeto ya no está en la papelera
        mock_restore.side_effect = ObjectDoesNotExist("Expiró")
        
        await on_restore_click(mock_update_cb, AsyncMock(), "99")
        
        mock_update_cb.callback_query.answer.assert_called_with("⚠️ Error", show_alert=True)
        mock_update_cb.callback_query.edit_message_text.assert_called_with(
            "⚠️ No se pudo restaurar (el registro expiró o ya fue restaurado)."
        )
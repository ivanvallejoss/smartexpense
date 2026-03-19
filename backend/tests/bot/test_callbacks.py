"""
Tests para los eventos de botones (callbacks) del bot.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.bot.handlers.callbacks import central_callback_handler, on_delete_click

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
        """Prueba borrar un gasto exitosamente mediante botón."""
        mock_get_user.return_value = MagicMock()
        mock_delete.return_value = True # Simulamos que sí se borró
        
        # El 55 sería el payload del expense_id
        await on_delete_click(mock_update_cb, AsyncMock(), "55")
        
        mock_update_cb.callback_query.answer.assert_called_with("🗑️ Gasto eliminado")
        mock_update_cb.callback_query.edit_message_text.assert_called_with("🗑️ Gasto eliminado correctamente.")

    @patch("apps.bot.handlers.callbacks.delete_expense")
    @patch("apps.bot.handlers.callbacks.get_user_by_telegram_id")
    async def test_on_delete_click_failure(self, mock_get_user, mock_delete, mock_update_cb):
        """Prueba intentar borrar un gasto que ya no existe."""
        mock_get_user.return_value = MagicMock()
        mock_delete.return_value = False # Simulamos que falló el borrado
        
        await on_delete_click(mock_update_cb, AsyncMock(), "55")
        
        mock_update_cb.callback_query.answer.assert_called_with("⚠️ Error", show_alert=True)
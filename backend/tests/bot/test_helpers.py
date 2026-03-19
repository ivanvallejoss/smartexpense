"""
Tests para los helpers del bot de Telegram.
"""
from apps.bot.handlers.helpers import get_keyboard_markup

def test_get_keyboard_markup_creates_valid_button():
    # Act
    markup = get_keyboard_markup(expense_id=55)
    
    # Assert
    # inline_keyboard es una lista de listas (filas y columnas de botones)
    button = markup.inline_keyboard[0][0]
    
    assert button.text == "Eliminar"
    assert button.callback_data == "del:55"
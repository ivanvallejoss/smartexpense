"""
Helpers for handlers
En este momento solo estan los helpers del handler /stats pero planeo tener una separacion mas clara a medida que crezcan los handlers
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ---------------------------------------
#            KEYBOARD MARK UP
# ---------------------------------------

def get_keyboard_markup(expense_id):
    """
    Helper to orchestrate the inline buttons for messages
    """
    
    keyboard = [
            [InlineKeyboardButton("Eliminar", callback_data=f"del:{expense_id}"),]
        ]
    markup = InlineKeyboardMarkup(keyboard) 
    
    return markup
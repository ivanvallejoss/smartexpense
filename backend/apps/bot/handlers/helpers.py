"""
Helpers for handlers
En este momento solo estan los helpers del handler /stats pero planeo tener una separacion mas clara a medida que crezcan los handlers
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ---------------------------------------
#            KEYBOARD MARK UP
# ---------------------------------------

def get_delete_keyboard_markup(expense_id):                                             
    """                                                                                 
    Helper to orchestrate the inline buttons for messages                               
    """                                                                                                                                                                         
    keyboard = [                                                                        
            [InlineKeyboardButton("Eliminar", callback_data=f"del:{expense_id}"),]      
        ]                                                                               
    markup = InlineKeyboardMarkup(keyboard)                                             
                                                                                        
    return markup                                                                       



def get_undo_keyboard_markup(deleted_object_id):
    """
    Genera el boton de deshacer apuntando el ID de la papelera de reciclaje
    """
    keyboard = [
        [InlineKeyboardButton("↩️ Deshacer borrado", callback_data=f"undo:{deleted_object_id}"),]
    ]

    return InlineKeyboardMarkup(keyboard)


def get_correction_keyboard_markup(expense_id: int):
    """
    Teclado para gastos con confianza media.
    Permite confirmar o corregir la categoría sugerida.
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Correcta", callback_data=f"cat_confirm:{expense_id}"),
            InlineKeyboardButton("✏️ Cambiar", callback_data=f"cat_list:{expense_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_category_selection_keyboard_markup(expense_id: int, categories: list):
    """
    Teclado para seleccionar categoría de una lista.
    Usado tanto para confianza baja como para corrección.
    Cada botón lleva: cat_select:{expense_id}:{category_id}
    """
    keyboard = []

    # Dos categorías por fila para no abrumar al usuario
    row = []
    for i, category in enumerate(categories):
        row.append(
            InlineKeyboardButton(
                category.name,
                callback_data=f"cat_select:{expense_id}:{category.id}"
            )
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []

    # Si quedó una categoría sola en la última fila
    if row:
        keyboard.append(row)

    # Botón para crear categoría nueva al final
    keyboard.append([
        InlineKeyboardButton("➕ Nueva categoría", callback_data=f"cat_new:{expense_id}")
    ])

    return InlineKeyboardMarkup(keyboard)
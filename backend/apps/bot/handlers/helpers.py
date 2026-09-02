"""
Construcción de opciones para los mensajes del bot.

Antes emitía InlineKeyboardMarkup de Telegram; ahora emite Option neutrales.
El layout de filas se preserva exactamente — ver test_grid_mas_row_preserva_el_layout.
"""
from services.channels.senders import Option, Rows, grid, row


def delete_options(expense_id: int) -> Rows:
    return row(Option(f"del:{expense_id}", "Eliminar"))


def undo_options(deleted_object_id: int) -> Rows:
    return row(Option(f"undo:{deleted_object_id}", "↩️ Deshacer borrado"))


def correction_options(expense_id: int) -> Rows:
    """Confianza media: confirmar o corregir la categoría sugerida."""
    return row(
        Option(f"cat_confirm:{expense_id}", "✅ Correcta"),
        Option(f"cat_list:{expense_id}", "✏️ Cambiar"),
    )


def category_selection_options(expense_id: int, categories: list) -> Rows:
    """
    Categorías de a dos por fila, y '➕ Nueva categoría' siempre sola al final.

    El row() final es explícito a propósito: con una lista plana y regla
    'de a dos', un número impar de categorías aparearía la última con
    'Nueva categoría' y cambiaría el layout visible.
    """
    opciones = [Option(f"cat_select:{expense_id}:{c.id}", c.name) for c in categories]
    return grid(opciones, columns=2) + row(Option(f"cat_new:{expense_id}", "➕ Nueva categoría"))

"""
Utilidades para el bot de Telegram.
Funciones helper para formateo y manejo de usuarios.
"""
from decimal import Decimal
from typing import Tuple

from zoneinfo import ZoneInfo
import logging
logger = logging.getLogger(__name__)


def format_amount(amount: Decimal) -> str:
    """
    Formatea un monto en notación arg.

    Examples:
        >>> format_amount(Decimal('1500'))
        '$1.500'
        >>> format_amount(Decimal('1500.50'))
        '$1.500,50'
    """
    # Separar parte entera y decimal
    parts = str(amount).split(".")
    integer_part = parts[0]
    decimal_part = parts[1] if len(parts) > 1 and parts[1] != "00" else None

    # Agregar separador de miles
    integer_with_sep = "{:,}".format(int(integer_part)).replace(",", ".")

    # Construir resultado
    if decimal_part:
        return f"${integer_with_sep},{decimal_part}"
    return f"${integer_with_sep}"


def format_expense_confirmation(expense, auto_categorized=False) -> str:
    """
    Genera mensaje de confirmación para un expense guardado.

    Args:
        expense: Instancia de Expense model
        auto_categorized: Si fue auto-categorizado por el sistema

    Returns:
        Mensaje formateado para enviar al usuario
    """
    # Mapeo de colores a emojis

    color_to_emoji = {
        "#F54927": "🔴",
        "#0000FF": "🔵",
        "#3CB371": "🟢",
        "#FFFF00": "🟡",
        "#FFFF00": "🟠",
        "#800080": "🟣",
        "#D2691E": "🟤",
        "#D3D3D3": "⚫",
        "default": "📂",
    }

    if expense.category:
        category_name = expense.category.name
        category_color = expense.category.color if expense.category else "default"
        category_emoji = color_to_emoji.get(category_color, "📂")

        # Si fue auto-categorizado, agregar indicador
        if auto_categorized:
            category_display = f"{category_emoji} {category_name} (auto)"
        else:
            category_display = f"{category_emoji} {category_name}"
    else:
        category_display = "📂 Sin categorizar"

    # Show the date in local timezone
    date_str = expense.date.astimezone(ZoneInfo("America/Argentina/Buenos_Aires")).strftime("%d %b %Y, %H:%M")

    message = "✅ Guardado correctamente\n\n" f"💵 Monto: {format_amount(expense.amount)}\n" f"📝 Descripción: {expense.description}\n" f"📂 Categoría: {category_display}\n" f"📅 {date_str}\n\n" "Tip: Usá /stats para ver tu resumen del mes"
    
    logger.info(
            "Expense created successfully",
            extra={
                "user_id": expense.user.id,
                "telegram_id": expense.user.telegram_id,
                "expense_id": expense.id,
                "amount": str(expense.amount),
                "description": expense.description,
                "category": expense.category.name if expense.category else None,
                "auto_categorized": auto_categorized,
            },
        )
    
    return message



def format_stats_message(month_name: str, total_amount: Decimal, total_count: int, by_category: list) -> str:
    """
    Formatea mensaje de estadísticas del mes.

    Args:
        month_name: Nombre del mes (ej: "Noviembre 2024")
        total_amount: Total gastado en el mes
        total_count: Cantidad de expenses
        by_category: Lista de dicts con stats por categoría

    Returns:
        Mensaje formateado
    """
    if total_count == 0:
        return f"📊 Resumen de {month_name}\n\n" "No tenés gastos registrados este mes todavía.\n" "¡Empezá a trackear tus expenses!"

    message = f"📊 Resumen de {month_name}\n\n" f"💰 Total gastado: {format_amount(total_amount)}\n" f"📦 Gastos registrados: {total_count}\n"

    if by_category:
        message += "\nPor categoría:\n"

        # Mapeo de colores a emojis (ya que no hay campo emoji)
        color_to_emoji = {
            "red": "🔴",
            "blue": "🔵",
            "green": "🟢",
            "yellow": "🟡",
            "orange": "🟠",
            "purple": "🟣",
            "brown": "🟤",
            "gray": "⚫",
            "default": "📂",
        }

        for cat in by_category:
            cat_name = cat["category__name"] or "Sin categorizar"
            cat_color = cat.get("category__color", "default")
            cat_emoji = color_to_emoji.get(cat_color, "🔴")
            cat_total = cat["total"]
            cat_percentage = (cat_total / total_amount * 100) if total_amount > 0 else 0

            message += f"{cat_emoji} {cat_name}: {format_amount(cat_total)} " f"({cat_percentage:.0f}%)\n"

    return message



def format_expense_list(expenses):
    """
    Format expenses list to show for the history command
    """
    if not expenses:
        return "📭 No tienes gastos registrados todavía."

    lines = ["📊 <b>Últimos movimientos:</b>\n"]
    
    # Defined the timezone for the user. 
    # Ideally, this should come from the user settings
    tz_ar = ZoneInfo("America/Argentina/Buenos_Aires")

    for exp in expenses:
        # Convert UTC -> Argentina
        local_date = exp.date.astimezone(tz_ar)
        
        # Format date: "30/01 20:45"
        date_str = local_date.strftime("%d/%m %H:%M")
        
        # Emoji for category
        icon = "💸" 
        
        # Build the line: "📅 30/01 20:45 · 💸 Supermercado: $1500"
        line = f"<code>{date_str}</code>\n" 
        
        # I'll keep like this for now, butttt..
        # Later I do not want to be checking if it has description or not
        # Because It must always have a description.
        if exp.description:
            line += f" {icon} {exp.description}: <b>${exp.amount:,.2f} \n</b>"
        else:
            line += f" {icon} <b>${exp.amount:,.2f}</b>"
        
        # Add description if exists
        if exp.category:
            line += f" ↳ Categoria:<i>{exp.category.name} \n</i>"

        lines.append(line)

    return "\n".join(lines)
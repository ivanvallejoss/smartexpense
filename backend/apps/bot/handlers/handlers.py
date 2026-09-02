"""
Handlers del bot, agnósticos al canal.

Reciben un ChannelEvent y responden por un Sender. Sin Update, sin
ContextTypes, sin import de telegram.
"""
import logging

from asgiref.sync import sync_to_async

from apps.bot.errors import error_parsing_expenses
from apps.bot.routing import split_command
from apps.bot.state import clear_pending_category_state, get_pending_category_state
from apps.bot.utils import (
    format_expense_confirmation,
    format_expense_list,
    format_expense_needs_confirmation,
    format_expense_pending,
    format_stats_message,
)
from services.channels.events import ChannelEvent
from services.channels.senders import Sender
from services.expenses import create_expense
from services.ml.categorizer import create_category_for_user
from services.ml.helper import get_category_suggestion, record_categorization_feedback
from services.parser.expense_parser import ExpenseParser
from services.selectors import get_expenses, get_month_stats, get_user_categories_or_defaults

from .helpers import category_selection_options, correction_options, delete_options

logger = logging.getLogger(__name__)


# ==================================================================
#                           COMANDOS
# ==================================================================


async def start_command(event: ChannelEvent, user, sender: Sender) -> None:
    welcome_message = (
        "Bienvenido a SmartExpense!\n\n"
        "Envíame tus gastos en lenguaje natural:\n"
        '• "Pizza 2000"\n'
        '• "$1.500 supermercado"\n'
        '• "Café con leche 800"\n\n'
        "Comandos disponibles:\n"
        "/help - Ver esta ayuda\n"
        "/stats - Resumen del mes\n"
        "/history - Ver ultimos gastos subidos (max. 22)"
    )

    logger.info(
        "Start command executed",
        extra={"user_id": user.id, "channel": event.channel},
    )

    await sender.reply(event.conversation_id, welcome_message)


async def help_command(event: ChannelEvent, user, sender: Sender) -> None:
    help_message = (
        "Ayuda de SmartExpense\n\n"
        "Formatos soportados:\n"
        '✓ "Pizza 2000" o "2000 pizza"\n'
        '✓ Con símbolo: "$500 café"\n'
        '✓ Decimales: "15,50" o "15.50"\n'
        '✓ Miles: "$1.500"\n\n'
        "Comandos:\n"
        "/stats - Ver estadísticas del mes\n"
        "/history - Ver tus ultimos 10 gastos\n"
        "/help - Esta ayuda\n"
        "/link - Acceso al dashboard (en construccion)"
    )

    logger.info("Help command executed", extra={"user_id": user.id})

    await sender.reply(event.conversation_id, help_message)


async def stats_command(event: ChannelEvent, user, sender: Sender) -> None:
    try:
        stats = await get_month_stats(user)

        stats_message = format_stats_message(
            month_name=stats["month_name"],
            total_amount=stats["total_amount"],
            total_count=stats["total_count"],
            by_category=stats["by_category"],
        )

        logger.info(
            "Stats command executed",
            extra={
                "user_id": user.id,
                "total_amount": str(stats["total_amount"]),
                "expense_count": stats["total_count"],
            },
        )

        await sender.reply(event.conversation_id, stats_message)

    except Exception:
        logger.error(
            "Error in stats_command",
            extra={"user_id": user.id, "channel": event.channel},
            exc_info=True,
        )
        await sender.reply(
            event.conversation_id,
            "Ocurrió un error al obtener las estadísticas. Por favor, intentá de nuevo.",
        )


async def history_command(event: ChannelEvent, user, sender: Sender) -> None:
    """
    Últimos n gastos, 0 < n <= 22.

    NOTA: cuando no hay gastos manda dos mensajes. Es un bug preexistente
    (falta el return) que se preserva deliberadamente en este refactor.
    Se arregla en un commit propio.
    """
    _, args = split_command(event.text)

    limit = 10
    if args and args[0].isdigit():
        limit = min(int(args[0]), 22)

    expenses = await get_expenses(user, limit)

    if not expenses:
        await sender.reply(
            event.conversation_id,
            "No encontramos gastos relacionados con tu usuario",
        )

    response_text = format_expense_list(expenses)
    await sender.reply(event.conversation_id, response_text, parse_mode="HTML")


async def link_command(event: ChannelEvent, user, sender: Sender) -> None:
    """
    Acceso al dashboard. Deshabilitado temporalmente.

    El magic link apuntaba al frontend React, que se abandono junto con la
    API JSON que validaba el token. El emisor del token
    (services.auth.generate_magic_link_token) sigue intacto y es la pieza que
    va a reusar el login web de la Fase B — pero mientras no exista quien lo
    valide, generar un token seria mandar al usuario a una URL muerta.
    """

    mensaje = (
        "<b>Acceso a tu Dashboard</b>\n\n"
        "El dashboard web esta en construccion.\n"
        "<i>Mientras tanto podes usar /stats y /history desde el chat.</i>"
    )

    await sender.reply(event.conversation_id, mensaje, parse_mode="HTML")


# ==================================================================
#                       MENSAJES DE TEXTO
# ==================================================================


async def handle_new_category_input(
    event: ChannelEvent, user, sender: Sender, expense_id: int
) -> None:
    """
    El usuario mandó el nombre de la categoría nueva que venía pendiente.
    """
    from apps.core.models import Expense

    category_name = event.text.strip()

    if not category_name or len(category_name) > 100:
        await sender.reply(
            event.conversation_id,
            "⚠️ El nombre debe tener entre 1 y 100 caracteres. Intentá de nuevo.",
        )
        return

    await clear_pending_category_state(event.channel, event.external_user_id)

    try:
        new_category = await sync_to_async(create_category_for_user)(user=user, name=category_name)

        expense = await Expense.objects.select_related("category", "user").aget(
            id=expense_id, user=user
        )

        previous_category = expense.category
        expense.category = new_category
        expense.status = Expense.STATUS_CONFIRMED
        await expense.asave()

        if previous_category != new_category:
            await record_categorization_feedback(
                expense=expense,
                suggested_category=previous_category,
                accepted=False,
                final_category=new_category,
            )

        await sender.reply(
            event.conversation_id,
            format_expense_confirmation(expense, auto_categorized=False),
            options=delete_options(expense.id),
        )

    except Expense.DoesNotExist:
        await sender.reply(
            event.conversation_id,
            "⚠️ No se encontró el gasto. El estado fue limpiado.",
        )


async def handle_message(event: ChannelEvent, user, sender: Sender) -> None:
    """
    Mensaje de texto libre. Tres caminos según confianza del categorizador:
      >= 0.8 → auto-categoriza y confirma
      >= 0.5 → guarda con sugerencia y pide confirmación
      <  0.5 → guarda pendiente y pide categoría
    """
    from apps.core.models import Expense

    try:
        try:
            pending_expense_id = await get_pending_category_state(
                event.channel, event.external_user_id
            )
        except Exception as e:
            logger.warning(f"Redis unavailable, skipping state check {e}")
            pending_expense_id = None

        if pending_expense_id:
            await handle_new_category_input(event, user, sender, pending_expense_id)
            return

        parser = ExpenseParser()
        message_parsed = parser.parse(event.text)

        if not message_parsed["success"]:
            await error_parsing_expenses(event, sender)
            return

        suggestion = await get_category_suggestion(user, message_parsed["description"])

        # --- CAMINO 1: alta confianza ---
        if suggestion.confidence >= 0.8:
            expense = await create_expense(
                user=user,
                amount=message_parsed["amount"],
                description=message_parsed["description"],
                category=suggestion.category,
            )
            await sender.reply(
                event.conversation_id,
                format_expense_confirmation(expense, auto_categorized=True),
                options=delete_options(expense.id),
            )

        # --- CAMINO 2: confianza media ---
        elif suggestion.confidence >= 0.5:
            expense = await create_expense(
                user=user,
                amount=message_parsed["amount"],
                description=message_parsed["description"],
                category=suggestion.category,
            )
            await sender.reply(
                event.conversation_id,
                format_expense_needs_confirmation(
                    expense,
                    suggested_category_name=(
                        suggestion.category.name if suggestion.category else "Sin categoría"
                    ),
                ),
                options=correction_options(expense.id),
            )

        # --- CAMINO 3: confianza baja ---
        else:
            expense = await create_expense(
                user=user,
                amount=message_parsed["amount"],
                description=message_parsed["description"],
                category=None,
                status=Expense.STATUS_PENDING,
            )
            categories = await get_user_categories_or_defaults(user)
            await sender.reply(
                event.conversation_id,
                format_expense_pending(expense),
                options=category_selection_options(expense.id, categories),
            )

    except Exception:
        logger.error(
            "Error in handle_message",
            extra={
                "user_id": getattr(user, "id", None),
                "channel": event.channel,
                "message_text": event.text,
            },
            exc_info=True,
        )
        await sender.reply(
            event.conversation_id,
            "Ocurrió un error al guardar tu gasto. Por favor, intentá de nuevo.",
        )

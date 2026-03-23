"""
Telegram bot handlers.
Works with the bot application to handle updates. (/start, /help, /stats and expenses)
"""
import logging
import os

from asgiref.sync import sync_to_async

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.ml.helper import get_category_suggestion, record_categorization_feedback
from services.ml.categorizer import ExpenseCategorizer, create_category_for_user
from services.parser.expense_parser import ExpenseParser
from services.expenses import create_expense
from services.users import get_or_create_user_by_telegram
from services.selectors import get_expenses, get_month_stats, get_user_categories_or_defaults
from services.auth import generate_magic_link_token

from apps.core.models import Expense
from apps.bot.errors import error_parsing_expenses
from apps.bot.utils import format_expense_confirmation, format_stats_message, format_expense_list, format_expense_needs_confirmation, format_expense_pending
from apps.bot.state import get_pending_category_state, clear_pending_category_state

from .helpers import get_delete_keyboard_markup, get_correction_keyboard_markup, get_category_selection_keyboard_markup
from django.conf import settings



logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start handler.
    get or create the user and send an Welcome message.
    """
    telegram_user = update.effective_user

    try:
        # get or create user
        user, created = await get_or_create_user_by_telegram(telegram_user)

        logger.info(
            "Start command executed",
            extra={
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "is_new_user": created,
                "username": telegram_user.username,
            },
        )

        welcome_message = (
            "Bienvenido a SmartExpense!\n\n" 
            "Envíame tus gastos en lenguaje natural:\n" 
            '• "Pizza 2000"\n' 
            '• "$1.500 supermercado"\n' 
            '• "Café con leche 800"\n\n' 
            "Comandos disponibles:\n" 
            "/help - Ver esta ayuda\n" 
            "/stats - Resumen del mes\n" 
            "/historial - Ver ultimos gastos subidos (max. 22)"
        )

        await update.message.reply_text(welcome_message)

    except Exception as e:
        logger.error(
            "Error in start_command",
            extra={
                "telegram_id": telegram_user.id,
                "error_detail": str(e),
            },
            exc_info=True,
        )
        await update.message.reply_text("Ocurrió un error al iniciar. Por favor, intentá de nuevo.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /help - muestra información de uso."""
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
        "/link - Obtener el link para ver todos tus gastos en un dashboard"
    )

    logger.info("Help command executed", extra={"telegram_id": update.effective_user.id})

    await update.message.reply_text(help_message)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para /stats.
    It shows the stats of the current week.
    """
    telegram_user = update.effective_user

    try:
        # Obtener o crear usuario
        user, _ = await get_or_create_user_by_telegram(telegram_user)

        # Obtener stats
        stats = await get_month_stats(user)

        # Formatear mensaje
        stats_message = format_stats_message(month_name=stats["month_name"], total_amount=stats["total_amount"], total_count=stats["total_count"], by_category=stats["by_category"])

        logger.info(
            "Stats command executed",
            extra={
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "total_amount": str(stats["total_amount"]),
                "expense_count": stats["total_count"],
            },
        )

        await update.message.reply_text(stats_message)

    except Exception as e:
        logger.error(
            "Error in stats_command",
            extra={
                "telegram_id": telegram_user.id,
                "error_detail": str(e),
            },
            exc_info=True,
        )
        await update.message.reply_text("Ocurrió un error al obtener las estadísticas. " "Por favor, intentá de nuevo.")



async def handle_new_category_input(
    update: Update,
    context,
    user,
    expense_id: int
) -> None:
    """
    Procesa el nombre de categoría que el usuario envió.
    Se llama cuando hay un estado pendiente de creación de categoría.
    """
    category_name = update.message.text.strip()

    if not category_name or len(category_name) > 100:
        await update.message.reply_text(
            "⚠️ El nombre debe tener entre 1 y 100 caracteres. Intentá de nuevo."
        )
        return

    await clear_pending_category_state(update.effective_user.id)

    try:
        # Creamos la categoría
        new_category = await sync_to_async(create_category_for_user)(
            user=user,
            name=category_name
        )

        # Buscamos el expense y le asignamos la categoría
        expense = await Expense.objects.select_related('category', 'user').aget(
            id=expense_id,
            user=user
        )

        previous_category = expense.category
        expense.category = new_category
        expense.status = Expense.STATUS_CONFIRMED
        await expense.asave()

        # Feedback para el ML
        if previous_category != new_category:
            await record_categorization_feedback(
                expense=expense,
                suggested_category=previous_category,
                accepted=False,
                final_category=new_category,
            )

        reply_markup = get_delete_keyboard_markup(expense_id=expense.id)
        await update.message.reply_text(
            format_expense_confirmation(expense, auto_categorized=False),
            reply_markup=reply_markup
        )

    except Expense.DoesNotExist:
        await update.message.reply_text("⚠️ No se encontró el gasto. El estado fue limpiado.")



async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para mensajes normales.
    Tres caminos según el nivel de confianza del categorizador:
    >= 0.8 → auto-categoriza, confirma al usuario (comportamiento actual)
    >= 0.5 → guarda con categoría sugerida, pide confirmación
    <  0.5 → guarda como pendiente, pide al usuario que elija categoría
    """
    telegram_user = update.effective_user
    message_text = update.message.text

    try:
        user, _ = await get_or_create_user_by_telegram(telegram_user)

        try:
            # Verificamos si el usuario está en medio de crear una categoría
            pending_expense_id = await get_pending_category_state(telegram_user.id)
        except Exception as e:
            logger.warning(f"Redis unavailable, skipping state check {e}")
            pending_expense_id = None
            
        if pending_expense_id:
            await handle_new_category_input(update, context, user, pending_expense_id)
            return


        parser = ExpenseParser()
        message_parsed = parser.parse(message_text)

        if not message_parsed["success"]:
            await error_parsing_expenses(update, context)
            return

        suggestion = await get_category_suggestion(user, message_parsed["description"])

        # --- CAMINO 1: Alta confianza → auto-categoriza ---
        if suggestion.confidence >= 0.8:
            expense = await create_expense(
                user=user,
                amount=message_parsed["amount"],
                description=message_parsed["description"],
                category=suggestion.category,
            )
            confirmation = format_expense_confirmation(expense, auto_categorized=True)
            reply_markup = get_delete_keyboard_markup(expense_id=expense.id)
            await update.message.reply_text(confirmation, reply_markup=reply_markup)

        # --- CAMINO 2: Confianza media → guarda y pide confirmación ---
        elif suggestion.confidence >= 0.5:
            expense = await create_expense(
                user=user,
                amount=message_parsed["amount"],
                description=message_parsed["description"],
                category=suggestion.category,
            )
            message = format_expense_needs_confirmation(
                expense,
                suggested_category_name=suggestion.category.name if suggestion.category else "Sin categoría"
            )
            reply_markup = get_correction_keyboard_markup(expense_id=expense.id)
            await update.message.reply_text(message, reply_markup=reply_markup)

        # --- CAMINO 3: Confianza baja → guarda pendiente, pide categoría ---
        else:
            expense = await create_expense(
                user=user,
                amount=message_parsed["amount"],
                description=message_parsed["description"],
                category=None,
                status=Expense.STATUS_PENDING,
            )
            categories = await get_user_categories_or_defaults(user)
            message = format_expense_pending(expense)
            reply_markup = get_category_selection_keyboard_markup(
                expense_id=expense.id,
                categories=categories
            )
            await update.message.reply_text(message, reply_markup=reply_markup)

    except Exception as e:
        logger.error(
            "Error in handle_message",
            extra={
                "telegram_id": telegram_user.id,
                "message_text": message_text,
                "error_detail": str(e),
            },
            exc_info=True,
        )
        await update.message.reply_text(
            "Ocurrió un error al guardar tu gasto. Por favor, intentá de nuevo."
        )



async def history_command(update, context):
    """
    Command that show the user the lasts n expenses
            0 < n <= 22
    """
    telegram_user = update.effective_user
    user, _ = await get_or_create_user_by_telegram(telegram_user=telegram_user)

    args = context.args # Get everything after the command

    limit = 10
    if args and args[0].isdigit():
        limit = min(int(context.args[0]), 22) # setting a max-value of 22 expenses to show
    
    expenses = await get_expenses(user, limit)

    if not expenses:
        await update.message.reply_text("No encontramos gastos relacionados con tu usuario")
    # Get the lists formatted for the user

    response_text = format_expense_list(expenses)
    await update.message.reply_text(response_text, parse_mode="HTML")


async def link_command(update, context):
    """
    Genera un Magic Link de un solo uso (o de tiempo limitado) para entrar al frontend
    """
    telegram_user = update.effective_user

    user, _ = await get_or_create_user_by_telegram(telegram_user=telegram_user)

    # Obtenemos el token desde el servicio
    token = generate_magic_link_token(telegram_id=telegram_user.id)

    # Construimos la URL.
    frontend_url = settings.FRONTEND_URL
    magic_link = f"{frontend_url}/login?token={token}"

    # Respondemos al usuario
    mensaje = (
        '<b>Acceso a tu Dashboard</b>\n\n'
        'Haz clic en el enlace de abajo para entrar.\n'
        '<i>Este link es personal, seguro y caduca en 15 minutos.</i>\n\n'
        f'<a href="{magic_link}">Ir al dashboard</a>'
    )

    await update.message.reply_text(mensaje, parse_mode=ParseMode.HTML)
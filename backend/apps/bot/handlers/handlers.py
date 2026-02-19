"""
Telegram bot handlers.
Works with the bot application to handle updates. (/start, /help, /stats and expenses)
"""
import logging
import os

from dotenv import load_dotenv

from asgiref.sync import sync_to_async

from telegram import Update
from telegram.ext import ContextTypes

from services.ml.helper import is_autocategorized, get_category_suggestion
from services.ml.categorizer import ExpenseCategorizer
from services.parser.expense_parser import ExpenseParser
from services.expenses import create_expense
from services.selectors import get_lasts_expenses, get_month_stats
from services.auth import generate_magic_link_token

from apps.core.models import Expense
from apps.bot.errors import error_parsing_expenses
from apps.bot.utils import format_expense_confirmation, format_stats_message, get_or_create_user_from_telegram, format_expense_list

from .helpers import get_keyboard_markup
from django.conf import settings


load_dotenv()
logger = logging.getLogger(__name__)


# Wrappear la función con el decorador para evitar race conditions
@sync_to_async
def async_get_or_create_user(telegram_user):
    """Versión async-safe de get_or_create_user_from_telegram."""
    return get_or_create_user_from_telegram(telegram_user)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start handler.
    get or create the user and send an Welcome message.
    """
    telegram_user = update.effective_user

    try:
        # get or create user
        user, created = await async_get_or_create_user(telegram_user)

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
        "/help - Esta ayuda"
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
        user, _ = await async_get_or_create_user(telegram_user)

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



async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para mensajes normales (no comandos).
    Parsea el mensaje con auto-categorización como expense, lo guarda y envía confirmación.
    """

    telegram_user = update.effective_user
    message_text = update.message.text

    try:
        # Obtener o crear usuario
        user, _ = await async_get_or_create_user(telegram_user)

        # Parsear mensaje con ExpenseParser (sync operation)
        parser = ExpenseParser()
        message_parsed = parser.parse(message_text)

        # Throw Error if parsing fails 
        if not message_parsed["success"]:
            await error_parsing_expenses(update, context)
            return

        # ML => Category Suggestion related 
        suggestion = await get_category_suggestion(user, message_parsed["description"])
        auto_categorized = await is_autocategorized(suggestion, user)

        expense = await create_expense(
            user=user,
            amount=message_parsed["amount"],
            description=message_parsed["description"],
            category=suggestion.category,
            raw_message=message_text,
        )

        # Format confirmation message
        confirmation = format_expense_confirmation(expense, auto_categorized=auto_categorized)
        
        # Get the MarkUps for the inline buttons
        reply_markup = get_keyboard_markup(expense_id=expense.id)
        
        await update.message.reply_text(confirmation, reply_markup=reply_markup)

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
        await update.message.reply_text("Ocurrió un error al guardar tu gasto. " "Por favor, intentá de nuevo.")



async def history_command(update, context):
    """
    Command that show the user the lasts n expenses
            0 < n <= 22
    """
    telegram_id = update.effective_user.id
    args = context.args # Get everything after the command

    limit = 5
    if args and args[0].isdigit():
        limit = min(int(context.args[0]), 22) # setting a max-value of 22 expenses to show
    
    expenses = await get_lasts_expenses(telegram_id, limit)

    if not expenses:
        await update.message.reply_text("No encontramos gastos relacionados con tu usuario")
    # Get the lists formatted for the user

    response_text = format_expense_list(expenses)
    await update.message.reply_text(response_text, parse_mode="HTML")


async def link_command(update, context):
    """
    Genera un Magic Link de un solo uso (o de tiempo limitado) para entrar al frontend
    """
    telegram_id = update.effective_user.id

    # Obtenemos el token desde el servicio
    token = generate_magic_link_token(telegram_id=telegram_id)

    # Construimos la URL.
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    magic_link = f"{frontend_url}/login?token={token}"

    # Respondemos al usuario
    mensaje = (
        "<b>Acceso a tu Dashboard</b>\n\n"
        "Haz clic en el enlace de abajo para entrar."
        "<i>Este link es personal, seguro y caduca en 15 minutos.</i>"
        f"<a href='{magic_link}'>Ir a mif finanzas</a>"
    )

    await update.message.reply_text(mensaje, parse_mode="HTML")
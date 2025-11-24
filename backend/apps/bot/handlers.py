"""
Telegram bot handlers.
Maneja comandos (/start, /help, /stats) y mensajes de expenses.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from asgiref.sync import sync_to_async
from telegram import Update
from telegram.ext import ContextTypes

from apps.core.models import Expense
from apps.parsers.expense_parser import ExpenseParser

from .utils import format_expense_confirmation, format_stats_message, get_or_create_user_from_telegram

logger = logging.getLogger(__name__)


# Wrappear la función con el decorador para evitar race conditions
@sync_to_async
def async_get_or_create_user(telegram_user):
    """Versión async-safe de get_or_create_user_from_telegram."""
    return get_or_create_user_from_telegram(telegram_user)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para /start.
    Crea o recupera el usuario y envía mensaje de bienvenida.
    """
    telegram_user = update.effective_user

    try:
        # Usar versión decorada
        user, created = await async_get_or_create_user(telegram_user)

        logger.info(
            "Start command executed",
            extra={
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "created": created,
                "username": telegram_user.username,
            },
        )

        welcome_message = (
            "Bienvenido a SmartExpense!\n\n" "Envíame tus gastos en lenguaje natural:\n" '• "Pizza 2000"\n' '• "$1.500 supermercado"\n' '• "Café con leche 800"\n\n' "Comandos disponibles:\n" "/help - Ver esta ayuda\n" "/stats - Resumen del mes"
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


# Helper async para queries de DB
@sync_to_async
def get_month_stats(user):
    """Helper sincrónico para obtener stats del mes."""
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    expenses = Expense.objects.filter(user=user, date__gte=month_start, date__lte=now)

    total_amount = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_count = expenses.count()

    by_category = list(expenses.values("category__name", "category__color").annotate(total=Sum("amount"), count=Count("id")).order_by("-total"))

    return {"total_amount": total_amount, "total_count": total_count, "by_category": by_category, "month_name": now.strftime("%B %Y")}


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para /stats.
    Muestra estadísticas del mes actual del usuario.
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


# Helper async para crear expense
@sync_to_async
def create_expense(user, amount, description):
    """Helper sincrónico para crear expense."""
    with transaction.atomic():
        expense = Expense.objects.create(user=user, amount=amount, description=description, date=timezone.now())
    return expense


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para mensajes normales (no comandos).
    Parsea el mensaje como expense, lo guarda y envía confirmación.
    """
    telegram_user = update.effective_user
    message_text = update.message.text

    try:
        # Obtener o crear usuario
        user, _ = await async_get_or_create_user(telegram_user)

        # Parsear mensaje con ExpenseParser (sync operation)
        parser = ExpenseParser()
        result = parser.parse(message_text)

        if not result["success"]:
            # Mensaje de error amigable
            error_message = "No pude detectar el monto en tu mensaje.\n\n" "Formato correcto:\n" '• "Pizza 2000"\n' '• "$500 café"\n' '• "1500 uber"\n\n' "Probá de nuevo o enviá /help para más info."

            logger.warning(
                "Failed to parse expense",
                extra={
                    "user_id": user.id,
                    "telegram_id": user.telegram_id,
                    "message_text": message_text,
                    "parse_error": result.get("error"),
                },
            )

            await update.message.reply_text(error_message)
            return

        # Guardar expense en DB
        expense = await create_expense(user=user, amount=result["amount"], description=result["description"])

        # Formatear y enviar confirmación
        confirmation = format_expense_confirmation(expense)

        logger.info(
            "Expense created successfully",
            extra={
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "expense_id": expense.id,
                "amount": str(expense.amount),
                "description": expense.description,
            },
        )

        await update.message.reply_text(confirmation)

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


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler global para errores no capturados.
    """
    logger.error(
        "Unhandled exception in bot",
        extra={
            "error_detail": str(context.error),
            "update_info": str(update) if update else None,
        },
        exc_info=context.error,
    )

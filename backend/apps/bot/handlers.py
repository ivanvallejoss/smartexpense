"""
Telegram bot handlers.
Works with the bot application to handle updates. (/start, /help, /stats and expenses)
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
from services.ml.categorizer import ExpenseCategorizer
from services.parser.expense_parser import ExpenseParser

from .utils import format_expense_confirmation, format_stats_message, get_or_create_user_from_telegram

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
    """Helper async to get month stats."""
    from zoneinfo import ZoneInfo

    user_tz = ZoneInfo("America/Argentina/Buenos_Aires")
    now = timezone.now()
    # We convert the timezone to Buenos Aires to get the correct month start for the User
    local_now = now.astimezone(user_tz)
    local_month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # We dont need to get the exact timezone of the user for this query
    # So, we use the timezone of the server for accuracy
    expenses = Expense.objects.filter(
        user=user, 
        date__gte=local_month_start, 
        date__lte=now
        )

    total_amount = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_count = expenses.count()

    by_category = list(
        expenses.values("category__name", "category__color")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
        )
    
    # We use the local month name
    local_month_name = local_now.strftime("%B %Y")

    return {
        "total_amount": total_amount, 
        "total_count": total_count, 
        "by_category": by_category, 
        "month_name": local_month_name}


# Still needs to figured it out how to implement this
# Not sure how to handle yet
@sync_to_async
def get_week_stats(user):
    """
    Helper async to get week stats.
    We calculate the week start for the user timezone and get the expenses for that week.
    """
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    
    now = timezone.now()
    user_tz = ZoneInfo("America/Argentina/Buenos_Aires")
    local_now = now.astimezone(user_tz)

    # We calculate the day of the week the user is rn
    days_to_calculate = local_now.weekday()
    # Calculating the start of the week from the current day
    week_start = local_now - timedelta(days=days_to_calculate)

    # So the query gets the expenses from the monday of this week to now
    expenses = Expense.objects.filter(
        user=user, 
        date__gte=week_start, 
        date__lte=now
        )

    total_amount = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_count = expenses.count()

    by_category = list(expenses
    .values("category__name", "category__color")
    .annotate(total=Sum("amount"), count=Count("id"))
    .order_by("-total"))

    return {
        "total_amount": total_amount, 
        "total_count": total_count, 
        "by_category": by_category, 
        # Returned the start of the week for the user
        "start_date": week_start.strftime("%d/%m")
        }


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


@sync_to_async
def create_expense(user, amount, description, category, raw_message, date):
    """Helper sincrónico para crear expense con categoría."""
    with transaction.atomic():
        expense = Expense.objects.create(
            user=user,
            amount=amount,
            description=description,
            category=category,
            date=date,
            raw_message=raw_message,
        )
    return expense


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

        # hacemos uso await con una async function para evitar problemas con la base de datos.
        suggestion = await get_category_suggestion(user, result["description"])

        # Determinar categoría basándose en confidence
        category = None
        auto_categorized = False

        if suggestion.confidence >= 0.8:
            # Alta confianza: auto-categorizar sin preguntar
            category = suggestion.category
            auto_categorized = True
            logger.info(
                "Auto-categorized expense",
                extra={
                    "user_id": user.id,
                    "description": result["description"],
                    "category": category.name,
                    "confidence": suggestion.confidence,
                    "reason": suggestion.reason,
                },
            )

        # Guardar expense en DB con categoría sugerida
        now = timezone.now()
        expense = await create_expense(
            user=user,
            amount=result["amount"],
            description=result["description"],
            category=category,
            raw_message=message_text,
            date=now,
        )

        # Guardar feedback si se auto-categorizó
        if auto_categorized:
            await record_categorization_feedback(
                expense=expense,
                suggested_category=category,
                accepted=True,
            )

        # Formatear y enviar confirmación
        confirmation = format_expense_confirmation(expense, auto_categorized=auto_categorized)

        logger.info(
            "Expense created successfully",
            extra={
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "expense_id": expense.id,
                "amount": str(expense.amount),
                "description": expense.description,
                "category": category.name if category else None,
                "auto_categorized": auto_categorized,
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


@sync_to_async
def record_categorization_feedback(expense, suggested_category, accepted):
    """Helper sincrónico para guardar feedback de categorización."""

    categorizer = ExpenseCategorizer(expense.user)
    categorizer.record_feedback(
        expense=expense,
        suggested_category=suggested_category,
        accepted=accepted,
        final_category=suggested_category if accepted else None,
    )


@sync_to_async
def get_category_suggestion(user, description):
    """Helper sincrónico para obtener sugerencia de categoría."""

    categorizer = ExpenseCategorizer(user)

    # # DEBUG: Ver qué categorías tiene el usuario
    # categories = categorizer._get_user_categories()
    # print(f"[DEBUG] Usuario {user.username} tiene {len(categories)} categorías")
    # for cat in categories:
    #     print(f"  - {cat.name}: keywords={cat.keywords}")

    # # DEBUG: Ver keyword map
    # keyword_map = categorizer._get_keyword_map()
    # print(f"[DEBUG] Keyword map tiene {len(keyword_map)} keywords")
    # print(f"[DEBUG] Primeros 10 keywords: {list(keyword_map.keys())}")

    suggestion = categorizer.suggest(description)

    # DEBUG: Ver resultado
    print(f"[DEBUG] Sugerencia para '{description}':")
    print(f"  - category: {suggestion.category.name if suggestion.category else None}")
    print(f"  - confidence: {suggestion.confidence}")
    print(f"  - reason: {suggestion.reason}")
    print(f"  - matched_keyword: {suggestion.matched_keyword}")

    return suggestion


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

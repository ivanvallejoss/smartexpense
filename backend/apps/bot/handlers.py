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
from apps.ml.categorizer import ExpenseCategorizer
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


@sync_to_async
def create_expense(user, amount, description, category, raw_message):
    """Helper sincrónico para crear expense con categoría."""
    with transaction.atomic():
        expense = Expense.objects.create(
            user=user,
            amount=amount,
            description=description,
            category=category,
            date=timezone.now(),
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
        expense = await create_expense(
            user=user,
            amount=result["amount"],
            description=result["description"],
            category=category,
            raw_message=message_text,
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

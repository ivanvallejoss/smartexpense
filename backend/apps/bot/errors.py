import logging
import traceback
from telegram import Update
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Log the error and send a telegram message to notify the developer.
    """
    logger.error(msg="Exception while handling an update", exc_info=context.error)
    
    # Getting the error traceback
    tb_list = traceback.format_exception(type(context.error), context.error, context.error.__traceback__)
    tb_str = "".join(tb_list)
    
    # Showing the error in the logs
    logger.error(
        "Unhandled exception in bot",
        extra={
            "error_detail": str(context.error),
            "update_info": str(update) if update else None,
            "traceback": tb_str,
        },
        exc_info=context.error,
    )


    # Just in case a user is involved
    if isinstance(update, Update) and update.effective_message:
        text = "Ocurrió un error al procesar tu mensaje. Por favor, intentá de nuevo."
        await update.effective_message.reply_text(text)
    
    # Send a text to the developer
    # dev_text = tb_str


async def error_parsing_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Log the error and send a telegram message to the user.
    """
    # Mensaje de error amigable
    error_message = "No pude detectar el monto en tu mensaje.\n\n" "Formato correcto:\n" '• "Pizza 2000"\n' '• "$500 café"\n' '• "1500 uber"\n\n' "Probá de nuevo o enviá /help para más info."

    logger.warning(
        "Failed to parse expense",
        extra={
            "user_id": update.effective_user.id,
            "telegram_id": update.effective_user.telegram_id,
            "message_text": update.message.text or None,
        },
    )

    await update.message.reply_text(error_message)
    return
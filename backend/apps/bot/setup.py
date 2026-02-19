from config import settings
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from .handlers.handlers import start_command, handle_message, help_command, stats_command, history_command, link_command
from .handlers.callbacks import central_callback_handler
from .errors import error_handler

def build_ptb_application():
    """
    App Builder
    """
    # Get token from settings
    token = settings.TELEGRAM_TOKEN
    if not token:
        raise ValueError("TELEGRAM_TOKEN is not set in the environment variables")

    # Building App
    app_builder = ApplicationBuilder().token(token)
    application = app_builder.build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("historial", history_command))
    application.add_handler(CommandHandler("link", link_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(central_callback_handler))
    application.add_error_handler(error_handler)

    return application 
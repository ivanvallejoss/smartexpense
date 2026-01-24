from config import settings
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

_ptb_application = None

def get_ptb_application():
    """
    Singleton Lazy.
    """
    global _ptb_application

    if _ptb_application is not None:
        return _ptb_application
    
    from .handlers import start_command, handle_message, help_command

    token = settings.TELEGRAM_TOKEN
    if not token:
        raise ValueError("TELEGRAM_TOKEN is not set in the environment variables")

    # Building app
    app_builder = ApplicationBuilder().token(token)
    application = app_builder.build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    _ptb_application = application

    return _ptb_application 
"""
Management command para correr el bot de Telegram.
"""
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from apps.bot.handlers import error_handler, handle_message, help_command, start_command, stats_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs the Telegram bot with polling"

    def handle(self, *args, **options):
        """Iniciar bot con polling para desarrollo."""

        # Validar token
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            self.stderr.write(self.style.ERROR("TELEGRAM_BOT_TOKEN not found in settings. " "Add it to your .env file."))
            return

        self.stdout.write(self.style.SUCCESS("Starting Telegram bot..."))

        # Crear application
        application = Application.builder().token(token).build()

        # Registrar command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))

        # Registrar message handler (para mensajes normales)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Registrar error handler
        application.add_error_handler(error_handler)

        self.stdout.write(self.style.SUCCESS("Bot started successfully. Press Ctrl+C to stop."))

        # Iniciar polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)

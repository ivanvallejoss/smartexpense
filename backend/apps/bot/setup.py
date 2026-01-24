from config import settings
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from .handlers import start_command, handle_message, help_command 

token = settings.TELEGRAM_TOKEN

# 1. Construir la app (Igual que hacías antes, pero sin run_polling)
# NOTA: Asegúrate de usar el mismo TOKEN
ptb_application = ApplicationBuilder().token(token).build()

# 2. Registrar tus handlers (Exactamente como ya lo tenías)
ptb_application.add_handler(CommandHandler("start", start_command))
ptb_application.add_handler(CommandHandler("help", help_command)) # Si lo tienes
#ptb_application.add_handler(CommandHandler("stats", stats_command)) # Si lo tienes

# Tu handler de texto (mensajes normales)
ptb_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# IMPORTANTE: Inicializar la app (necesario en versiones nuevas de PTB v20+)
async def setup_ptb():
    await ptb_application.initialize()
    await ptb_application.start()
    # No llamamos a run_polling() ni a stop() aquí

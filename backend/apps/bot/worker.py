
import os
import logging
import django

# Setting the worker environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# After setting the environment we can import the rest
from django.conf import settings
from arq.connections import RedisSettings
from telegram import Update

from services.infraestructure.redis_client import close_all

from apps.bot.setup import build_ptb_application

logger = logging.getLogger(__name__)

# Hooks de ciclo de vida del worker
async def startup(ctx):
    """
    Se ejecuta UNA vez al encender el worker.
    """
    logger.info(
        "encendiendo worker ARQ y cargando PTB en memoria.."
    )
    ptb_app = build_ptb_application()
    await ptb_app.initialize()

    # Guardamos la app viva en el diccionario ctx (memoria RAM compartida)
    ctx['ptb_app'] = ptb_app
    logger.info(
        "Worker listo para procesar gastos."
    )

async def shutdown(ctx):
    """
    Se ejecuta al apagar el worker (ej. Ctrl+C)
    """
    logger.info(
        "Apagando worker y limpiando sockets.."
    )
    ptb_app = ctx.get('ptb_app')
    
    if ptb_app:
        await ptb_app.shutdown()
    await close_all()


async def process_telegram_message(ctx, payload):
    """
    Esta funcion recibe los datos de Redis y dispara tus handlers
    """
    try:
        ptb_app = ctx['ptb_app']

        # Reconstruccion del objeto update
        update = Update.de_json(payload, ptb_app.bot)

        await ptb_app.process_update(update)

    except Exception as e:
        logger.error(
            f"Error procesando el mensaje en el worker: {e}",
            exc_info=True
        )

class WorkerSettings:
    # URL de Redis
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    functions = [process_telegram_message]
    
    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 10
    job_timeout = 60

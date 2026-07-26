import logging
import os

import django

# Setting the worker environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# After setting the environment we can import the rest
from arq.connections import RedisSettings
from django.conf import settings

from services.channels.events import ChannelEvent
from services.channels.registry import build_default_senders, normalize
from services.channels.senders import get_sender, shutdown_all, startup_all
from services.channels.telegram import CHANNEL as TELEGRAM
from services.identities import get_or_create_user_by_channel
from services.infrastructure.redis_client import close_all

from apps.bot.dispatcher import dispatch
from apps.bot.errors import MENSAJE_ERROR_GENERICO

logger = logging.getLogger(__name__)


# ==================================================================
#                    CICLO DE VIDA DEL WORKER
# ==================================================================

async def startup(ctx):
    """
    Se ejecuta UNA vez al encender el worker.

    Antes cargaba la Application de PTB en memoria para usarla como
    dispatcher. Ahora solo registra los clientes de salida: el ruteo
    lo hace apps/bot/dispatcher.py.
    """
    logger.info("Encendiendo worker ARQ y registrando senders...")
    build_default_senders()
    await startup_all()
    logger.info("Worker listo para procesar gastos.")


async def shutdown(ctx):
    """Se ejecuta al apagar el worker (ej. Ctrl+C)."""
    logger.info("Apagando worker y limpiando sockets...")
    await shutdown_all()
    await close_all()


# ==================================================================
#                          TASK ÚNICA
# ==================================================================

async def process_message(ctx, event: dict):
    """
    Única task del pipeline. Recibe el evento canónico ya normalizado
    por el productor — el worker nunca ve un payload crudo de un canal.
    """
    # --- Etapa sin efectos laterales ---
    # Un fallo acá no escribió nada todavía: es seguro reintentar,
    # así que se propaga para que ARQ haga su trabajo.
    canonical = ChannelEvent.from_dict(event)
    sender = get_sender(canonical.channel)

    user, created = await get_or_create_user_by_channel(
        canonical.channel,
        canonical.external_user_id,
        canonical.profile,
    )

    if created:
        logger.info(
            "Usuario creado desde canal",
            extra={
                "user_id": user.id,
                "channel": canonical.channel,
                "external_user_id": canonical.external_user_id,
            },
        )

    # --- Etapa con efectos laterales ---
    # El handler puede haber creado un gasto antes de fallar. Reintentar
    # lo duplicaría, así que el error se absorbe acá: se loguea completo
    # y se le avisa al usuario. Reemplaza al error_handler de PTB.
    try:
        await dispatch(canonical, user, sender)

    except Exception:
        logger.error(
            "Error procesando el evento en el worker",
            extra={
                "job_id": ctx.get("job_id"),
                "job_try": ctx.get("job_try"),
                "channel": canonical.channel,
                "message_id": canonical.message_id,
                "event_type": canonical.type,
                "user_id": user.id,
            },
            exc_info=True,
        )

        try:
            await sender.reply(canonical.conversation_id, MENSAJE_ERROR_GENERICO)
        except Exception:
            logger.error(
                "No se pudo notificar el error al usuario",
                extra={"job_id": ctx.get("job_id")},
                exc_info=True,
            )


async def process_telegram_message(ctx, payload):
    """
    DEPRECADO — alias de compatibilidad.

    Existe solo para los jobs encolados antes del deploy de la Fase 5,
    que llevan un Update crudo de Telegram en vez de un evento canónico.
    Sin esto, ARQ falla al no encontrar la función y esos mensajes se pierden.

    Se elimina en el deploy siguiente, una vez drenada la cola.
    """
    logger.warning(
        "Job recibido con el nombre viejo de la task",
        extra={"job_id": ctx.get("job_id")},
    )

    canonical = normalize(TELEGRAM, payload)

    if canonical is None:
        logger.info("Update no procesable, descartado", extra={"job_id": ctx.get("job_id")})
        return

    await process_message(ctx, canonical.to_dict())


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    functions = [process_message, process_telegram_message]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 10
    job_timeout = 60
    max_tries = 3
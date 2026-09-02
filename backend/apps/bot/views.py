import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from services.channels.events import job_id_for
from services.channels.registry import normalize
from services.channels.telegram import CHANNEL as TELEGRAM
from services.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)

# TTL = 24 HOURS is the same as Telegram max_tries TTL
IDEMPOTENCY_TTL = 60 * 60 * 24


@csrf_exempt
async def webhook(request):
    """
    Productor del pipeline.

    Normaliza el update de Telegram a evento canónico y lo encola. El worker
    nunca ve un payload crudo — ver services/channels/.
    """
    if request.method != "POST":
        return HttpResponse("Method Not Allowed", status=405)

    secret = settings.TELEGRAM_WEBHOOK_TOKEN
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
        return HttpResponse("Forbidden", status=403)

    try:
        json_data = request.body.decode("UTF-8")
        payload = json.loads(json_data)

        update_id = payload.get("update_id")
        if not update_id:
            logger.warning(
                "Webhook payload received without update_id",
                extra={"payload": payload},
            )
            return HttpResponse("Bad Request", status=400)

        # 1. Normalización: acá muere el vocabulario de Telegram.
        event = normalize(TELEGRAM, payload)

        if event is None:
            # Updates que el sistema no atiende (edited_message, fotos,
            # stickers, channel_post). Antes los descartaba PTB por falta
            # de handler; ahora ni siquiera se encolan.
            logger.info(
                "Update no procesable, descartado en el webhook",
                extra={"update_id": update_id},
            )
            return HttpResponse("OK", status=200)

        # 2. Idempotencia de ventana larga (24h, la de Telegram).
        #    SET NX es atómico: reemplaza al GET+SET que tenía carrera.
        #    Se marca ANTES de encolar — at-most-once, ver el ADR.
        cache = await get_redis("cache")
        idempotency_key = f"idempotency:{event.channel}:{event.message_id}"

        primera_vez = await cache.set(idempotency_key, "1", ex=IDEMPOTENCY_TTL, nx=True)

        if not primera_vez:
            logger.info(
                "Duplicate update ignored",
                extra={"channel": event.channel, "message_id": event.message_id},
            )
            return HttpResponse("OK", status=200)

        # 3. Encolado. _job_id da una segunda capa atómica de ~1h
        #    (keep_result de ARQ). enqueue_job retorna None si el id ya existe.
        jobs = await get_redis("jobs")
        job = await jobs.enqueue_job(
            "process_message",
            event.to_dict(),
            _job_id=job_id_for(event),
        )

        if job is None:
            logger.info(
                "Job duplicado descartado por ARQ",
                extra={"job_id": job_id_for(event)},
            )

        return HttpResponse("OK", status=200)

    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)

    except Exception as e:
        logger.error(
            "An unexpected error ocurred processing the webhook:",
            extra={"error_info": str(e)},
            exc_info=True,
        )
        return HttpResponse("Error procesado", status=200)

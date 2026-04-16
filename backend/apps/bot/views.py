import json
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from services.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL = 60 * 60 * 24 # TTL = 24 HOURS is the same as Telegram max_tries TTL

@csrf_exempt
async def webhook(request):

    if request.method != "POST":
        return HttpResponse("Method Not Allowed", status=405)

    secret = settings.TELEGRAM_WEBHOOK_TOKEN
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
        return HttpResponse("Forbidden", status=403)
    
    try:
        json_data = request.body.decode('UTF-8')
        payload = json.loads(json_data)

        update_id = payload.get("update_id")
        if not update_id:
            logger.warning(
                "Webhook payload received without update_id",
                extra={"payload": payload}
            )
            return HttpResponse("Bad Request", status=400)

        redis = await get_redis("jobs")

        # 1. Idempotency: discard any update_id already processed
        idempotency_key = f"processed_updated:{update_id}"
        already_processed = await redis.get(idempotency_key)
        if already_processed:
            logger.info(
                "Duplicate update ignored",
                extra={"update_id": update_id}
            )
            return HttpResponse("OK", status=200)
        
        # 2. If not processed, we mark it as processed
        await redis.set(idempotency_key, "1", ex=IDEMPOTENCY_TTL)
        # 3. Then we enqueue the job
        await redis.enqueue_job('process_telegram_message', payload)

        return HttpResponse("OK", status=200)
    
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)

    except Exception as e:
        logger.error(
            "An unexpected error ocurred processing the webhook:",
            extra={'error_info': str(e)},
            exc_info=True
            )
        return HttpResponse("Error procesado", status=200)
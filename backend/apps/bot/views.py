import json
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from services.infraestructure.redis_client import get_redis

logger = logging.getLogger(__name__)

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
        
        redis = await get_redis("jobs")
        await redis.enqueue_job('process_telegram_message', payload)

        return HttpResponse("OK", status=200)
    
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)

    except Exception as e:
        logger.error(
            "An unexpected error ocurred processing the webhook:",
            extra={
                'error_info': str(e),  
                },
            exc_info=True
            )
        return HttpResponse("Error procesado", status=200)
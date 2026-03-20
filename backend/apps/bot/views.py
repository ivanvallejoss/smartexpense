import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST 
from arq import create_pool
from arq.connections import RedisSettings
from telegram import Update

from django.conf import settings

logger = logging.getLogger(__name__)

# Variable global para reutilizar la conexion a Redis entre peticiones 
_redis_pool = None

async def get_redis_pool():
    global _redis_pool
    if _redis_pool is None:
        # Crea la conexion usando la URL de settings
        _redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _redis_pool



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
        
        # Conectamos a Redis y encolamos al trabajo
        redis = await get_redis_pool()
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
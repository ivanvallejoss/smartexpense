from celery import shared_task
from django.conf import settings
import requests
import logging

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,), # autoretry en caso de falla excepcional
    retry_kwargs={'max_retries': 5},
    default_retry_delay=10 # segundos    
)
def process_message(chat_id, text):
    try:
        print(f"🤖 Procesando: {text}")
        
        response_text = f"Respuesta desde Termux: {text}"
        
        # --- CAMBIO: ENVÍO MANUAL VÍA HTTP POST ---
        token = settings.TELEGRAM_BOT_TOKEN
        send_url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": response_text
        }
        
        # Enviamos la petición directa y esperamos respuesta
        r = requests.post(send_url, json=payload, timeout=5)
        r.raise_for_status() # Lanzar una excepcion si el status no es 200
        
        return "Done"

    except Exception as e:
        logger.error(
            "An unregistered error has ocurred",
            extra={
                "error_info": str(e),
                "status_code": r.status_code
            },
            exc_info=True
        )

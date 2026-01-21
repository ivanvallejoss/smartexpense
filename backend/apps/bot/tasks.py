from celery import shared_task
from django.conf import settings
import requests  # <--- Usaremos esto en lugar de telegram.Bot

@shared_task
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
        r = requests.post(send_url, json=payload)
        
        # Chequeamos si Telegram nos dio error
        if r.status_code != 200:
            print(f"❌ Error al responder a Telegram: {r.text}")
        else:
            print(f"✅ Mensaje enviado correctamente")
            
        return "Done"

    except Exception as e:
        print(f"❌ Error fatal: {e}")

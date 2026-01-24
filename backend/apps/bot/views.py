import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from telegram import Update

# Importamos la app que configuramos arriba
from .setup import get_ptb_application

@csrf_exempt
async def webhook(request):
    if request.method == 'POST':
        # Initialize the bot application for the first time
        ptb_app = get_ptb_application()

        try:
            json_str = request.body.decode('UTF-8')
            update = json.loads(json_str)
            
            # python-telegram-bot manage the update on an async way
            await ptb_app.update_queue.put(
                ptb_app.update_processor.parse_json(update)
            )
            return HttpResponse("OK")
        except Exception as e:
            print(f"Error en webhook: {e}")
            return HttpResponse("Error en webhook", status=500)
    
    return HttpResponse(status=405)

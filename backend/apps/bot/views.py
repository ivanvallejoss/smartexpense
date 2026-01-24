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

        if not ptb_app._initialized:
            await ptb_app.initialize()

        try:
            json_str = request.body.decode('UTF-8')
            data = json.loads(json_str)
            
            update = Update.de_json(data, ptb_app.bot)

            await ptb_app.process_update(update)
            return HttpResponse("OK")

        except Exception as e:
            print(f"Error en webhook: {e}")
            return HttpResponse("Error procesado", status=200)
    
    return HttpResponse(status=405)

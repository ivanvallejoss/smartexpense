import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from telegram import Update

# Imported the created mechanism to get the bot application
from .setup import build_ptb_application

@csrf_exempt
async def webhook(request):
    if request.method == 'POST':

        # Get or create the bot application
        ptb_app = build_ptb_application()

        # We need to initialize the application
        await ptb_app.initialize()

        try:
            # Decoded the request body and parsed it as JSON
            json_str = request.body.decode('UTF-8')
            data = json.loads(json_str)
            
            update = Update.de_json(data, ptb_app.bot)

            await ptb_app.process_update(update)
            return HttpResponse("Update processed", status=200)

        except Exception as e:
            print(f"Error en webhook: {e}")
            return HttpResponse("Error procesado", status=200)
        
        finally:
            # Shutdown the bot application
            await ptb_app.shutdown()
    
    return HttpResponse(status=405)

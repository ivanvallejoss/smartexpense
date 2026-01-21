import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from telegram import Update

# Importamos la app que configuramos arriba
from .setup import ptb_application, setup_ptb

# Variable para controlar si la app ya inició
ptb_initialized = False

@csrf_exempt
async def webhook(request):
    global ptb_initialized
    
    if request.method == 'POST':
        # 1. Inicialización Lazy (solo la primera vez)
        if not ptb_initialized:
            await setup_ptb()
            ptb_initialized = True

        try:
            # 2. Recibir y decodificar el JSON
            json_str = request.body.decode('UTF-8')
            data = json.loads(json_str)
            
            # 3. CONVERTIR JSON A OBJETO 'UPDATE' DE PTB
            # Aquí ocurre la magia: transformamos el dict de Django en la clase Update de Telegram
            telegram_update = Update.de_json(data, ptb_application.bot)
            
            # 4. PROCESAR LA UPDATE
            # Esto automáticamente buscará el handler correcto (start, text, etc.)
            # y ejecutará tu función start_command pasándole (update, context)
            await ptb_application.process_update(telegram_update)

        except Exception as e:
            print(f"Error en webhook: {e}")
            # Loguear error pero no fallar ante Telegram
        
        return HttpResponse("OK")
    
    return HttpResponse(status=404)

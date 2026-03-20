import urllib.request
import urllib.parse
import json
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Configura la URL del Webhook en Telegram'

    def add_arguments(self, parser):
        parser.add_argument('url', type=str, help='La URL base de Ngrok (ej: https://a1b2.ngrok.app)')

    def handle(self, *args, **kwargs):
        ngrok_url = kwargs['url'].rstrip('/')
        # Asegúrate de que esta ruta coincida con tu urls.py
        webhook_path = f"{ngrok_url}/bot/webhook/" 
        
        telegram_token = settings.TELEGRAM_TOKEN
        api_url = f"https://api.telegram.org/bot{telegram_token}/setWebhook"
        
        data = urllib.parse.urlencode({
            'url': webhook_path,
            'secret_token': settings.TELEGRAM_WEBHOOK_TOKEN
            }).encode('utf-8')
        req = urllib.request.Request(api_url, data=data)

        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                if result.get('ok'):
                    self.stdout.write(self.style.SUCCESS(f"Webhook configurado exitosamente en: {webhook_path}"))
                else:
                    self.stdout.write(self.style.ERROR(f"Error de Telegram: {result}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Excepción al conectar: {e}"))
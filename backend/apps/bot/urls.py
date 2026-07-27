from django.urls import path

from .views import webhook

urlpatterns = [
    # La ruta lleva el canal en el path. La vista sigue siendo especifica de
    # Telegram (valida su secret header y su update_id); lo que se resuelve
    # aca es que Telegram no ocupe el namespace generico "bot/webhook/", que
    # obligaria a re-registrar el webhook cuando entre un segundo canal.
    # Ver docs/decision_records/multichannel_webhook_routing.md
    path("telegram/webhook/", webhook, name="telegram-webhook"),
    # Alias de transicion: el webhook registrado en BotFather todavia apunta
    # aca. Se elimina despues de correr 'manage.py set_webhook' contra el
    # dominio de produccion y confirmar que llegan updates a la ruta nueva.
    path("webhook/", webhook, name="telegram-webhook-legacy"),
]

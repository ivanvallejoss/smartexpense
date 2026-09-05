"""
Puente magic link -> sesion web.

Cierra el break-glass de B1: hasta aca el unico login era el del admin, un
formulario que ningun usuario del bot puede usar porque ninguno tiene
contrasena. La sesion es consecuencia del canje, no un requisito de producto:
nadie pidio una cuenta web, pidieron ver sus gastos en una pantalla mas grande.

El GET no canjea nada. Telegram y WhatsApp hacen un GET a cualquier link que se
mande para armar la preview, asi que un canje en el GET lo consume el crawler
antes de que la persona toque el link, y el sintoma seria "el magic link nunca
funciona" con la causa lejos del codigo de auth. Ver docs/trampas.md.

Ver docs/decision_records/vinculacion_canales.md, seccion 7.
"""
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.views.generic import View

from asgiref.sync import sync_to_async

from apps.core.models import User
from services.auth import consume_grant
from services.constants import PURPOSE_WEB_ACCESS

# Un canje fallido no distingue entre vencido, ya usado e inexistente: quien
# llega aca no puede hacer nada distinto con cada caso, y diferenciarlos le
# confirmaria a quien tantea que ese token existio.
AVISO_LINK_INVALIDO = "Ese link ya no sirve. Pedile uno nuevo al bot con /link."


@sync_to_async
def _crear_sesion(request, user) -> None:
    """
    django.contrib.auth.login() es sincrono y estas views son async, asi que va
    envuelto: mismo patron que _create_user_with_identity en services/identities.

    Se llama sin backend explicito porque hay un solo AUTHENTICATION_BACKENDS
    (el ModelBackend por default, settings no lo declara). El dia que se agregue
    un segundo, este llamado empieza a fallar con ValueError y hay que pasarle
    el backend a mano.
    """
    login(request, user)


class EntrarView(View):
    """
    GET renderiza el boton, POST canjea. La separacion es la razon de ser de
    esta vista y no una preferencia de UX (ver el docstring del modulo).
    """

    async def get(self, request, token):
        return render(request, "auth/entrar.html", {"token": token})

    async def post(self, request, token):
        payload = await consume_grant(token, PURPOSE_WEB_ACCESS)

        if payload is not None:
            user = await User.objects.filter(pk=payload["user_id"]).afirst()
            if user is not None:
                await _crear_sesion(request, user)
                return redirect("dashboard")

        # Doble submit y boton atras: el grant se consumio en el primer POST, y
        # el segundo llega con un token que ya no existe. Mostrarle el error de
        # link invalido a alguien que ya tiene sesion parece un bug de la logica
        # de grants sin serlo.
        usuario_actual = await request.auser()
        if usuario_actual.is_authenticated:
            return redirect("dashboard")

        # 200 y no 404: un 404 confirmaria que ese token no existe.
        return render(request, "auth/pedir_acceso.html", {"avisos": [AVISO_LINK_INVALIDO]})


class PedirAccesoView(View):
    """
    Destino de LOGIN_URL. Explica como conseguir un link, porque no hay ninguna
    accion que ofrecer desde la web: el unico emisor es el bot.

    El ?next= que agrega redirect_to_login se ignora. La persona sale a pedirle
    un link al bot y vuelve con una URL nueva, asi que el next no sobrevive el
    viaje; construir el plumbing seria sostener un parametro que nunca llega.
    """

    async def get(self, request):
        return render(request, "auth/pedir_acceso.html")

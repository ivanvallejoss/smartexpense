"""
Tests del puente magic link -> sesion (unidad 4).

Los grants se emiten llamando issue_grant directamente: link_command todavia no
emite ninguno (unidad 5), asi que no existe el camino real por el que una
persona conseguiria un link.

Ojo con la fixture autouse reloj_fijo de conftest.py: congela
django.utils.timezone.now. Nada de aca depende de eso —los TTL viven en Redis y
el fake no los aplica— pero cualquier assert sobre vencimiento por tiempo real
seria mentira bajo ese freeze.
"""
from unittest.mock import AsyncMock, patch

from django.test import Client
from django.urls import reverse

import pytest
from asgiref.sync import async_to_sync

from apps.core.models import User
from services.auth import consume_grant, issue_grant
from services.constants import PURPOSE_CHANNEL_LINK, PURPOSE_WEB_ACCESS

pytestmark = pytest.mark.django_db

TG = "telegram"


@pytest.fixture(autouse=True)
def redis():
    """
    Fake del pool con respaldo en un dict, mismo patron que
    tests/services/test_services_auth.py.

    Tiene que respaldar de verdad y no devolver valores fijos: varios tests de
    acá afirman que un grant SOBREVIVIO a una operacion, y contra un mock sin
    estado eso no se distingue de que la operacion no hizo nada.

    autouse porque toda vista de este modulo pasa por consume_grant: un test que
    se olvide de pedir la fixture no falla limpio, se conecta al Redis real de
    quien corre la suite y revienta con "Event loop is closed" desde el fondo de
    redis.asyncio. Costo un debugging descubrirlo.
    """
    store: dict[str, str] = {}

    async def fake_set(key, value, *, ex=None, nx=False):
        if nx and key in store:
            return None
        store[key] = value
        return True

    async def fake_getdel(key):
        return store.pop(key, None)

    with patch("services.auth.get_redis") as mock_get:
        r = AsyncMock()
        r.set.side_effect = fake_set
        r.getdel.side_effect = fake_getdel
        r.store = store
        mock_get.return_value = r
        yield r


@pytest.fixture
def emitir(redis):
    """Emite un grant como lo hara link_command en la unidad 5."""

    def _emitir(user_id, purpose=PURPOSE_WEB_ACCESS):
        return async_to_sync(issue_grant)(user_id, purpose, TG, "123")

    return _emitir


def _entrar(token):
    return reverse("entrar", args=[token])


def _templates(respuesta):
    return [t.name for t in respuesta.templates]


class TestElGetNoConsume:
    def test_el_get_renderiza_el_boton(self, client, ivan, emitir):
        respuesta = client.get(_entrar(emitir(ivan.id)))

        assert respuesta.status_code == 200
        assert "auth/entrar.html" in _templates(respuesta)

    def test_despues_del_get_el_post_todavia_funciona(self, client, ivan, emitir):
        """
        La razon de ser del diseno GET/POST.

        Telegram y WhatsApp hacen un GET a cualquier link para armar la preview.
        Si el canje se moviera al GET, el crawler consumiria el grant y este
        POST posterior —el de la persona real— fallaria.
        """
        token = emitir(ivan.id)

        client.get(_entrar(token))
        respuesta = client.post(_entrar(token))

        assert respuesta.status_code == 302
        assert respuesta["Location"] == reverse("dashboard")
        assert client.session["_auth_user_id"] == str(ivan.id)


class TestCanje:
    def test_post_valido_crea_sesion_y_redirige_al_dashboard(self, client, ivan, emitir):
        respuesta = client.post(_entrar(emitir(ivan.id)))

        assert respuesta.status_code == 302
        assert respuesta["Location"] == reverse("dashboard")
        assert client.session["_auth_user_id"] == str(ivan.id)

    def test_el_segundo_canje_no_crea_sesion(self, client, ivan, emitir):
        """El uso unico visto desde la vista: otro cliente con el mismo token."""
        token = emitir(ivan.id)
        client.post(_entrar(token))

        otro = Client()
        respuesta = otro.post(_entrar(token))

        assert respuesta.status_code == 200
        assert "auth/pedir_acceso.html" in _templates(respuesta)
        assert "_auth_user_id" not in otro.session

    def test_token_inexistente_no_crea_sesion(self, client):
        respuesta = client.post(_entrar("no-existe"))

        # 200 y no 404: un 404 confirmaria que ese token no existe.
        assert respuesta.status_code == 200
        assert "auth/pedir_acceso.html" in _templates(respuesta)
        assert "_auth_user_id" not in client.session

    def test_grant_valido_de_un_user_borrado_no_es_un_500(self, client, ivan, emitir):
        """El payload apunta a una fila que ya no esta. Es un link muerto, no un error."""
        token = emitir(ivan.id)
        User.objects.filter(pk=ivan.id).delete()

        respuesta = client.post(_entrar(token))

        assert respuesta.status_code == 200
        assert "auth/pedir_acceso.html" in _templates(respuesta)
        assert "_auth_user_id" not in client.session


class TestPropositoCerrado:
    def test_un_token_de_channel_link_no_abre_sesion(self, client, ivan, emitir):
        respuesta = client.post(_entrar(emitir(ivan.id, PURPOSE_CHANNEL_LINK)))

        assert respuesta.status_code == 200
        assert "_auth_user_id" not in client.session

    def test_y_el_grant_de_channel_link_sobrevive(self, client, ivan, emitir):
        """
        Alguien tanteando codigos de seis digitos contra /entrar/ no puede
        quemar vinculaciones legitimas ajenas: el proposito va en la clave.
        """
        token = emitir(ivan.id, PURPOSE_CHANNEL_LINK)

        client.post(_entrar(token))

        payload = async_to_sync(consume_grant)(token, PURPOSE_CHANNEL_LINK)
        assert payload["user_id"] == ivan.id


class TestYaAutenticado:
    def test_token_invalido_con_sesion_viva_va_al_dashboard(self, client_logueado):
        """
        Doble submit y boton atras: el grant se consumio en el primer POST.
        Mostrarle un error de link invalido a alguien que ya entro parece un bug
        de la logica de grants sin serlo.
        """
        respuesta = client_logueado.post(_entrar("ya-consumido"))

        assert respuesta.status_code == 302
        assert respuesta["Location"] == reverse("dashboard")


class TestPedirAcceso:
    def test_responde_sin_sesion(self, client):
        """
        LOGIN_URL apuntando a una ruta que no resuelve es un loop de redirects.
        """
        respuesta = client.get(reverse("pedir-acceso"))

        assert respuesta.status_code == 200
        assert "auth/pedir_acceso.html" in _templates(respuesta)

    def test_el_dashboard_sin_sesion_manda_a_pedir_acceso(self, client):
        respuesta = client.get(reverse("dashboard"))

        assert respuesta.status_code == 302
        assert respuesta["Location"].startswith(reverse("pedir-acceso"))

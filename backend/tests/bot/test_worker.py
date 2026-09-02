"""
Tests de process_message: resolución de identidad, despacho y la
semántica de errores partida por etapa.
"""
from unittest.mock import AsyncMock, patch

import pytest
from tests.constants import EXTERNAL_USER_ID

from apps.bot.worker import process_message, process_telegram_message
from apps.core.models import ChannelIdentity, User
from services.channels.senders import UnknownChannel

pytestmark = pytest.mark.django_db(transaction=True)

CTX = {"job_id": "test-job", "job_try": 1}

TELEGRAM_UPDATE = {
    "update_id": 423934621,
    "message": {
        "message_id": 293,
        "date": 1753439000,
        "from": {"id": int(EXTERNAL_USER_ID), "username": "ivanvallejoss", "first_name": "Ivan"},
        "chat": {"id": int(EXTERNAL_USER_ID), "type": "private"},
        "text": "almuerzo 3500",
    },
}


@pytest.fixture
def wired(sender):
    """Sender registrado y dispatch parcheado."""
    with patch("apps.bot.worker.get_sender", return_value=sender), patch(
        "apps.bot.worker.dispatch", new=AsyncMock()
    ) as mock_dispatch:
        yield {"sender": sender, "dispatch": mock_dispatch}


class TestResolucionDeIdentidad:
    async def test_crea_usuario_e_identidad_en_el_primer_mensaje(self, make_event, wired):
        await process_message(CTX, make_event("almuerzo 3500").to_dict())

        identity = await ChannelIdentity.objects.select_related("user").aget(
            channel="telegram", external_id=EXTERNAL_USER_ID
        )
        assert identity.user.username == "test_user"

    async def test_reutiliza_la_identidad_existente(self, make_event, wired):
        u = await User.objects.acreate(username="ya_existe", telegram_id=int(EXTERNAL_USER_ID))
        await ChannelIdentity.objects.acreate(
            user=u, channel="telegram", external_id=EXTERNAL_USER_ID
        )

        await process_message(CTX, make_event("almuerzo 3500").to_dict())

        assert await User.objects.acount() == 1
        assert wired["dispatch"].await_args.args[1].id == u.id

    async def test_pasa_el_evento_reconstruido_al_dispatch(self, make_event, wired):
        await process_message(CTX, make_event("almuerzo 3500").to_dict())

        event_arg = wired["dispatch"].await_args.args[0]
        assert event_arg.text == "almuerzo 3500"
        assert event_arg.channel == "telegram"


class TestSemanticaDeErrores:
    async def test_error_del_handler_avisa_al_usuario_y_no_relanza(self, make_event, wired):
        """
        El handler pudo haber creado el gasto antes de fallar. Reintentar
        lo duplicaría, así que se absorbe.
        """
        wired["dispatch"].side_effect = Exception("Explotó el handler")

        await process_message(CTX, make_event("almuerzo 3500").to_dict())  # no levanta

        assert "Ocurrió un error al procesar tu mensaje" in wired["sender"].last_reply["text"]

    async def test_canal_sin_sender_se_propaga(self, make_event):
        """
        Sin efectos laterales todavía: es seguro que ARQ reintente.
        """
        with patch("apps.bot.worker.get_sender", side_effect=UnknownChannel("x")):
            with pytest.raises(UnknownChannel):
                await process_message(CTX, make_event("hola").to_dict())

    async def test_fallo_resolviendo_identidad_se_propaga(self, make_event, wired):
        with patch(
            "apps.bot.worker.get_or_create_user_by_channel",
            side_effect=Exception("Postgres caído"),
        ):
            with pytest.raises(Exception, match="Postgres caído"):
                await process_message(CTX, make_event("hola").to_dict())

    async def test_evento_malformado_se_propaga(self, wired):
        with pytest.raises(TypeError):
            await process_message(CTX, {"channel": "telegram", "campo_raro": 1})

    async def test_fallo_notificando_el_error_no_explota(self, make_event, wired):
        """Doble fallo: el handler revienta y el canal también."""
        wired["dispatch"].side_effect = Exception("Explotó el handler")
        wired["sender"].reply = AsyncMock(side_effect=Exception("Telegram caído"))

        await process_message(CTX, make_event("hola").to_dict())  # no levanta


class TestAliasDeCompatibilidad:
    async def test_normaliza_el_payload_crudo_y_despacha(self, wired):
        """Jobs encolados antes del deploy de la Fase 5."""
        await process_telegram_message(CTX, TELEGRAM_UPDATE)

        wired["dispatch"].assert_awaited_once()
        assert wired["dispatch"].await_args.args[0].text == "almuerzo 3500"

    async def test_update_no_procesable_se_descarta(self, wired):
        await process_telegram_message(CTX, {"update_id": 1, "channel_post": {"text": "x"}})

        wired["dispatch"].assert_not_awaited()

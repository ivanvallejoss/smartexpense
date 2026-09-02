"""
Tests del normalizador. Sin DB, sin Redis, sin red — funciones puras.
"""
import pytest

from services.channels.events import (
    EVENT_CALLBACK,
    EVENT_MESSAGE,
    ChannelEvent,
    InvalidEvent,
    job_id_for,
)
from services.channels.registry import UnknownChannel, normalize
from services.channels.telegram.inbound import normalize as normalize_telegram

RECEIVED_AT = 1753440000

TEXT_UPDATE = {
    "update_id": 423934621,
    "message": {
        "message_id": 293,
        "date": 1753439000,
        "from": {
            "id": 123456789,
            "username": "ivanvallejoss",
            "first_name": "Ivan",
            "last_name": "Vallejos",
        },
        "chat": {"id": 123456789, "type": "private"},
        "text": "almuerzo 3500",
    },
}

CALLBACK_UPDATE = {
    "update_id": 423934622,
    "callback_query": {
        "id": "4382abc",
        "from": {"id": 123456789, "username": "ivanvallejoss", "first_name": "Ivan"},
        "data": "cat_select:55:3",
        "message": {
            "message_id": 294,
            "date": 1753439100,
            "chat": {"id": 123456789, "type": "private"},
        },
    },
}


class TestMensajeDeTexto:
    def test_mapea_los_campos_del_contrato(self):
        event = normalize_telegram(TEXT_UPDATE, received_at=RECEIVED_AT)

        assert event.channel == "telegram"
        assert event.external_user_id == "123456789"
        assert event.text == "almuerzo 3500"
        assert event.timestamp == 1753439000
        assert event.raw is TEXT_UPDATE

    def test_message_id_es_el_update_id_no_el_message_id_nativo(self):
        """
        D2: message.message_id es único por chat, no global.
        Usarlo como clave de idempotencia colisiona entre chats.
        """
        event = normalize_telegram(TEXT_UPDATE, received_at=RECEIVED_AT)
        assert event.message_id == "423934621"
        assert event.message_id != "293"

    def test_external_user_id_sale_de_from_no_de_chat(self):
        """D3: la identidad es la persona, no la conversación."""
        update = {
            **TEXT_UPDATE,
            "message": {**TEXT_UPDATE["message"], "chat": {"id": -100999, "type": "group"}},
        }
        event = normalize_telegram(update, received_at=RECEIVED_AT)

        assert event.external_user_id == "123456789"
        assert event.conversation_id == "-100999"

    def test_conversation_id_cae_al_usuario_si_no_hay_chat(self):
        update = {**TEXT_UPDATE, "message": {**TEXT_UPDATE["message"], "chat": {}}}
        event = normalize_telegram(update, received_at=RECEIVED_AT)
        assert event.conversation_id == "123456789"

    def test_extrae_el_perfil(self):
        event = normalize_telegram(TEXT_UPDATE, received_at=RECEIVED_AT)
        assert event.profile == {
            "username": "ivanvallejoss",
            "first_name": "Ivan",
            "last_name": "Vallejos",
        }

    def test_los_comandos_pasan_como_texto_plano(self):
        """El router de la Fase 4b distingue comandos; el normalizador no."""
        update = {**TEXT_UPDATE, "message": {**TEXT_UPDATE["message"], "text": "/stats"}}
        event = normalize_telegram(update, received_at=RECEIVED_AT)

        assert event.type == EVENT_MESSAGE
        assert event.text == "/stats"

    def test_sin_edit_ref_ni_ack_ref(self):
        event = normalize_telegram(TEXT_UPDATE, received_at=RECEIVED_AT)
        assert event.edit_ref is None
        assert event.ack_ref is None


class TestCallbackQuery:
    def test_el_callback_data_ocupa_el_lugar_del_texto(self):
        event = normalize_telegram(CALLBACK_UPDATE, received_at=RECEIVED_AT)

        assert event.type == EVENT_CALLBACK
        assert event.is_callback is True
        assert event.text == "cat_select:55:3"

    def test_expone_edit_ref_del_mensaje_original(self):
        """Necesario para replicar query.edit_message_text sin cambio visible."""
        event = normalize_telegram(CALLBACK_UPDATE, received_at=RECEIVED_AT)
        assert event.edit_ref == "294"

    def test_expone_ack_ref_para_answer_callback_query(self):
        """Sin esto Telegram deja el spinner del botón girando."""
        event = normalize_telegram(CALLBACK_UPDATE, received_at=RECEIVED_AT)
        assert event.ack_ref == "4382abc"

    def test_usa_la_hora_de_recepcion(self):
        """Telegram no informa cuándo se apretó el botón."""
        event = normalize_telegram(CALLBACK_UPDATE, received_at=RECEIVED_AT)
        assert event.timestamp == RECEIVED_AT

    def test_callback_sin_data_se_descarta(self):
        update = {
            "update_id": 1,
            "callback_query": {**CALLBACK_UPDATE["callback_query"], "data": None},
        }
        assert normalize_telegram(update, received_at=RECEIVED_AT) is None


class TestUpdatesIgnorados:
    """Todos estos hoy caen sin handler en PTB. Deben seguir cayendo."""

    @pytest.mark.parametrize(
        "payload",
        [
            {"message": {"text": "hola", "from": {"id": 1}}},  # sin update_id
            {"update_id": 1, "edited_message": {"text": "hola", "from": {"id": 1}}},
            {"update_id": 1, "channel_post": {"text": "hola"}},
            {"update_id": 1, "my_chat_member": {"from": {"id": 1}}},
            {"update_id": 1, "message": {"from": {"id": 1}, "photo": [{"file_id": "x"}]}},
            {"update_id": 1, "message": {"from": {"id": 1}, "sticker": {"file_id": "x"}}},
            {"update_id": 1, "message": {"text": "hola", "chat": {"id": 5}}},  # sin from
            {"update_id": 1},
        ],
    )
    def test_retorna_none(self, payload):
        assert normalize_telegram(payload, received_at=RECEIVED_AT) is None


class TestEventoCanonico:
    def test_roundtrip_dict(self):
        original = normalize_telegram(TEXT_UPDATE, received_at=RECEIVED_AT)
        recuperado = ChannelEvent.from_dict(original.to_dict())
        assert recuperado == original

    def test_to_dict_es_serializable_plano(self):
        event = normalize_telegram(TEXT_UPDATE, received_at=RECEIVED_AT)
        data = event.to_dict()

        assert isinstance(data, dict)
        assert set(data) == {
            "channel",
            "external_user_id",
            "text",
            "message_id",
            "timestamp",
            "raw",
            "type",
            "conversation_id",
            "edit_ref",
            "ack_ref",
            "profile",
        }

    def test_ids_numericos_se_coercionan_a_str(self):
        event = ChannelEvent(
            channel="telegram",
            external_user_id=123,
            text="x",
            message_id=456,
            timestamp=1,
            raw={},
        )
        assert event.external_user_id == "123"
        assert event.message_id == "456"

    def test_conversation_id_default_al_usuario(self):
        event = ChannelEvent(
            channel="telegram",
            external_user_id="123",
            text="x",
            message_id="1",
            timestamp=1,
            raw={},
        )
        assert event.conversation_id == "123"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"channel": ""},
            {"external_user_id": ""},
            {"message_id": ""},
            {"type": "inventado"},
        ],
    )
    def test_rechaza_eventos_invalidos(self, kwargs):
        base = dict(
            channel="telegram", external_user_id="1", text="x", message_id="1", timestamp=1, raw={}
        )
        with pytest.raises(InvalidEvent):
            ChannelEvent(**{**base, **kwargs})

    def test_job_id(self):
        event = normalize_telegram(TEXT_UPDATE, received_at=RECEIVED_AT)
        assert job_id_for(event) == "telegram:423934621"


class TestRegistry:
    def test_despacha_al_normalizador_del_canal(self):
        event = normalize("telegram", TEXT_UPDATE, received_at=RECEIVED_AT)
        assert event.channel == "telegram"

    def test_canal_desconocido_explota(self):
        """
        Falla ruidoso, no silencioso: un canal sin normalizador es un bug
        de configuración, no un mensaje descartable.
        """
        with pytest.raises(UnknownChannel):
            normalize("signal", {})

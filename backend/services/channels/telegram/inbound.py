"""
Traducción Telegram Update → evento canónico.

Funciones puras, sin I/O y sin dependencia de python-telegram-bot: recibe
el dict crudo tal cual lo manda Telegram.

Qué se ignora (retorna None), replicando lo que hoy descarta PTB por
ausencia de handler:
  - updates sin update_id
  - edited_message, channel_post, my_chat_member, etc.
  - mensajes sin texto (fotos, stickers, ubicaciones)
  - callback_query sin data
"""
import time
from typing import Any

from services.channels.events import EVENT_CALLBACK, EVENT_MESSAGE, ChannelEvent
from services.channels.telegram import CHANNEL


def normalize(payload: dict[str, Any], *, received_at: int | None = None) -> ChannelEvent | None:
    """
    Args:
        payload: Update crudo de Telegram
        received_at: epoch de recepción. Inyectable para tests.

    Returns:
        ChannelEvent, o None si el update no es procesable.
    """
    received_at = int(received_at if received_at is not None else time.time())

    update_id = payload.get("update_id")
    if update_id is None:
        return None

    # message_id de entrega: update_id es único global por bot.
    # message.message_id NO lo es — es único por chat (ver D2).
    message_id = str(update_id)

    if "callback_query" in payload:
        return _from_callback_query(payload, message_id, received_at)

    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("text"), str):
        return _from_message(payload, message, message_id, received_at)

    return None


def _from_message(payload, message, message_id, received_at) -> ChannelEvent | None:
    sender = message.get("from") or {}
    external_user_id = sender.get("id")
    if external_user_id is None:
        return None

    chat = message.get("chat") or {}

    return ChannelEvent(
        channel=CHANNEL,
        type=EVENT_MESSAGE,
        external_user_id=external_user_id,
        conversation_id=chat.get("id") or external_user_id,
        text=message["text"],
        message_id=message_id,
        # Telegram provee la hora de envío del mensaje.
        timestamp=message.get("date") or received_at,
        edit_ref=None,
        ack_ref=None,
        profile=_profile(sender),
        raw=payload,
    )


def _from_callback_query(payload, message_id, received_at) -> ChannelEvent | None:
    query = payload.get("callback_query") or {}
    sender = query.get("from") or {}
    external_user_id = sender.get("id")
    data = query.get("data")

    if external_user_id is None or not isinstance(data, str):
        return None

    source_message = query.get("message") or {}
    chat = source_message.get("chat") or {}

    return ChannelEvent(
        channel=CHANNEL,
        type=EVENT_CALLBACK,
        external_user_id=external_user_id,
        conversation_id=chat.get("id") or external_user_id,
        # El callback_data ocupa el lugar del texto: "del:55", "cat_select:12:3".
        # CALLBACK_ROUTES lo consume igual que hoy.
        text=data,
        message_id=message_id,
        # Telegram no informa cuándo se apretó el botón. Usamos la recepción.
        timestamp=received_at,
        edit_ref=_str_or_none(source_message.get("message_id")),
        ack_ref=_str_or_none(query.get("id")),
        profile=_profile(sender),
        raw=payload,
    )


def _profile(sender: dict[str, Any]) -> dict[str, Any]:
    """
    Forma neutral: {username, first_name, last_name}.
    WhatsApp llenará username="" y first_name con profile.name.
    """
    return {
        "username": sender.get("username") or "",
        "first_name": sender.get("first_name") or "",
        "last_name": sender.get("last_name") or "",
    }


def _str_or_none(value) -> str | None:
    return str(value) if value is not None else None
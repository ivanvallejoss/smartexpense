"""
Registro de normalizadores. Espejo simétrico de SENDERS (Fase 3).

Agregar WhatsApp = una entrada acá + un módulo inbound. Cero cambios
en el webhook ni en el worker.
"""
from typing import Any, Callable

from services.channels.events import ChannelEvent
from services.channels.telegram import CHANNEL as TELEGRAM
from services.channels.telegram.inbound import normalize as normalize_telegram

Normalizer = Callable[..., ChannelEvent | None]

NORMALIZERS: dict[str, Normalizer] = {
    TELEGRAM: normalize_telegram,
}


class UnknownChannel(KeyError):
    """Canal sin normalizador registrado."""


def normalize(channel: str, payload: dict[str, Any], **kwargs) -> ChannelEvent | None:
    """
    Punto de entrada único. El Bridge del gateway Go llamará
    normalize(envelope["source"], envelope["payload"]).
    """
    try:
        normalizer = NORMALIZERS[channel]
    except KeyError:
        raise UnknownChannel(f"Sin normalizador para el canal {channel!r}") from None
    return normalizer(payload, **kwargs)
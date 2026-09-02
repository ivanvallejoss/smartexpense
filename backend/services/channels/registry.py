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
    Punto de entrada único, y le pertenece al productor: quien recibe el payload
    crudo lo normaliza acá y encola el evento canónico. El worker nunca ve un
    payload crudo (multichannel_refactor.md, punto 2).

    Hoy el productor es el webhook de Django. Cuando aterrice v2 será el Bridge
    Python: el gateway Go es platform-agnostic y reenvía el payload sin tocarlo,
    así que normalizar sigue siendo trabajo de este lado (D6).
    """
    try:
        normalizer = NORMALIZERS[channel]
    except KeyError:
        raise UnknownChannel(f"Sin normalizador para el canal {channel!r}") from None
    return normalizer(payload, **kwargs)


def build_default_senders() -> None:
    """
    Registra los senders disponibles. Se llama una vez en el startup del worker.

    Agregar WhatsApp = dos líneas acá. El worker no se entera.
    """
    from services.channels.senders import register
    from services.channels.telegram.outbound import build_sender as build_telegram

    register(build_telegram())

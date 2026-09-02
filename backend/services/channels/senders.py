"""
Despacho de salida: cómo el worker le responde al usuario, sin saber
en qué canal está.

SENDERS se puebla en el arranque del worker (no en import time: construir
un cliente de Telegram requiere token y ciclo de vida async).
"""
import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Option:
    """
    Acción ofrecida al usuario, neutral al canal.

    id: vuelve como event.text cuando el usuario la elige.
        Formato "accion:payload", consumido por CALLBACK_ROUTES.
    """

    id: str
    label: str


Rows = list[list[Option]]


def row(*options: Option) -> Rows:
    """Una fila con las opciones dadas."""
    return [list(options)]


def grid(options: list[Option], columns: int = 2) -> Rows:
    """Distribuye en filas de `columns`. La última puede quedar incompleta."""
    return [options[i : i + columns] for i in range(0, len(options), columns)]


class OptionsNotSupported(ValueError):
    """
    El canal no puede renderizar esta cantidad/forma de opciones.

    Existe para que un canal con límites duros (WhatsApp: 3 botones, o
    listas de 10 por sección) falle ruidoso en vez de truncar en silencio.
    """


@runtime_checkable
class Sender(Protocol):
    channel: str

    async def reply(
        self,
        conversation_id: str,
        text: str,
        *,
        options: Rows | None = None,
        parse_mode: str | None = None,
        disable_preview: bool = False,
    ) -> str | None:
        """
        Envía un mensaje. Retorna el id del mensaje enviado, si el canal lo provee.

        El primer parámetro es el camino de respuesta, no la identidad de quien
        escribió. En Telegram privado from.id y chat.id coinciden y la distinción
        es invisible; en WhatsApp el lid del remitente y el chat_jid del chat son
        valores distintos. Se responde al segundo.

        disable_preview suprime la vista previa del link. Canales sin este
        concepto lo ignoran en silencio, mismo criterio que ack().
        """
        ...

    async def edit(
        self,
        conversation_id: str,
        edit_ref: str,
        *,
        text: str | None = None,
        options: Rows | None = None,
        parse_mode: str | None = None,
    ) -> None:
        """
        Modifica un mensaje ya enviado.

        conversation_id es el camino de respuesta, con el mismo criterio que en
        reply(): destino, no identidad.

        text=None cambia solo las opciones, conservando el texto.
        Canales sin edición (WhatsApp) deben emular enviando uno nuevo.
        """
        ...

    async def ack(self, ack_ref: str, text: str = "", *, alert: bool = False) -> None:
        """
        Acusa recibo de una acción. Canales sin este concepto: no-op.
        Nunca debe propagar excepción: fallar el ack no puede tumbar el job.
        """
        ...

    async def startup(self) -> None:
        ...

    async def shutdown(self) -> None:
        ...


SENDERS: dict[str, Sender] = {}


class UnknownChannel(KeyError):
    """Canal sin sender registrado."""


def register(sender: Sender) -> None:
    if sender.channel in SENDERS:
        logger.warning("Sender de %r sobrescrito", sender.channel)
    SENDERS[sender.channel] = sender


def get_sender(channel: str) -> Sender:
    try:
        return SENDERS[channel]
    except KeyError:
        raise UnknownChannel(f"Sin sender registrado para el canal {channel!r}") from None


async def startup_all() -> None:
    for channel, sender in SENDERS.items():
        await sender.startup()
        logger.info("Sender iniciado", extra={"channel": channel})


async def shutdown_all() -> None:
    for channel, sender in SENDERS.items():
        try:
            await sender.shutdown()
        except Exception:
            logger.warning("Fallo cerrando el sender de %r", channel, exc_info=True)
    SENDERS.clear()

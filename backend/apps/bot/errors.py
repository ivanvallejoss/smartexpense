"""
Mensajes de error al usuario.

El error_handler de PTB desaparece: su rol lo cumple el try/except del
router en la Fase 4b.
"""
import logging

from services.channels.events import ChannelEvent
from services.channels.senders import Sender

logger = logging.getLogger(__name__)

MENSAJE_ERROR_GENERICO = "Ocurrió un error al procesar tu mensaje. Por favor, intentá de nuevo."


async def error_parsing_expenses(event: ChannelEvent, sender: Sender) -> None:
    """El parser no encontró un monto en el mensaje."""
    error_message = (
        "No pude detectar el monto en tu mensaje.\n\n"
        "Formato correcto:\n"
        '• "Pizza 2000"\n'
        '• "$500 café"\n'
        '• "1500 uber"\n\n'
        "Probá de nuevo o enviá /help para más info."
    )

    logger.warning(
        "Failed to parse expense",
        extra={
            "channel": event.channel,
            "external_user_id": event.external_user_id,
            "message_text": event.text,
        },
    )

    await sender.reply(event.conversation_id, error_message)
"""
Router de despacho: decide qué handler atiende cada evento canónico.

Reemplaza a CommandHandler, MessageHandler y CallbackQueryHandler de PTB.
Vive separado de routing.py para evitar el ciclo de imports: handlers.py
importa split_command desde routing.
"""
import logging

from services.channels.events import ChannelEvent
from services.channels.senders import Sender

from apps.bot.handlers.callbacks import central_callback_handler
from apps.bot.handlers.handlers import (
    handle_message,
    help_command,
    history_command,
    link_command,
    start_command,
    stats_command,
)
from apps.bot.routing import split_command

logger = logging.getLogger(__name__)


COMMAND_ROUTES = {
    "start": start_command,
    "help": help_command,
    "stats": stats_command,
    "history": history_command,
    "link": link_command,
}


async def dispatch(event: ChannelEvent, user, sender: Sender) -> None:
    """
    Enruta el evento al handler correspondiente.

    Un comando no registrado se ignora en silencio: hoy PTB hace lo mismo,
    porque MessageHandler filtra con ~filters.COMMAND y ningún
    CommandHandler matchea. Responder algo sería un cambio visible.
    """
    if event.is_callback:
        await central_callback_handler(event, user, sender)
        return

    command, _ = split_command(event.text)

    if command is None:
        await handle_message(event, user, sender)
        return

    handler = COMMAND_ROUTES.get(command)

    if handler is None:
        logger.info(
            "Comando desconocido ignorado",
            extra={"command": command, "channel": event.channel, "user_id": user.id},
        )
        return

    await handler(event, user, sender)
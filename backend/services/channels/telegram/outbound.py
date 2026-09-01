"""
Adapter de salida de Telegram.

Único punto del sistema donde vive python-telegram-bot. Se usa como cliente
HTTP de la API — no como dispatcher (ver D1). El worker nunca lo importa.
"""
import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

from services.channels.senders import Option, Rows
from services.channels.telegram import CHANNEL

logger = logging.getLogger(__name__)

# Telegram devuelve este mensaje cuando el contenido de la edición es idéntico
# al actual. No es un error operativo: es doble click del usuario.
_NOT_MODIFIED = "message is not modified"


class TelegramSender:
    channel = CHANNEL

    def __init__(self, token: str):
        if not token:
            raise ValueError("TELEGRAM_TOKEN no está configurado")
        self._bot = Bot(token=token)

    async def startup(self) -> None:
        await self._bot.initialize()

    async def shutdown(self) -> None:
        await self._bot.shutdown()

    async def reply(
        self,
        conversation_id: str,
        text: str,
        *,
        options: Rows | None = None,
        parse_mode: str | None = None,
        disable_preview: bool = False,
    ) -> str | None:
        # El flag viaja solo cuando se pide. Mandarlo siempre haría que este
        # adapter fije el default de PTB, que es de PTB y no nuestro; además
        # disable_web_page_preview y link_preview_options son mutuamente
        # excluyentes, así que no ocupar el lugar sin necesidad deja libre la
        # modernización del llamado.
        preview = {"disable_web_page_preview": True} if disable_preview else {}
        message = await self._bot.send_message(
            chat_id=conversation_id,
            text=text,
            reply_markup=_to_markup(options),
            parse_mode=parse_mode,
            **preview,
        )
        return str(message.message_id)

    async def edit(
        self,
        conversation_id: str,
        edit_ref: str,
        *,
        text: str | None = None,
        options: Rows | None = None,
        parse_mode: str | None = None,
    ) -> None:
        try:
            if text is None:
                # Cambia solo los botones, conserva el texto.
                # Replica query.edit_message_reply_markup (on_cat_list_click).
                await self._bot.edit_message_reply_markup(
                    chat_id=conversation_id,
                    message_id=int(edit_ref),
                    reply_markup=_to_markup(options),
                )
            else:
                await self._bot.edit_message_text(
                    chat_id=conversation_id,
                    message_id=int(edit_ref),
                    text=text,
                    reply_markup=_to_markup(options),
                    parse_mode=parse_mode,
                )
        except BadRequest as exc:
            if _NOT_MODIFIED in str(exc).lower():
                logger.debug("Edición sin cambios, ignorada", extra={"edit_ref": edit_ref})
                return
            raise

    async def ack(self, ack_ref: str, text: str = "", *, alert: bool = False) -> None:
        """
        answerCallbackQuery caduca a los ~60s. Un ack vencido no debe
        propagar: el trabajo real ya se hizo. Hoy PTB lo tapa con el
        error_handler; acá lo hacemos explícito.
        """
        try:
            await self._bot.answer_callback_query(
                callback_query_id=ack_ref,
                text=text or None,
                show_alert=alert,
            )
        except Exception:
            logger.warning("Fallo el ack del callback", extra={"ack_ref": ack_ref}, exc_info=True)


def _to_markup(options: Rows | None) -> InlineKeyboardMarkup | None:
    if not options:
        return None
    return InlineKeyboardMarkup([
        [_to_button(option) for option in fila]
        for fila in options
    ])


def _to_button(option: Option) -> InlineKeyboardButton:
    return InlineKeyboardButton(option.label, callback_data=option.id)


def build_sender() -> TelegramSender:
    """Fábrica desde settings. Se llama en el startup del worker."""
    from django.conf import settings
    return TelegramSender(token=settings.TELEGRAM_TOKEN)
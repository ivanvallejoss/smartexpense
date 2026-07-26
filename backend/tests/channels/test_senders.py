"""
Tests del dispatcher de salida. Sin red: el Bot de PTB se reemplaza por
un AsyncMock, lo que además verifica que el adapter llame a la API con
exactamente los argumentos que usa el código actual.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from telegram.error import BadRequest

from services.channels.senders import (
    SENDERS,
    Option,
    UnknownChannel,
    get_sender,
    grid,
    register,
    row,
)
from services.channels.telegram.outbound import TelegramSender, _to_markup


@pytest.fixture
def sender():
    s = TelegramSender(token="fake-token")
    s._bot = AsyncMock()
    s._bot.send_message.return_value = MagicMock(message_id=294)
    return s


@pytest.fixture(autouse=True)
def registro_limpio():
    previo = dict(SENDERS)
    SENDERS.clear()
    yield
    SENDERS.clear()
    SENDERS.update(previo)


class TestRegistro:

    def test_get_sender_devuelve_el_registrado(self):
        s = TelegramSender(token="x")
        register(s)
        assert get_sender("telegram") is s

    def test_canal_sin_sender_explota(self):
        with pytest.raises(UnknownChannel):
            get_sender("whatsapp")

    def test_token_vacio_falla_al_construir(self):
        """Mejor fallar en el startup que en el primer mensaje del usuario."""
        with pytest.raises(ValueError):
            TelegramSender(token="")


class TestLayout:

    def test_row_arma_una_sola_fila(self):
        filas = row(Option("a", "A"), Option("b", "B"))
        assert len(filas) == 1
        assert len(filas[0]) == 2

    def test_grid_reparte_de_a_dos(self):
        opciones = [Option(str(i), str(i)) for i in range(5)]
        filas = grid(opciones, columns=2)
        assert [len(f) for f in filas] == [2, 2, 1]

    def test_grid_mas_row_preserva_el_layout_de_categorias(self):
        """
        Con 3 categorías: dos filas de categorías (2 + 1) y 'Nueva' sola.
        Una lista plana de a 2 aparearía la última categoría con 'Nueva'.
        """
        cats = [Option(f"cat_select:1:{i}", f"Cat{i}") for i in range(3)]
        filas = grid(cats, 2) + row(Option("cat_new:1", "➕ Nueva categoría"))

        assert [len(f) for f in filas] == [2, 1, 1]
        assert filas[-1][0].label == "➕ Nueva categoría"

    def test_sin_opciones_no_hay_markup(self):
        assert _to_markup(None) is None
        assert _to_markup([]) is None

    def test_option_id_viaja_como_callback_data(self):
        """El id vuelve como event.text y lo consume CALLBACK_ROUTES."""
        markup = _to_markup(row(Option("del:55", "Eliminar")))
        boton = markup.inline_keyboard[0][0]
        assert boton.callback_data == "del:55"
        assert boton.text == "Eliminar"


class TestReply:

    async def test_envia_texto_plano(self, sender):
        await sender.reply("123", "hola")

        sender._bot.send_message.assert_awaited_once_with(
            chat_id="123", text="hola", reply_markup=None, parse_mode=None
        )

    async def test_retorna_el_id_del_mensaje_enviado(self, sender):
        assert await sender.reply("123", "hola") == "294"

    async def test_propaga_parse_mode(self, sender):
        """history_command y link_command dependen de HTML."""
        await sender.reply("123", "<b>x</b>", parse_mode="HTML")
        assert sender._bot.send_message.await_args.kwargs["parse_mode"] == "HTML"

    async def test_traduce_opciones_a_inline_keyboard(self, sender):
        await sender.reply("123", "hola", options=row(Option("del:55", "Eliminar")))

        markup = sender._bot.send_message.await_args.kwargs["reply_markup"]
        assert markup.inline_keyboard[0][0].callback_data == "del:55"


class TestEdit:

    async def test_edita_texto_y_botones(self, sender):
        await sender.edit("123", "294", text="nuevo", options=row(Option("del:55", "X")))

        sender._bot.edit_message_text.assert_awaited_once()
        kwargs = sender._bot.edit_message_text.await_args.kwargs
        assert kwargs["chat_id"] == "123"
        assert kwargs["message_id"] == 294
        assert kwargs["text"] == "nuevo"

    async def test_text_none_edita_solo_los_botones(self, sender):
        """Replica on_cat_list_click: cambia el teclado, conserva el texto."""
        await sender.edit("123", "294", options=row(Option("cat_select:1:2", "Comida")))

        sender._bot.edit_message_reply_markup.assert_awaited_once()
        sender._bot.edit_message_text.assert_not_awaited()

    async def test_message_is_not_modified_se_traga(self, sender):
        """Doble click del usuario. Hoy lo tapa el error_handler de PTB."""
        sender._bot.edit_message_text.side_effect = BadRequest("Message is not modified")
        await sender.edit("123", "294", text="igual")  # no debe levantar

    async def test_otros_bad_request_se_propagan(self, sender):
        sender._bot.edit_message_text.side_effect = BadRequest("Chat not found")
        with pytest.raises(BadRequest):
            await sender.edit("123", "294", text="x")


class TestAck:

    async def test_ack_mudo(self, sender):
        await sender.ack("4382abc")

        sender._bot.answer_callback_query.assert_awaited_once_with(
            callback_query_id="4382abc", text=None, show_alert=False
        )

    async def test_ack_con_alerta(self, sender):
        await sender.ack("4382abc", "⚠️ Error", alert=True)

        kwargs = sender._bot.answer_callback_query.await_args.kwargs
        assert kwargs["text"] == "⚠️ Error"
        assert kwargs["show_alert"] is True

    async def test_ack_vencido_no_tumba_el_job(self, sender):
        """
        answerCallbackQuery caduca a los ~60s. El trabajo real ya se hizo;
        fallar acá perdería el efecto por un detalle cosmético.
        """
        sender._bot.answer_callback_query.side_effect = BadRequest("Query is too old")
        await sender.ack("4382abc")  # no debe levantar


class TestCicloDeVida:

    async def test_startup_y_shutdown_delegan_en_el_bot(self, sender):
        await sender.startup()
        await sender.shutdown()

        sender._bot.initialize.assert_awaited_once()
        sender._bot.shutdown.assert_awaited_once()
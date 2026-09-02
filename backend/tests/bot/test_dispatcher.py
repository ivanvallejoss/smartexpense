"""
Tests del router de despacho. Reemplazan implícitamente a lo que antes
garantizaba el registro de handlers de PTB en setup.py.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.bot.dispatcher import dispatch


@pytest.fixture
def user():
    """El router no toca la DB: alcanza un doble."""
    u = MagicMock()
    u.id = 1
    return u


@pytest.fixture
def handlers():
    """Parchea todos los handlers y devuelve los mocks por nombre."""
    nombres = [
        "start_command",
        "help_command",
        "stats_command",
        "history_command",
        "link_command",
        "handle_message",
        "central_callback_handler",
    ]
    patches = {n: patch(f"apps.bot.dispatcher.{n}", new=AsyncMock()) for n in nombres}
    mocks = {n: p.start() for n, p in patches.items()}

    # COMMAND_ROUTES capturó las funciones originales al importarse
    with patch.dict(
        "apps.bot.dispatcher.COMMAND_ROUTES",
        {
            "start": mocks["start_command"],
            "help": mocks["help_command"],
            "stats": mocks["stats_command"],
            "history": mocks["history_command"],
            "link": mocks["link_command"],
        },
    ):
        yield mocks

    for p in patches.values():
        p.stop()


class TestComandos:
    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("/start", "start_command"),
            ("/help", "help_command"),
            ("/stats", "stats_command"),
            ("/history", "history_command"),
            ("/link", "link_command"),
        ],
    )
    async def test_rutea_cada_comando(self, texto, esperado, make_event, user, sender, handlers):
        await dispatch(make_event(texto), user, sender)
        handlers[esperado].assert_awaited_once()

    async def test_comando_con_argumentos(self, make_event, user, sender, handlers):
        await dispatch(make_event("/history 15"), user, sender)
        handlers["history_command"].assert_awaited_once()

    async def test_comando_con_mencion_al_bot(self, make_event, user, sender, handlers):
        """Telegram agrega @BotName en grupos."""
        await dispatch(make_event("/stats@SmartExpenseBot"), user, sender)
        handlers["stats_command"].assert_awaited_once()

    async def test_comando_en_mayusculas(self, make_event, user, sender, handlers):
        await dispatch(make_event("/STATS"), user, sender)
        handlers["stats_command"].assert_awaited_once()

    async def test_comando_desconocido_se_ignora_en_silencio(
        self, make_event, user, sender, handlers
    ):
        """
        PTB hoy no responde nada: MessageHandler filtra con ~filters.COMMAND
        y ningún CommandHandler matchea. Responder sería un cambio visible.
        """
        await dispatch(make_event("/inventado"), user, sender)

        for mock in handlers.values():
            mock.assert_not_awaited()
        assert sender.replies == []


class TestTextoLibre:
    async def test_texto_va_a_handle_message(self, make_event, user, sender, handlers):
        await dispatch(make_event("almuerzo 3500"), user, sender)
        handlers["handle_message"].assert_awaited_once()

    async def test_barra_sola_es_texto_no_comando(self, make_event, user, sender, handlers):
        await dispatch(make_event("/"), user, sender)
        handlers["handle_message"].assert_awaited_once()

    async def test_texto_que_empieza_con_barra_en_medio(self, make_event, user, sender, handlers):
        await dispatch(make_event("pague 500 al 50/50"), user, sender)
        handlers["handle_message"].assert_awaited_once()


class TestCallbacks:
    async def test_callback_va_al_router_de_acciones(
        self, make_callback_event, user, sender, handlers
    ):
        await dispatch(make_callback_event("del:55"), user, sender)

        handlers["central_callback_handler"].assert_awaited_once()
        handlers["handle_message"].assert_not_awaited()

    async def test_callback_que_parece_comando_no_se_confunde(
        self, make_callback_event, user, sender, handlers
    ):
        """El type manda, no el contenido del texto."""
        await dispatch(make_callback_event("/start"), user, sender)

        handlers["central_callback_handler"].assert_awaited_once()
        handlers["start_command"].assert_not_awaited()

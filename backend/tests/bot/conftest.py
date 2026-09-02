from unittest.mock import AsyncMock, patch

import pytest
from tests.constants import EXTERNAL_USER_ID

from services.channels.events import EVENT_CALLBACK, EVENT_MESSAGE, ChannelEvent


@pytest.fixture(autouse=True)
def mock_redis_state():
    """
    Estado conversacional mockeado para todos los tests del bot.
    Sin esto, cualquier test que ejecute handle_message falla porque
    Redis no está disponible en el entorno de tests.
    """
    with patch(
        "apps.bot.handlers.handlers.get_pending_category_state",
        new=AsyncMock(return_value=None),
    ) as mock_get, patch(
        "apps.bot.handlers.handlers.clear_pending_category_state",
        new=AsyncMock(return_value=None),
    ) as mock_clear:
        yield {"get": mock_get, "clear": mock_clear}


class FakeSender:
    """
    Sender de test que registra lo enviado en vez de hablar con una API.

    Deliberadamente no es un MagicMock: las aserciones quedan legibles
    y valida que los handlers no dependan de nada específico de Telegram.
    """

    channel = "test"

    def __init__(self):
        self.replies = []
        self.edits = []
        self.acks = []

    async def reply(
        self, conversation_id, text, *, options=None, parse_mode=None, disable_preview=False
    ):
        self.replies.append(
            {
                "to": conversation_id,
                "text": text,
                "options": options,
                "parse_mode": parse_mode,
                "disable_preview": disable_preview,
            }
        )
        return str(len(self.replies))

    async def edit(self, conversation_id, edit_ref, *, text=None, options=None, parse_mode=None):
        self.edits.append(
            {
                "to": conversation_id,
                "edit_ref": edit_ref,
                "text": text,
                "options": options,
                "parse_mode": parse_mode,
            }
        )

    async def ack(self, ack_ref, text="", *, alert=False):
        self.acks.append({"ack_ref": ack_ref, "text": text, "alert": alert})

    async def startup(self):
        ...

    async def shutdown(self):
        ...

    # --- helpers de aserción ---

    @property
    def last_reply(self):
        return self.replies[-1]

    @property
    def last_edit(self):
        return self.edits[-1]

    @property
    def last_ack(self):
        return self.acks[-1]

    def callback_ids(self, source: dict) -> list[str]:
        """Ids de las Options de un reply/edit, aplanados."""
        return [opt.id for fila in (source["options"] or []) for opt in fila]


@pytest.fixture
def sender():
    return FakeSender()


@pytest.fixture
def make_event():
    def _make(text="", *, type=EVENT_MESSAGE, edit_ref=None, ack_ref=None, **kwargs):
        defaults = dict(
            channel="telegram",
            external_user_id=EXTERNAL_USER_ID,
            conversation_id=EXTERNAL_USER_ID,
            text=text,
            message_id="423934621",
            timestamp=1753440000,
            raw={},
            profile={"username": "test_user", "first_name": "Test", "last_name": "User"},
        )
        defaults.update(kwargs)
        return ChannelEvent(type=type, edit_ref=edit_ref, ack_ref=ack_ref, **defaults)

    return _make


@pytest.fixture
def make_callback_event(make_event):
    def _make(data: str):
        return make_event(data, type=EVENT_CALLBACK, edit_ref="294", ack_ref="4382abc")

    return _make


@pytest.fixture
async def user():
    from apps.core.models import ChannelIdentity, User

    u = await User.objects.acreate(username="test_user", telegram_id=int(EXTERNAL_USER_ID))
    await ChannelIdentity.objects.acreate(user=u, channel="telegram", external_id=EXTERNAL_USER_ID)
    return u

import pytest
from unittest.mock import AsyncMock, patch

from apps.bot.state import (
    set_pending_category_state,
    get_pending_category_state,
    clear_pending_category_state,
    STATE_TTL,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
async def mock_redis():
    """
    Mock del pool centralizado de Redis.
    Un solo punto de mock para todos los tests del módulo.
    """
    with patch("apps.bot.state.get_redis") as mock_get:
        redis = AsyncMock()
        mock_get.return_value = redis
        yield redis


class TestSetPendingCategoryState:

    async def test_sets_correct_key_with_ttl(self, mock_redis):
        """
        Verifica el contrato completo de escritura:
        clave con formato correcto, valor correcto, TTL configurado.
        """
        await set_pending_category_state(
            telegram_user_id=123,
            expense_id=456
        )

        mock_redis.set.assert_called_once_with(
            "cat_state:123",
            456,
            ex=STATE_TTL
        )


class TestGetPendingCategoryState:

    async def test_returns_expense_id_when_state_exists(self, mock_redis):
        mock_redis.get.return_value = b"456"

        result = await get_pending_category_state(telegram_user_id=123)

        assert result == 456
        mock_redis.get.assert_called_once_with("cat_state:123")

    async def test_returns_none_when_no_state(self, mock_redis):
        """
        Un usuario sin estado pendiente no debe bloquear el flujo normal
        de handle_message — debe recibir None limpiamente.
        """
        mock_redis.get.return_value = None

        result = await get_pending_category_state(telegram_user_id=123)

        assert result is None


class TestClearPendingCategoryState:

    async def test_deletes_correct_key(self, mock_redis):
        await clear_pending_category_state(telegram_user_id=123)

        mock_redis.delete.assert_called_once_with("cat_state:123")
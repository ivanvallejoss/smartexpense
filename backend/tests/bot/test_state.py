import pytest
from unittest.mock import AsyncMock, patch

from apps.bot.state import (
    STATE_TTL,
    clear_pending_category_state,
    get_pending_category_state,
    set_pending_category_state,
)

pytestmark = pytest.mark.django_db(transaction=True)

TG = "telegram"
UID = "123"

KEY = "cat_state:telegram:123"
LEGACY_KEY = "cat_state:123"


@pytest.fixture
async def redis():
    """Mock del pool centralizado. Un solo punto de mock para el módulo."""
    with patch("apps.bot.state.get_redis") as mock_get:
        r = AsyncMock()
        r.mget.return_value = [None, None]
        mock_get.return_value = r
        yield r


class TestSet:

    async def test_escribe_la_clave_namespaced_con_ttl(self, redis):
        await set_pending_category_state(TG, UID, expense_id=456)

        redis.set.assert_called_once_with(KEY, 456, ex=STATE_TTL)

    async def test_canales_distintos_no_comparten_estado(self, redis):
        """El mismo id nativo en dos canales son dos personas distintas."""
        await set_pending_category_state("whatsapp", UID, expense_id=456)

        assert redis.set.call_args[0][0] == "cat_state:whatsapp:123"


class TestGet:

    async def test_sin_estado_devuelve_none(self, redis):
        assert await get_pending_category_state(TG, UID) is None

    async def test_lee_el_formato_nuevo(self, redis):
        redis.mget.return_value = [b"456", None]

        assert await get_pending_category_state(TG, UID) == 456

    async def test_una_sola_ida_a_redis(self, redis):
        """
        Camino caliente: se ejecuta en cada mensaje de texto. El fallback
        al formato viejo no debe costar un round-trip extra.
        """
        await get_pending_category_state(TG, UID)

        redis.mget.assert_called_once_with(KEY, LEGACY_KEY)
        redis.get.assert_not_called()

    async def test_fallback_al_formato_viejo(self, redis):
        """Estados en vuelo al momento del deploy no se pierden."""
        redis.mget.return_value = [None, b"789"]

        assert await get_pending_category_state(TG, UID) == 789

    async def test_el_formato_nuevo_tiene_prioridad(self, redis):
        redis.mget.return_value = [b"456", b"789"]

        assert await get_pending_category_state(TG, UID) == 456


class TestClear:

    async def test_borra_ambos_formatos(self, redis):
        """
        Si quedara la clave vieja, el fallback la resucitaría en la
        próxima lectura y el usuario quedaría atrapado en el flujo.
        """
        await clear_pending_category_state(TG, UID)

        redis.delete.assert_called_once_with(KEY, LEGACY_KEY)
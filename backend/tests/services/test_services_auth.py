from unittest.mock import AsyncMock, patch

import pytest

from services.auth import _MAX_INTENTOS, GrantCollision, _generate_token, consume_grant, issue_grant
from services.constants import (
    CHANNEL_LINK_DIGITS,
    GRANT_TTL,
    PURPOSE_CHANNEL_LINK,
    PURPOSE_WEB_ACCESS,
)

TG = "telegram"
UID = "123"


@pytest.fixture
async def redis():
    """
    Mock del pool centralizado. Un solo punto de mock para el módulo, mismo
    patrón que tests/bot/test_state.py.

    set y getdel van contra un dict en vez de devolver valores fijos: lo que
    estos tests tienen que afirmar es qué clave se tocó y qué quedó vivo
    después, y con returns fijos eso no se puede distinguir de un no-op.
    """
    store: dict[str, str] = {}

    async def fake_set(key, value, *, ex=None, nx=False):
        if nx and key in store:
            return None
        store[key] = value
        return True

    async def fake_getdel(key):
        return store.pop(key, None)

    with patch("services.auth.get_redis") as mock_get:
        r = AsyncMock()
        r.set.side_effect = fake_set
        r.getdel.side_effect = fake_getdel
        r.store = store
        mock_get.return_value = r
        yield r


class TestIssueGrant:
    async def test_escribe_con_nx_y_el_ttl_del_proposito(self, redis):
        token = await issue_grant(1, PURPOSE_WEB_ACCESS, TG, UID)

        redis.set.assert_called_once()
        args, kwargs = redis.set.call_args
        assert args[0] == f"grant:web_access:{token}"
        assert kwargs["nx"] is True
        assert kwargs["ex"] == GRANT_TTL[PURPOSE_WEB_ACCESS]

    async def test_cada_proposito_usa_su_propio_ttl(self, redis):
        await issue_grant(1, PURPOSE_CHANNEL_LINK, TG, UID)

        assert redis.set.call_args.kwargs["ex"] == GRANT_TTL[PURPOSE_CHANNEL_LINK]
        assert GRANT_TTL[PURPOSE_CHANNEL_LINK] != GRANT_TTL[PURPOSE_WEB_ACCESS]

    async def test_el_proposito_va_en_la_clave(self, redis):
        """
        Si el propósito viviera en el valor, el GETDEL tendría que destruir el
        grant para recién después poder rechazarlo por propósito.
        """
        token = await issue_grant(1, PURPOSE_CHANNEL_LINK, TG, UID)

        assert list(redis.store) == [f"grant:channel_link:{token}"]

    async def test_el_payload_lleva_el_emisor_para_auditoria(self, redis):
        token = await issue_grant(7, PURPOSE_WEB_ACCESS, TG, "999")

        payload = await consume_grant(token, PURPOSE_WEB_ACCESS)

        assert payload["user_id"] == 7
        assert payload["purpose"] == PURPOSE_WEB_ACCESS
        assert payload["issued_by_channel"] == TG
        assert payload["issued_by_external_id"] == "999"
        assert isinstance(payload["iat"], int)

    async def test_proposito_desconocido_levanta(self, redis):
        """La entropía no se hereda: un propósito nuevo sin declarar falla."""
        with pytest.raises(ValueError):
            await issue_grant(1, "inventado", TG, UID)

        redis.set.assert_not_called()


class TestConsumeGrant:
    async def test_con_el_proposito_correcto_devuelve_el_payload(self, redis):
        token = await issue_grant(42, PURPOSE_WEB_ACCESS, TG, UID)

        assert (await consume_grant(token, PURPOSE_WEB_ACCESS))["user_id"] == 42

    async def test_proposito_distinto_devuelve_none_y_no_consume(self, redis):
        """
        El test de la decisión de diseño de la clave.

        Alguien tanteando códigos de seis dígitos en el endpoint web no puede
        quemar grants de vinculación legítimos: el propósito equivocado ni
        siquiera nombra la clave del grant real.
        """
        token = await issue_grant(7, PURPOSE_CHANNEL_LINK, TG, UID)

        assert await consume_grant(token, PURPOSE_WEB_ACCESS) is None

        # El grant sobrevivió al intento con el propósito equivocado.
        assert (await consume_grant(token, PURPOSE_CHANNEL_LINK))["user_id"] == 7

    async def test_el_segundo_canje_devuelve_none(self, redis):
        token = await issue_grant(1, PURPOSE_WEB_ACCESS, TG, UID)

        assert await consume_grant(token, PURPOSE_WEB_ACCESS) is not None
        assert await consume_grant(token, PURPOSE_WEB_ACCESS) is None

    async def test_token_inexistente_devuelve_none(self, redis):
        """Vencido, ya usado e inexistente son el mismo None a propósito."""
        assert await consume_grant("no-existe", PURPOSE_WEB_ACCESS) is None


class TestColisionDeCodigo:
    async def test_reintenta_y_no_pisa_el_grant_existente(self, redis):
        primero = await issue_grant(1, PURPOSE_CHANNEL_LINK, TG, UID)

        with patch("services.auth._generate_token", side_effect=[primero, "999999"]):
            segundo = await issue_grant(2, PURPOSE_CHANNEL_LINK, TG, "456")

        assert segundo != primero
        assert redis.set.call_count == 3  # 1 del primero + 2 del segundo

        # Lo que NX protege: el dueño del primer código no lo perdió.
        assert (await consume_grant(primero, PURPOSE_CHANNEL_LINK))["user_id"] == 1
        assert (await consume_grant(segundo, PURPOSE_CHANNEL_LINK))["user_id"] == 2

    async def test_reintentos_agotados_levanta(self, redis):
        token = await issue_grant(1, PURPOSE_CHANNEL_LINK, TG, UID)

        with patch("services.auth._generate_token", return_value=token):
            with pytest.raises(GrantCollision):
                await issue_grant(2, PURPOSE_CHANNEL_LINK, TG, "456")

        # El grant original sigue intacto: fallar no destruyó nada.
        assert (await consume_grant(token, PURPOSE_CHANNEL_LINK))["user_id"] == 1

    async def test_no_reintenta_para_siempre(self, redis):
        token = await issue_grant(1, PURPOSE_CHANNEL_LINK, TG, UID)
        redis.set.reset_mock()

        with patch("services.auth._generate_token", return_value=token):
            with pytest.raises(GrantCollision):
                await issue_grant(2, PURPOSE_CHANNEL_LINK, TG, "456")

        assert redis.set.call_count == _MAX_INTENTOS


class TestEntropiaPorProposito:
    def test_el_codigo_de_channel_link_siempre_mide_seis(self):
        """
        Un código que a veces mide cinco dígitos es un bug de UX y una fuga de
        entropía: delata que el valor cayó bajo 100000.
        """
        for _ in range(200):
            token = _generate_token(PURPOSE_CHANNEL_LINK)

            assert len(token) == CHANNEL_LINK_DIGITS
            assert token.isdigit()

    def test_el_padding_es_de_ceros_a_la_izquierda(self):
        with patch("services.auth.secrets.randbelow", return_value=7):
            assert _generate_token(PURPOSE_CHANNEL_LINK) == "000007"

    def test_web_access_no_usa_la_entropia_de_channel_link(self):
        token = _generate_token(PURPOSE_WEB_ACCESS)

        assert len(token) > CHANNEL_LINK_DIGITS
        assert not token.isdigit()

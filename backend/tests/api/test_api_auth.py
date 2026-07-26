import jwt
import pytest
from datetime import datetime, timezone, timedelta

from django.conf import settings

from apps.api.auth import GlobalAuth


from tests.factories import UserFactory
from asgiref.sync import sync_to_async

pytestmark = pytest.mark.django_db(transaction=True)



def make_token(user_id, exp_delta=timedelta(days=1), secret=None, typ="magic_link_v2"):
    """Helper para generar tokens con parámetros controlados."""
    payload = {
        "sub": str(user_id),
        "typ": typ,
        "exp": datetime.now(timezone.utc) + exp_delta,
    }
    return jwt.encode(
        payload,
        secret or settings.JWT_SECRET_KEY,
        algorithm="HS256"
    )


class TestGlobalAuth:

    async def test_valid_token_returns_user(self):
        user = await sync_to_async(UserFactory)()
        token = make_token(user.user_id)

        auth = GlobalAuth()
        result = await auth.authenticate(None, token)

        assert result is not None
        assert result.id == user.id

    async def test_expired_token_returns_none(self):
        """
        Un token expirado debe ser rechazado silenciosamente.
        El sistema registra el error en logs pero no expone detalles al cliente.
        """
        user = await sync_to_async(UserFactory)()
        token = make_token(user.id, exp_delta=-timedelta(minutes=1))

        auth = GlobalAuth()
        result = await auth.authenticate(None, token)

        assert result is None

    async def test_invalid_signature_returns_none(self):
        user = await sync_to_async(UserFactory)()
        token = make_token(user.id, secret="clave-incorrecta")

        auth = GlobalAuth()
        result = await auth.authenticate(None, token)

        assert result is None

    async def test_valid_token_for_nonexistent_user_returns_none(self):
        """
        Un token criptográficamente válido pero cuyo usuario fue eliminado
        debe ser rechazado. El token no es suficiente — el usuario debe existir.
        """
        token = make_token(user_id=999999999)  # ID que no existe en DB

        auth = GlobalAuth()
        result = await auth.authenticate(None, token)

        assert result is None

    async def test_token_del_esquema_viejo_se_rechaza(self):
        """
        Tokens con sub=telegram_id y sin 'typ'. Sin este guard se leerian
        como User.id y podrian resolver a otro usuario.
        """
        user = await sync_to_async(UserFactory)()
        token = make_token(user.id, typ=None)

        auth = GlobalAuth()
        result = await auth.authenticate(None, token)

        assert result is None
# tests/services/test_auth.py

import jwt
import pytest
from datetime import datetime, timezone, timedelta
from django.conf import settings

from services.auth import generate_magic_link_token

pytestmark = pytest.mark.django_db(transaction=True)


class TestGenerateMagicLinkToken:

    def test_returns_decodable_string(self):
        token = generate_magic_link_token(telegram_id=12345)

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )

        assert payload is not None

    def test_payload_contains_telegram_id_as_string(self):
        token = generate_magic_link_token(telegram_id=12345)

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )

        assert payload["sub"] == "12345"
        assert isinstance(payload["sub"], str)

    def test_token_expires_in_15_minutes(self):
        before = datetime.now(timezone.utc)
        token = generate_magic_link_token(telegram_id=12345)
        after = datetime.now(timezone.utc)

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected_min = before + timedelta(minutes=14, seconds=59)
        expected_max = after + timedelta(minutes=15, seconds=1)

        assert expected_min <= exp <= expected_max

    def test_expired_token_is_not_decodable(self):
        """
        Un token expirado debe ser rechazado por PyJWT.
        Verificamos que el sistema no acepte tokens vencidos
        aunque la firma sea criptográficamente válida.
        """
        expired_payload = {
            "sub": "12345",
            "iat": datetime.now(timezone.utc) - timedelta(minutes=30),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=15),
        }
        expired_token = jwt.encode(
            expired_payload,
            settings.JWT_SECRET_KEY,
            algorithm="HS256"
        )

        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(
                expired_token,
                settings.JWT_SECRET_KEY,
                algorithms=["HS256"]
            )
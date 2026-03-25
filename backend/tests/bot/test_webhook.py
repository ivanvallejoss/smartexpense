# tests/bot/test_webhook.py

import json
import pytest
from unittest.mock import AsyncMock, patch
from django.test import AsyncClient
from django.conf import settings

pytestmark = pytest.mark.django_db(transaction=True)

WEBHOOK_URL = "/bot/webhook/"
VALID_PAYLOAD = {
    "update_id": 123456789,
    "message": {
        "message_id": 1,
        "from": {"id": 111, "first_name": "Ivan"},
        "text": "Pizza 2000"
    }
}


@pytest.fixture
def client():
    return AsyncClient()


def auth_headers():
    """Headers con el secret token correcto."""
    return {"X-Telegram-Bot-Api-Secret-Token": settings.TELEGRAM_WEBHOOK_TOKEN}


# ============================================
# TESTS
# ============================================

class TestWebhook:

    @patch("services.infraestructure.redis_client.get_redis")
    async def test_valid_request_enqueues_job_and_returns_200(
        self, mock_pool, client
    ):
        """
        Camino feliz: secret correcto, JSON válido, Redis disponible.
        Verifica el contrato de llamada a Redis sin depender de infraestructura.
        """
        mock_redis = AsyncMock()
        mock_pool.return_value = mock_redis

        response = await client.post(
            WEBHOOK_URL,
            data=json.dumps(VALID_PAYLOAD),
            content_type="application/json",
            **auth_headers()
        )

        assert response.status_code == 200
        mock_redis.enqueue_job.assert_called_once_with(
            "process_telegram_message", VALID_PAYLOAD
        )

    async def test_wrong_http_method_returns_405(self, client):
        response = await client.get(WEBHOOK_URL, **auth_headers())
        assert response.status_code == 405

    async def test_missing_secret_token_returns_403(self, client):
        response = await client.post(
            WEBHOOK_URL,
            data=json.dumps(VALID_PAYLOAD),
            content_type="application/json"
            # sin headers de autenticación
        )
        assert response.status_code == 403

    async def test_wrong_secret_token_returns_403(self, client):
        response = await client.post(
            WEBHOOK_URL,
            data=json.dumps(VALID_PAYLOAD),
            content_type="application/json",
            **{"X-Telegram-Bot-Api-Secret-Token": "token-equivocado"}
        )
        assert response.status_code == 403

    async def test_malformed_json_returns_400(self, client):
        response = await client.post(
            WEBHOOK_URL,
            data="esto no es json {{{",
            content_type="application/json",
            **auth_headers()
        )
        assert response.status_code == 400

    @patch("apps.bot.views.get_redis_pool")
    async def test_redis_failure_still_returns_200(
        self, mock_pool, client
    ):
        """
        Cuando Redis falla, el webhook devuelve 200 igual.
        Decisión de diseño: Telegram no debe reintentar — el mensaje
        se pierde silenciosamente en lugar de generar un loop de reintentos.
        """
        mock_redis = AsyncMock()
        mock_redis.enqueue_job.side_effect = Exception("Redis connection refused")
        mock_pool.return_value = mock_redis

        response = await client.post(
            WEBHOOK_URL,
            data=json.dumps(VALID_PAYLOAD),
            content_type="application/json",
            **auth_headers()
        )

        assert response.status_code == 200
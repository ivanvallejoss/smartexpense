import json
import pytest
from unittest.mock import AsyncMock, patch
from django.test import RequestFactory
from django.conf import settings

from apps.bot.views  import webhook

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
def factory():
    return RequestFactory()

def make_request(factory, method="post", data=None, secret=None):
    """
    Helper para construir requests con los headers correctos.
    """
    headers = {}
    if secret is not False:
        headers["HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"] = (
            secret or settings.TELEGRAM_WEBHOOK_TOKEN
        )
    
    body = json.dumps(data or VALID_PAYLOAD)

    if method == "post":
        return factory.post(
            WEBHOOK_URL,
            data=body,
            content_type="application/json",
            **headers
        )
    return factory.get(WEBHOOK_URL, **headers)


# ============================================
# TESTS
# ============================================

class TestWebhook:

    @patch("services.infrastructure.redis_client.get_redis")
    async def test_valid_request_enqueues_job_and_returns_200(
        self, mock_pool, client
    ):
        """
        Camino feliz: secret correcto, JSON válido, Redis disponible.
        Verifica el contrato de llamada a Redis sin depender de infraestructura.
        """
        mock_redis = AsyncMock()
        mock_pool.return_value = mock_redis

        request = make_request(factory)
        response = await webhook(request)

        assert response.status_code == 200
        mock_redis.enqueue_job.assert_called_once_with(
            "process_telegram_message", VALID_PAYLOAD
        )

    async def test_wrong_http_method_returns_405(self, client):
        request = make_request(factory, method="get")
        response = await webhook(request)
        assert response.status_code == 405

    async def test_missing_secret_token_returns_403(self, client):
        request = make_request(factory, secret=False)
        response = await webhook(request)
        assert response.status_code == 403

    async def test_wrong_secret_token_returns_403(self, client):
        request = make_request(factory, secret="token-equivocado")
        response = await webhook(request)
        assert response.status_code == 403

    async def test_malformed_json_returns_400(self, client):
        request = factory.post(
            WEBHOOK_URL,
            data="esto no es json {{{",
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=settings.TELEGRAM_WEBHOOK_TOKEN
        )
        response = await webhook(request)
        assert response.status_code == 400

    @patch("apps.bot.views.get_redis")
    async def test_redis_failure_still_returns_200(
        self, mock_get_redis, factory
    ):
        """
        Cuando Redis falla, el webhook devuelve 200 igual.
        Decisión de diseño: Telegram no debe reintentar.
        """
        mock_redis = AsyncMock()
        mock_redis.enqueue_job.side_effect = Exception("Redis connection refused")
        mock_get_redis.return_value = mock_redis

        request = make_request(factory)
        response = await webhook(request)

        assert response.status_code == 200

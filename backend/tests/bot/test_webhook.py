import json
import pytest
from unittest.mock import AsyncMock, patch
from django.test import RequestFactory
from django.conf import settings

from apps.bot.views import webhook

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
PAYLOAD_WITHOUT_UPDATE_ID = {
    "message": {
        "message_id": 1,
        "from": {"id": 111, "first_name": "Ivan"},
        "text": "Pizza 2000"
        # sin update_id
    }
}


@pytest.fixture
def request_factory():
    return RequestFactory()


def make_request(rf, method="post", data=None, secret=None):
    headers = {}
    if secret is not False:
        headers["HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"] = (
            secret or settings.TELEGRAM_WEBHOOK_TOKEN
        )

    body = json.dumps(data or VALID_PAYLOAD)

    if method == "post":
        return rf.post(
            WEBHOOK_URL,
            data=body,
            content_type="application/json",
            **headers
        )
    return rf.get(WEBHOOK_URL, **headers)


class TestWebhook:

    @patch("apps.bot.views.get_redis")
    async def test_valid_request_enqueues_job_and_returns_200(
        self, mock_pool, request_factory
    ):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_pool.return_value = mock_redis

        request = make_request(request_factory)
        response = await webhook(request)

        assert response.status_code == 200
        mock_redis.enqueue_job.assert_called_once_with(
            "process_telegram_message", VALID_PAYLOAD
        )
    
    async def test_payload_without_update_id_is_rejected(
        self, request_factory
    ):
        """
        Payloaads sin update_id son rechazados con 400.
        Telegram siempre incluye update_id - su ausencia indica
        un request malformado o de origen no esperado.    
        """
        request = make_request(request_factory, data=PAYLOAD_WITHOUT_UPDATE_ID)
        response = await webhook(request)

        assert response.status_code == 400

    @patch("apps.bot.views.get_redis")
    async def test_duplicate_update_is_discarded(
        self, mock_pool, request_factory
    ):
        """
        El segundo request con el mismo update_id no debe encolarse.
        Redis ya tiene la clave del primer procesamiento.
        """
        mock_redis = AsyncMock()
        mock_pool.return_value = mock_redis

        # Simulamos que Redis ya tiene la clave — el update fue procesado antes
        mock_redis.get.return_value = b"1"

        request = make_request(request_factory)
        response = await webhook(request)

        assert response.status_code == 200
        mock_redis.enqueue_job.assert_not_called()

    async def test_wrong_http_method_returns_405(self, request_factory):
        request = make_request(request_factory, method="get")
        response = await webhook(request)
        assert response.status_code == 405

    async def test_missing_secret_token_returns_403(self, request_factory):
        request = make_request(request_factory, secret=False)
        response = await webhook(request)
        assert response.status_code == 403

    async def test_wrong_secret_token_returns_403(self, request_factory):
        request = make_request(request_factory, secret="token-equivocado")
        response = await webhook(request)
        assert response.status_code == 403

    async def test_malformed_json_returns_400(self, request_factory):
        request = request_factory.post(
            WEBHOOK_URL,
            data="esto no es json {{{",
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=settings.TELEGRAM_WEBHOOK_TOKEN
        )
        response = await webhook(request)
        assert response.status_code == 400

    @patch("apps.bot.views.get_redis")
    async def test_redis_failure_still_returns_200(
        self, mock_get_redis, request_factory
    ):
        """
        Cuando Redis falla, el webhook devuelve 200 igual.
        Decisión de diseño: Telegram no debe reintentar.
        """
        mock_redis = AsyncMock()
        mock_redis.enqueue_job.side_effect = Exception("Redis connection refused")
        mock_get_redis.return_value = mock_redis

        request = make_request(request_factory)
        response = await webhook(request)

        assert response.status_code == 200
    

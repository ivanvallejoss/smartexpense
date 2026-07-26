import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
        "text": "Pizza 2000",
    },
}

PAYLOAD_WITHOUT_UPDATE_ID = {
    "message": {
        "message_id": 1,
        "from": {"id": 111, "first_name": "Ivan"},
        "text": "Pizza 2000",
    }
}

# Update que el sistema no atiende: antes lo descartaba PTB por falta de handler
PAYLOAD_NO_PROCESABLE = {
    "update_id": 123456790,
    "channel_post": {"message_id": 5, "text": "anuncio"},
}


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def redis():
    """
    Los dos pools que usa el webhook: 'cache' para la clave de idempotencia
    y 'jobs' para la cola.
    """
    cache = AsyncMock()
    cache.set.return_value = True          # primera vez por defecto
    jobs = AsyncMock()
    jobs.enqueue_job.return_value = MagicMock()

    async def _get_redis(purpose="jobs"):
        return cache if purpose == "cache" else jobs

    with patch("apps.bot.views.get_redis", new=_get_redis):
        yield {"cache": cache, "jobs": jobs}


def make_request(rf, method="post", data=None, secret=None):
    headers = {}
    if secret is not False:
        headers["HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"] = (
            secret or settings.TELEGRAM_WEBHOOK_TOKEN
        )

    body = json.dumps(data or VALID_PAYLOAD)

    if method == "post":
        return rf.post(WEBHOOK_URL, data=body, content_type="application/json", **headers)
    return rf.get(WEBHOOK_URL, **headers)


class TestEncolado:

    async def test_encola_el_evento_canonico(self, redis, request_factory):
        response = await webhook(make_request(request_factory))

        assert response.status_code == 200
        redis["jobs"].enqueue_job.assert_called_once()

        args, kwargs = redis["jobs"].enqueue_job.call_args
        assert args[0] == "process_message"

        event = args[1]
        assert event["channel"] == "telegram"
        assert event["external_user_id"] == "111"
        assert event["text"] == "Pizza 2000"
        assert event["type"] == "message"

    async def test_message_id_es_el_update_id(self, redis, request_factory):
        """D2: message.message_id es único por chat, update_id es global."""
        await webhook(make_request(request_factory))

        event = redis["jobs"].enqueue_job.call_args[0][1]
        assert event["message_id"] == "123456789"

    async def test_job_id_sigue_el_contrato(self, redis, request_factory):
        await webhook(make_request(request_factory))

        kwargs = redis["jobs"].enqueue_job.call_args[1]
        assert kwargs["_job_id"] == "telegram:123456789"

    async def test_el_worker_no_recibe_payload_crudo(self, redis, request_factory):
        """El raw viaja adentro del evento, no como argumento suelto."""
        await webhook(make_request(request_factory))

        event = redis["jobs"].enqueue_job.call_args[0][1]
        assert event["raw"] == VALID_PAYLOAD
        assert redis["jobs"].enqueue_job.call_args[0][1] is not VALID_PAYLOAD


class TestIdempotencia:

    async def test_marca_la_clave_antes_de_encolar(self, redis, request_factory):
        """
        Orden intencional (at-most-once): si falla entre marcar y encolar,
        el mensaje se pierde. Preferible a un gasto duplicado.
        """
        orden = []
        redis["cache"].set.side_effect = lambda *a, **k: orden.append("set") or True
        redis["jobs"].enqueue_job.side_effect = lambda *a, **k: orden.append("enqueue")

        await webhook(make_request(request_factory))

        assert orden == ["set", "enqueue"]

    async def test_usa_set_nx_atomico(self, redis, request_factory):
        """El GET+SET anterior tenía carrera entre entregas simultáneas."""
        await webhook(make_request(request_factory))

        kwargs = redis["cache"].set.call_args[1]
        assert kwargs["nx"] is True
        assert kwargs["ex"] == 60 * 60 * 24

    async def test_clave_namespaced_por_canal(self, redis, request_factory):
        await webhook(make_request(request_factory))

        clave = redis["cache"].set.call_args[0][0]
        assert clave == "idempotency:telegram:123456789"

    async def test_duplicado_no_se_encola(self, redis, request_factory):
        """SET NX devuelve None cuando la clave ya existía."""
        redis["cache"].set.return_value = None

        response = await webhook(make_request(request_factory))

        assert response.status_code == 200
        redis["jobs"].enqueue_job.assert_not_called()

    async def test_duplicado_detectado_por_arq_no_rompe(self, redis, request_factory):
        """Segunda capa: enqueue_job retorna None si el _job_id ya existe."""
        redis["jobs"].enqueue_job.return_value = None

        response = await webhook(make_request(request_factory))

        assert response.status_code == 200


class TestUpdatesDescartados:

    async def test_update_no_procesable_no_se_encola(self, redis, request_factory):
        """
        channel_post, fotos, stickers: antes se encolaban y los descartaba
        PTB en el worker. Ahora se filtran en el webhook.
        """
        response = await webhook(
            make_request(request_factory, data=PAYLOAD_NO_PROCESABLE)
        )

        assert response.status_code == 200
        redis["jobs"].enqueue_job.assert_not_called()
        redis["cache"].set.assert_not_called()

    async def test_payload_without_update_id_is_rejected(self, request_factory):
        """
        Telegram siempre incluye update_id — su ausencia indica un request
        malformado o de origen no esperado. Se rechaza antes de tocar Redis.
        """
        response = await webhook(
            make_request(request_factory, data=PAYLOAD_WITHOUT_UPDATE_ID)
        )
        assert response.status_code == 400


class TestSeguridadYTransporte:

    async def test_wrong_http_method_returns_405(self, request_factory):
        response = await webhook(make_request(request_factory, method="get"))
        assert response.status_code == 405

    async def test_missing_secret_token_returns_403(self, request_factory):
        response = await webhook(make_request(request_factory, secret=False))
        assert response.status_code == 403

    async def test_wrong_secret_token_returns_403(self, request_factory):
        response = await webhook(make_request(request_factory, secret="token-equivocado"))
        assert response.status_code == 403

    async def test_malformed_json_returns_400(self, request_factory):
        request = request_factory.post(
            WEBHOOK_URL,
            data="esto no es json {{{",
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=settings.TELEGRAM_WEBHOOK_TOKEN,
        )
        response = await webhook(request)
        assert response.status_code == 400

    async def test_redis_failure_still_returns_200(self, redis, request_factory):
        """
        Cuando Redis falla, el webhook devuelve 200 igual.
        Decisión de diseño: Telegram no debe reintentar.
        """
        redis["jobs"].enqueue_job.side_effect = Exception("Redis connection refused")

        response = await webhook(make_request(request_factory))

        assert response.status_code == 200
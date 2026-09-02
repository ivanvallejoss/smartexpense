"""
Manejo de estado de conversación usando Redis directamente.
Alternativa liviana al ConversationHandler de PTB para flujos simples.

Las claves se namespacean por canal: dos usuarios con el mismo id nativo
en canales distintos no comparten estado.
"""
import logging

from services.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)

STATE_TTL = 300  # 5 minutos — si el usuario no responde, el estado expira

_PREFIX = "cat_state"


def _key(channel: str, external_user_id: str) -> str:
    return f"{_PREFIX}:{channel}:{external_user_id}"


def _legacy_key(external_user_id: str) -> str:
    """
    Formato previo al refactor multi-canal, sin namespace.

    Se lee durante un release para no cortar los flujos en vuelo al
    desplegar. No requiere migración de datos: el TTL de 5 minutos hace
    que el formato viejo se extinga solo.
    """
    return f"{_PREFIX}:{external_user_id}"


async def set_pending_category_state(channel: str, external_user_id: str, expense_id: int) -> None:
    """
    Marca que el usuario está en medio de crear una categoría nueva
    para un expense específico.
    """
    redis = await get_redis("state")
    await redis.set(_key(channel, external_user_id), expense_id, ex=STATE_TTL)
    logger.info(
        "Category state set",
        extra={
            "channel": channel,
            "external_user_id": external_user_id,
            "expense_id": expense_id,
        },
    )


async def get_pending_category_state(channel: str, external_user_id: str):
    """
    Retorna el expense_id pendiente o None si no hay estado activo.

    MGET en vez de dos GET: leer el formato viejo no agrega round-trip.
    Importa porque este es el camino caliente — se ejecuta en cada
    mensaje de texto, y casi siempre devuelve None.
    """
    redis = await get_redis("state")

    actual, legacy = await redis.mget(
        _key(channel, external_user_id),
        _legacy_key(external_user_id),
    )

    value = actual if actual is not None else legacy
    return int(value) if value else None


async def clear_pending_category_state(channel: str, external_user_id: str) -> None:
    """
    Limpia el estado después de que el flujo se completa o cancela.

    Borra ambos formatos: si quedara el viejo, la próxima lectura lo
    resucitaría por el fallback.
    """
    redis = await get_redis("state")
    await redis.delete(
        _key(channel, external_user_id),
        _legacy_key(external_user_id),
    )

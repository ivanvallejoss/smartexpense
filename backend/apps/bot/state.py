"""
Manejo de estado de conversación usando Redis directamente.
Alternativa liviana al ConversationHandler de PTB para flujos simples.
"""
import logging

from django.conf import settings

from services.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)

STATE_TTL = 300  # 5 minutos — si el usuario no responde, el estado expira


async def set_pending_category_state(telegram_user_id: int, expense_id: int) -> None:
    """
    Marca que el usuario está en medio de crear una categoría nueva
    para un expense específico.
    """
    redis = await get_redis("state")
    key = f"cat_state:{telegram_user_id}"
    await redis.set(key, expense_id, ex=STATE_TTL)
    logger.info(f"Category state set for user {telegram_user_id}, expense {expense_id}")


async def get_pending_category_state(telegram_user_id: int):
    """
    Retorna el expense_id pendiente o None si no hay estado activo.
    """
    redis = await get_redis("state")
    key = f"cat_state:{telegram_user_id}"
    value = await redis.get(key)
    return int(value) if value else None


async def clear_pending_category_state(telegram_user_id: int) -> None:
    """
    Limpia el estado después de que el flujo se completa o cancela.
    """
    redis = await get_redis("state")
    key = f"cat_state:{telegram_user_id}"
    await redis.delete(key)
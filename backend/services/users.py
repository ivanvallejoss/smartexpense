from apps.core.models import User
import logging

logger = logging.getLogger(__name__)


async def get_user_with_telegram_id(telegram_id: int):
    try:
        user = User.objects.aget(telegram_id=telegram_id)
        return user
    except User.DoesNotExist:
        return None

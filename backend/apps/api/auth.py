import logging
import jwt

from ninja.security import HttpBearer
from django.conf import settings
from services.users import get_user_by_telegram_id

logger = logging.getLogger(__name__)

class GlobalAuth(HttpBearer):
    async def authenticate(self, request, token):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

            # Recibimos string y devolvemos convertirlo a entero
            telegram_id = int(payload.get("sub"))

            user = await get_user_by_telegram_id(telegram_id=telegram_id)

            # logger para tener informacion durante el proceso
            logger.info(
                "Authentication process", extra={
                    "user_id": user,
                    "expire_time": payload.get("exp"),
                    "telegram": telegram_id
                },
            )

            # Si no hay usuario obtenemos Error 401 de Ninja
            return user

        except jwt.ExpiredSignatureError:
            logger.error(
                "ExpiredSignatureError: unAuthorized user", 
                exc_info=True, 
            )
            return None

        except jwt.InvalidTokenError:
            logger.error(
                "InvalidTokenError: unAuthorized user",
                exc_info=True,
            )
            return None

        except Exception as e:
            logger.error(
                "An unregistered error ocurred",
                extra={
                    "error_details": str(e),
                },
                exc_info=True
            )
            return None
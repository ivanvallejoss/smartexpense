import logging
import jwt

from ninja.security import HttpBearer
from django.conf import settings
from services.users import get_user_by_telegram_id

logger = logging.getLogger(__name__)

class GlobalAuth(HttpBearer):
    async def authenticate(self, request, token):
        try:
            # 1. Decodificamos el token
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            telegram_id = payload.get("sub")

            # 2. Buscamos al usuario de forma limpia
            user = await get_user_by_telegram_id(telegram_id=telegram_id)


            if not user:
                logger.warning(f"Usuario no encontrado para telegram_id: {telegram_id}")
                return None

            logger.info(
                "Authentication process", extra={
                    "user_id": user.id,
                    "expire_time": payload.get("exp"),
                    "telegram": telegram_id
                },
            )




            # 3. Retornamos el usuario (Si es None, Ninja lanza error 401)
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
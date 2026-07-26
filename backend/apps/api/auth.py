import logging
import jwt

from ninja.security import HttpBearer
from django.conf import settings
from apps.core.models import User

logger = logging.getLogger(__name__)

class GlobalAuth(HttpBearer):
    async def authenticate(self, request, token):
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])

            # Rechaza tokens del esquema viejo (sub=telegram_id), que de otro modo
            # se leerian como User.id
            if payload.get("typ") != "magic_link_v2":
                logger.warning("Token con esquema no soportado")
                return None

            # Recibimos en STRING (por requerimientos de PyJWT) y lo convertimos a entero.
            user_id = int(payload.get("sub"))
            user = await User.objects.filter(id=user_id).afirst()

            # logger para tener informacion durante el proceso
            logger.info(
                "Authentication process", extra={
                    "user_id": user_id,
                    "expire_time": payload.get("exp"),
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
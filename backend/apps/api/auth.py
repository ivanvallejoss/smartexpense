from ninja.security import HttpBearer
import jwt
from django.conf import settings
from services.users import get_user_by_telegram_id

class GlobalAuth(HttpBearer):
    async def authenticate(self, request, token):
        try:
            # 1. Decodificamos el token
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            telegram_id = payload.get("sub")

            # 2. Buscamos al usuario de forma limpia
            user = await get_user_by_telegram_id(telegram_id=telegram_id)

            # 3. Retornamos el usuario (Si es None, Ninja lanza error 401)
            return user

        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
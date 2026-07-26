import jwt
from datetime import datetime, timedelta, timezone
from django.conf import settings

def generate_magic_link_token(user_id:int) -> str:
    """
    Genera un token JWT firmado con la JWT_SECRET_KEY de Django.
    Contiene el ID interno del usuario y expira en 15 minutos por seguridad.

    El 'sub' es User.id, no telegram_id: el acceso al dashboard es independiente del canal por el que el usuario llego. 
    """
    payload = {
        # DEBEMOS CONVERTIRLO A string PARA CUMPLIR CON LAS NUEVAS NORMAS DE PyJWT
        # sino obtendremos error "jwt.InvalidSubjectError: Subject must be a string"
        'sub': str(user.id),
        'typ': 'magic_link_v2',
        'iat': datetime.now(timezone.utc), # 'iat' (Issued At)
        'exp': datetime.now(timezone.utc) + timedelta(minutes=15)
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm='HS256')

    return token
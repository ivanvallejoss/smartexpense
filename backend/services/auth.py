import jwt
from datetime import datetime, timedelta, timezone
from django.conf import settings

def generate_magic_link_token(telegram_id:int) -> str:
    """
    Genera un token JWT firmado con la SECRET_KEY de Django.
    Contiene el ID del usuario y expira en 10 minutos por seguridad. 
    """
    payload = {
        # DEBEMOS CONVERTIRLO A string PARA CUMPLIR CON LAS NUEVAS NORMAS DE PyJWT
        # sino obtendremos error jwt.InvalidSubjectError: Subject must be a string
        'sub': str(telegram_id),
        'iat': datetime.now(timezone.utc), # 'iat' (Issued At)
        'exp': datetime.now(timezone.utc) + timedelta(minutes=10)
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

    return token
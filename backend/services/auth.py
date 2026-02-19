import jwt
from datetime import datetime, timedelta, timezone
from django.conf import settings

def generate_magic_link_token(telegram_id:int) -> str:
    """
    Genera un token JWT firmado con la SECRET_KEY de Django.
    Contiene el ID del usuario y expira en 10 minutos por seguridad.
    """
    # El Payload es el "cuerpo" del token. Lo que viaja adentro.
    payload = {
        'sub': telegram_id, # 'sub' (Subject): De quien es este token
        'iat': datetime.now(timezone.utc), # 'iat' (Issued At): Cuando se emitio
        'exp': datetime.now(timezone.utc) + timedelta(minutes=10) # 'exp' (Expiration Time)
    }

    # Firmamos el token usando el algoritmo HS256 y tu clave secreta
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

    return token
"""
Grants de un solo uso sobre Redis.

Reemplaza al JWT del magic link. Un JWT resuelve el problema de verificar un
token *sin estado compartido*; acá el estado compartido es obligatorio, porque
la atomicidad del GETDEL es lo único que garantiza el uso único. Teniendo que ir
a Redis igual, firmar es criptografía que se paga y no se usa: la existencia de
la clave ya es la prueba de validez, y su ausencia la prueba de que venció o se
usó.

Ver docs/decision_records/vinculacion_canales.md, secciones 5 y 6.
"""
import json
import logging
import secrets
import time

from services.constants import (
    CHANNEL_LINK_DIGITS,
    GRANT_TTL,
    PURPOSE_CHANNEL_LINK,
    PURPOSE_WEB_ACCESS,
)
from services.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)

_PREFIX = "grant"

# Reintentos ante colisión de código. Cinco es holgado para 10^6 con los grants
# concurrentes de esta escala: agotarlos no es mala suerte estadística, es señal
# de que algo anda mal. Por eso levanta en vez de degradar en silencio.
_MAX_INTENTOS = 5


class GrantCollision(RuntimeError):
    """
    Se agotaron los reintentos de encontrar un token libre.

    No es un error esperable del flujo: con el espacio de claves vivo acotado
    por el TTL, cinco colisiones seguidas significan que el espacio se llenó o
    que el generador dejó de ser aleatorio. Las dos ameritan enterarse.
    """


# La entropía se declara por propósito y no se hereda: un propósito nuevo que
# olvide su entrada acá falla al emitir en vez de recibir en silencio la del
# vecino, que es exactamente la contaminación que 5.2 del ADR evita.
_TOKEN_FACTORIES = {
    PURPOSE_WEB_ACCESS: lambda: secrets.token_urlsafe(32),
    # secrets y no random: random es un Mersenne Twister predecible a partir de
    # unas pocas salidas observadas, y esto es una credencial.
    PURPOSE_CHANNEL_LINK: (
        lambda: f"{secrets.randbelow(10 ** CHANNEL_LINK_DIGITS):0{CHANNEL_LINK_DIGITS}d}"
    ),
}


def _key(purpose: str, token: str) -> str:
    """
    El propósito va en la clave, no en el valor.

    Es lo que hace que un canje con el propósito equivocado sea un miss que no
    consume nada: el GETDEL ni siquiera nombra la clave del otro propósito. Si
    el propósito viviera en el valor habría que leer-y-borrar para recién
    después rechazarlo, y alguien tanteando códigos en el endpoint web quemaría
    grants de vinculación ajenos y legítimos.
    """
    return f"{_PREFIX}:{purpose}:{token}"


def _generate_token(purpose: str) -> str:
    """Token nuevo con la entropía que le corresponde al propósito."""
    try:
        return _TOKEN_FACTORIES[purpose]()
    except KeyError:
        raise ValueError(f"Propósito sin entropía declarada: {purpose!r}") from None


def _ttl_for(purpose: str) -> int:
    try:
        return GRANT_TTL[purpose]
    except KeyError:
        raise ValueError(f"Propósito sin TTL declarado: {purpose!r}") from None


async def issue_grant(
    user_id: int,
    purpose: str,
    issued_by_channel: str,
    issued_by_external_id: str,
) -> str:
    """
    Emite un grant y devuelve el token en claro. Es la única vez que existe.

    Se emite donde la identidad ya resuelve a un User y se consume donde todavía
    no: quien canjea es quien tiene que probar algo, no quien ya lo probó. Los
    campos issued_by_* quedan en el payload para auditoría, no para autorizar —
    el grant es abierto en canal a propósito, así que quién lo canjea no se
    restringe por dónde se emitió.
    """
    ttl = _ttl_for(purpose)
    redis = await get_redis("auth")

    value = json.dumps(
        {
            "user_id": user_id,
            "purpose": purpose,
            "issued_by_channel": issued_by_channel,
            "issued_by_external_id": str(issued_by_external_id),
            "iat": int(time.time()),
        }
    )

    for intento in range(1, _MAX_INTENTOS + 1):
        token = _generate_token(purpose)

        # NX y no SET a secas: con seis dígitos, dos emisiones concurrentes
        # pueden sacar el mismo código, y un SET pisaría al primero en silencio.
        # Esa persona perdería su código sin que nadie se entere.
        if await redis.set(_key(purpose, token), value, ex=ttl, nx=True):
            return token

        logger.warning(
            "Colisión de token al emitir grant, reintentando",
            extra={"purpose": purpose, "intento": intento, "user_id": user_id},
        )

    raise GrantCollision(f"No se pudo emitir un grant de {purpose!r} en {_MAX_INTENTOS} intentos")


async def consume_grant(token: str, expected_purpose: str) -> dict | None:
    """
    Canjea un grant. Devuelve el payload, o None.

    None cubre tres casos —no existe, venció, ya se usó— y no los distingue a
    propósito: quien llama no puede hacer nada distinto con cada uno, y
    diferenciarlos le confirmaría a quien tantea que un código existió.

    Un propósito distinto al de emisión cae en el mismo None sin tocar el grant
    real, porque la clave que se busca es otra (ver _key).

    El uso único sale de la atomicidad del GETDEL, no de una comprobación
    previa: leer y borrar en dos pasos deja pasar dos canjes concurrentes.
    """
    redis = await get_redis("auth")

    raw = await redis.getdel(_key(expected_purpose, token))
    if raw is None:
        return None

    return json.loads(raw)

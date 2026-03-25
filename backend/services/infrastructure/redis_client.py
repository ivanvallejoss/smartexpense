"""
Infraestructura central de Redis.

Fuente de verdad única para todas las conexiones Redis del sistema.
Cada `purpose` mapea a una database distinta para aislamiento operacional.

Databases:
    0 - jobs:  Cola de ARQ (mensajes de Telegram entrantes)
    1 - state: Estado de conversación del bot (cat_state:{user_id})
    2 - cache: Disponible para rate limiting y cache futuro
"""
import logging
from arq import create_pool
from arq.connections import RedisSettings
from django.conf import settings

logger = logging.getLogger(__name__)

_pools = {}

_DATABASES = {
    "jobs":  0,
    "state": 1,
    "cache": 2,
}


def _get_url_for_purpose(purpose: str) -> str:
    """
    Construye la URL de Redis para el purpose dado.
    Reemplaza el número de database al final de la URL base.
    """
    if purpose not in _DATABASES:
        raise ValueError(
            f"Purpose '{purpose}' no reconocido. "
            f"Opciones válidas: {list(_DATABASES.keys())}"
        )

    base_url = settings.REDIS_URL.rsplit("/", 1)[0]
    db = _DATABASES[purpose]
    return f"{base_url}/{db}"


async def get_redis(purpose: str = "jobs"):
    """
    Retorna el pool de Redis para el purpose solicitado.
    Crea el pool en el primer acceso y lo reutiliza en llamadas posteriores.
    """
    if purpose not in _pools:
        url = _get_url_for_purpose(purpose)
        logger.info(f"Initializing Redis pool for purpose='{purpose}' db={_DATABASES[purpose]}")
        _pools[purpose] = await create_pool(RedisSettings.from_dsn(url))

    return _pools[purpose]


async def close_all() -> None:
    """
    Cierra todos los pools abiertos limpiamente.
    Llamar desde el shutdown hook del worker.
    """
    for purpose, pool in _pools.items():
        await pool.close()
        logger.info(f"Redis pool closed for purpose='{purpose}'")
    _pools.clear()
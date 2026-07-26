"""
Resolución de usuarios por identidad de canal.

Reemplaza a services/users.py:get_or_create_user_by_telegram, que recibía
un objeto User de PTB. Acá la entrada es un dict plano — sin dependencia
de ningún SDK de mensajería.
"""
import logging

from asgiref.sync import sync_to_async
from django.db import transaction

from apps.core.models import ChannelIdentity, User

logger = logging.getLogger(__name__)


async def get_user_by_channel(channel: str, external_id: str):
    """
    Retorna el User asociado a (channel, external_id), o None.
    """
    identity = await (
        ChannelIdentity.objects
        .select_related("user")
        .filter(channel=channel, external_id=str(external_id))
        .afirst()
    )
    return identity.user if identity else None


@sync_to_async
def _create_user_with_identity(channel: str, external_id: str, profile: dict):
    """
    Crea User + ChannelIdentity en una transacción.

    Síncrono y envuelto en sync_to_async: Django no soporta transaction.atomic
    en contexto async. Mismo patrón que create_category_for_user.
    """
    with transaction.atomic():
        identity = (
            ChannelIdentity.objects
            .select_for_update()
            .select_related("user")
            .filter(channel=channel, external_id=external_id)
            .first()
        )
        if identity:
            return identity.user, False

        username = profile.get("username") or f"user_{external_id}"
        user = User.objects.create(
            username=username,
            first_name=profile.get("first_name") or "",
            last_name=profile.get("last_name") or "",
            # Escritura dual: el JWT del magic link todavía depende de esto.
            telegram_id=int(external_id) if channel == ChannelIdentity.CHANNEL_TELEGRAM else None,
            telegram_username=profile.get("username") or None,
        )
        ChannelIdentity.objects.create(
            user=user,
            channel=channel,
            external_id=external_id,
            external_username=profile.get("username") or "",
            display_name=f"{profile.get('first_name') or ''} {profile.get('last_name') or ''}".strip(),
        )
        return user, True


@sync_to_async
def _sync_profile(user, identity, profile: dict) -> None:
    """
    Actualiza nombre/username si el canal reporta cambios.
    Replica el comportamiento de get_or_create_user_by_telegram.
    """
    username = profile.get("username")
    first_name = profile.get("first_name") or ""
    last_name = profile.get("last_name") or ""

    user_fields = []
    if username and user.username != username:
        user.username = username
        user_fields.append("username")
    if user.first_name != first_name:
        user.first_name = first_name
        user.last_name = last_name
        user_fields += ["first_name", "last_name"]
    if user_fields:
        user.save(update_fields=user_fields)

    identity_fields = []
    if identity.external_username != (username or ""):
        identity.external_username = username or ""
        identity_fields.append("external_username")

    display_name = f"{first_name} {last_name}".strip()
    if identity.display_name != display_name:
        identity.display_name = display_name
        identity_fields.append("display_name")

    if identity_fields:
        identity.save(update_fields=identity_fields + ["updated_at"])


async def get_or_create_user_by_channel(
    channel: str,
    external_id: str,
    profile: dict | None = None,
):
    """
    Resuelve el User de una identidad de canal, creándolo si no existe.

    Args:
        channel: "telegram" | "whatsapp"
        external_id: id nativo del usuario en el canal
        profile: {"username", "first_name", "last_name"} — todos opcionales

    Returns:
        (User, created: bool)
    """
    external_id = str(external_id)
    profile = profile or {}

    identity = await (
        ChannelIdentity.objects
        .select_related("user")
        .filter(channel=channel, external_id=external_id)
        .afirst()
    )

    if identity is not None:
        await _sync_profile(identity.user, identity, profile)
        return identity.user, False

    return await _create_user_with_identity(channel, external_id, profile)
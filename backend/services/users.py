from apps.core.models import User
from django.core.exceptions import ObjectDoesNotExist

async def get_user_by_telegram_id(telegram_id: int):
    """
    Busca un usuario por su ID de Telegram ed forma asincrona.
    Retorna el User si existe, o None si no.
    """
    try:
        return await User.objects.aget(telegram_id=telegram_id)
    except User.DoesNotExist:
        # Retornamos None para evitar romper el sistema en caso de que el usuario no exista
        return None


async def get_or_create_user_by_telegram(telegram_user):
    """
    Obtiene el usuario de la DB o lo crea si no existe.
    Usa el metodo nativo asincrono
    """
    user, created = await User.objects.aget_or_create(
        telegram_id=telegram_user.id,
        defaults={
            "username": telegram_user.username or f"user_{telegram_user.id}",
            "first_name": telegram_user.first_name,
            "last_name": telegram_user.last_name or "",
        },
    )

    if not created:
        updated = False

        if telegram_user.username and user.username != telegram_user.username:
            user.username = telegram_user.username
            updated = True

        if user.first_name != telegram_user.first_name:
            user.first_name = telegram_user.first_name
            user.last_name = telegram_user.last_name
            updated = True

        if updated:
            await user.asave()
    
    return user, created
from apps.core.models import User

async def get_user_by_telegram_id(telegram_id: int):
    """
    Busca un usuario por su ID de Telegram ed forma asincrona.
    Retorna el User si existe, o None si no.
    """
    try:
        return await User.objects.aget(telegram_id=telegram_id)
    except User.DoesNotExist:
        return None
import pytest
from dataclasses import dataclass
from apps.core.models import User
from services.users import get_user_by_telegram_id, get_or_create_user_by_telegram
from tests.factories import UserFactory

# --- Mocking de Telegram ---
@dataclass
class MockTelegramUser:
    id: int
    username: str
    first_name: str
    last_name: str

# El parámetro transaction=True es OBLIGATORIO en Django para tests async con DB
pytestmark = pytest.mark.django_db(transaction=True)

class TestUserServices:

    async def test_get_user_by_telegram_id_exists(self):
        # Arreglar: Creamos el usuario con factory (sync logic wrapper for test)
        user = await User.objects.acreate(telegram_id=999, username="test_999")
        
        # Actuar: Buscamos
        result = await get_user_by_telegram_id(999)
        
        # Afirmar
        assert result is not None
        assert result.telegram_id == 999

    async def test_get_user_by_telegram_id_not_found(self):
        result = await get_user_by_telegram_id(12345)
        assert result is None

    async def test_get_or_create_user_by_telegram_new_user(self):
        tg_user = MockTelegramUser(id=111, username="nuevo", first_name="Juan", last_name="Perez")
        
        user, created = await get_or_create_user_by_telegram(tg_user)
        
        assert created is True
        assert user.telegram_id == 111
        assert user.first_name == "Juan"

    async def test_get_or_create_user_by_telegram_updates_existing(self):
        # Usuario original guardado en BD
        await User.objects.acreate(telegram_id=222, username="viejo", first_name="Old", last_name="Name")
        
        # Telegram manda datos nuevos
        tg_user_updated = MockTelegramUser(id=222, username="nuevo", first_name="New", last_name="Name")
        
        user, created = await get_or_create_user_by_telegram(tg_user_updated)
        
        assert created is False
        assert user.username == "nuevo"
        assert user.first_name == "New"
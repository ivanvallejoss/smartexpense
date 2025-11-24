"""
Tests para las utilidades del bot.
"""
from decimal import Decimal
from unittest.mock import Mock

import pytest

from apps.bot.utils import format_amount, get_or_create_user_from_telegram
from apps.core.models import User


class TestFormatAmount:
    """Tests para format_amount."""

    def test_formats_integer_amount(self):
        """Test formateo de monto entero."""
        assert format_amount(Decimal("1500")) == "$1.500"
        assert format_amount(Decimal("2000")) == "$2.000"

    def test_formats_decimal_amount(self):
        """Test formateo de monto con decimales."""
        assert format_amount(Decimal("1500.50")) == "$1.500,50"
        assert format_amount(Decimal("2000.75")) == "$2.000,75"

    def test_handles_large_amounts(self):
        """Test formateo de montos grandes."""
        assert format_amount(Decimal("1000000")) == "$1.000.000"
        assert format_amount(Decimal("1234567.89")) == "$1.234.567,89"


@pytest.mark.django_db
class TestGetOrCreateUserFromTelegram:
    """Tests para get_or_create_user_from_telegram."""

    def test_creates_new_user(self):
        """Test que crea usuario nuevo."""
        telegram_user = Mock()
        telegram_user.id = 12345
        telegram_user.username = "newuser"
        telegram_user.first_name = "New"
        telegram_user.last_name = "User"

        user, created = get_or_create_user_from_telegram(telegram_user)

        assert created is True
        assert user.telegram_id == 12345
        assert user.username == "newuser"
        assert user.first_name == "New"

    def test_returns_existing_user(self):
        """Test que retorna usuario existente."""
        existing = User.objects.create(telegram_id=12345, username="existing", first_name="Existing")

        telegram_user = Mock()
        telegram_user.id = 12345
        telegram_user.username = "existing"
        telegram_user.first_name = "Existing"
        telegram_user.last_name = ""

        user, created = get_or_create_user_from_telegram(telegram_user)

        assert created is False
        assert user.id == existing.id

    def test_updates_changed_username(self):
        """Test que actualiza username si cambió."""
        User.objects.create(telegram_id=12345, username="oldname", first_name="Test")

        telegram_user = Mock()
        telegram_user.id = 12345
        telegram_user.username = "newname"
        telegram_user.first_name = "Test"
        telegram_user.last_name = ""

        user, created = get_or_create_user_from_telegram(telegram_user)

        assert created is False
        assert user.username == "newname"

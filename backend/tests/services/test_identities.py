import pytest
from django.db import IntegrityError

from apps.core.models import ChannelIdentity, User
from services.identities import (
    get_or_create_user_by_channel,
    get_user_by_channel,
)

pytestmark = pytest.mark.django_db(transaction=True)

TG = ChannelIdentity.CHANNEL_TELEGRAM
WA = ChannelIdentity.CHANNEL_WHATSAPP


class TestUniquenessConstraint:

    def test_same_external_id_in_same_channel_is_rejected(self):
        u1 = User.objects.create(username="a")
        u2 = User.objects.create(username="b")
        ChannelIdentity.objects.create(user=u1, channel=TG, external_id="111")

        with pytest.raises(IntegrityError):
            ChannelIdentity.objects.create(user=u2, channel=TG, external_id="111")

    def test_same_external_id_in_different_channels_is_allowed(self):
        u = User.objects.create(username="a")
        ChannelIdentity.objects.create(user=u, channel=TG, external_id="111")
        ChannelIdentity.objects.create(user=u, channel=WA, external_id="111")

        assert u.channel_identities.count() == 2


class TestGetOrCreate:

    async def test_creates_user_and_identity_when_absent(self):
        user, created = await get_or_create_user_by_channel(
            TG, "999", {"username": "ivan", "first_name": "Ivan", "last_name": "V"}
        )

        assert created is True
        assert user.username == "ivan"
        identity = await ChannelIdentity.objects.aget(channel=TG, external_id="999")
        assert identity.user_id == user.id
        assert identity.display_name == "Ivan V"

    async def test_writes_telegram_id_for_backward_compat(self):
        """
        El magic link JWT usa User.telegram_id como 'sub'.
        Mientras services/auth.py no migre, la escritura dual es obligatoria.
        """
        user, _ = await get_or_create_user_by_channel(TG, "999", {})
        assert user.telegram_id == 999

    async def test_does_not_write_telegram_id_for_other_channels(self):
        user, _ = await get_or_create_user_by_channel(WA, "5491122334455", {})
        assert user.telegram_id is None

    async def test_returns_existing_user_without_duplicating(self):
        first, created_first = await get_or_create_user_by_channel(TG, "999", {})
        second, created_second = await get_or_create_user_by_channel(TG, "999", {})

        assert created_first is True
        assert created_second is False
        assert first.id == second.id
        assert await ChannelIdentity.objects.filter(channel=TG).acount() == 1

    async def test_falls_back_to_generated_username(self):
        user, _ = await get_or_create_user_by_channel(TG, "777", {})
        assert user.username == "user_777"

    async def test_syncs_profile_changes_on_subsequent_calls(self):
        await get_or_create_user_by_channel(
            TG, "999", {"username": "viejo", "first_name": "Viejo"}
        )
        user, _ = await get_or_create_user_by_channel(
            TG, "999", {"username": "nuevo", "first_name": "Nuevo"}
        )

        assert user.username == "nuevo"
        identity = await ChannelIdentity.objects.aget(channel=TG, external_id="999")
        assert identity.external_username == "nuevo"

    async def test_accepts_int_external_id(self):
        """El normalizador puede pasar un int; la resolución debe normalizar a str."""
        await get_or_create_user_by_channel(TG, 999, {})
        assert await get_user_by_channel(TG, "999") is not None


class TestGetUserByChannel:

    async def test_returns_none_when_identity_absent(self):
        assert await get_user_by_channel(TG, "inexistente") is None
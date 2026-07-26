"""
Backfill: crea una ChannelIdentity de Telegram por cada User con telegram_id.

User.telegram_id NO se borra: services/auth.py lo usa como 'sub' del JWT
del magic link. Queda deprecado, escrito en paralelo, y se remueve en una
fase posterior junto con la migración del esquema de auth.
"""
from django.db import migrations

TELEGRAM = "telegram"
BATCH = 500


def backfill(apps, schema_editor):
    User = apps.get_model("core", "User")
    ChannelIdentity = apps.get_model("core", "ChannelIdentity")

    pendientes = []
    qs = User.objects.filter(telegram_id__isnull=False).only(
        "id", "telegram_id", "telegram_username", "first_name", "last_name"
    )

    for user in qs.iterator(chunk_size=BATCH):
        pendientes.append(
            ChannelIdentity(
                user_id=user.id,
                channel=TELEGRAM,
                external_id=str(user.telegram_id),
                external_username=user.telegram_username or "",
                display_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
            )
        )

    ChannelIdentity.objects.bulk_create(
        pendientes, batch_size=BATCH, ignore_conflicts=True
    )


def unbackfill(apps, schema_editor):
    """
    Reversa destructiva: borra TODAS las identidades de Telegram, no solo
    las creadas acá. Es la semántica honesta — si revertís esta migración
    querés el estado anterior, en el que la tabla no existía.
    """
    ChannelIdentity = apps.get_model("core", "ChannelIdentity")
    ChannelIdentity.objects.filter(channel=TELEGRAM).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_channelidentity"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
"""
Core models para SmartExpense.
"""
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom User model con integración de Telegram.
    Extiende AbstractUser de Django para agregar campos específicos del bot.
    """

    telegram_id = models.BigIntegerField(
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="ID único del usuario en Telegram",
    )
    telegram_username = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Username de Telegram (sin @)",
    )
    notifications_enabled = models.BooleanField(default=True, help_text="Si el usuario quiere recibir notificaciones del bot")

    class Meta:
        db_table = "users"
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        indexes = [
            models.Index(fields=["telegram_id"], name="idx_telegram_id"),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_full_name() or 'Sin nombre'})"


class Category(models.Model):
    """
    Categorías de gastos.
    Pueden ser personales (user-specific) o globales (is_default=True).
    """

    name = models.CharField(max_length=100, help_text="Nombre de la categoría")
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="categories",
        null=True,
        blank=True,
        help_text="Usuario dueño de la categoría. NULL = categoría global",
    )
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de palabras clave para auto-categorización (ej: ['uber', 'taxi'])",
    )
    is_default = models.BooleanField(default=False, help_text="Si es una categoría global disponible para todos")
    color = models.CharField(
        max_length=7,
        blank=True,
        default="#6B7280",
        help_text="Color en formato HEX para UI (ej: #FF5733)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "categories"
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique_category_per_user",
                condition=models.Q(user__isnull=False),
            )
        ]
        ordering = ["name"]

    def __str__(self):
        if self.is_default:
            return f"{self.name} (Global)"
        return f"{self.name} - {self.user.username if self.user else 'Sin usuario'}"


class Expense(models.Model):
    """
    Gastos de usuarios.
    Registra cada gasto con su monto, categoría, fecha y mensaje original del bot.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="expenses",
        help_text="Usuario que registró el gasto",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Monto del gasto (debe ser mayor a 0)",
    )
    description = models.TextField(max_length=500, help_text="Descripción del gasto (máx 500 caracteres)")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="expenses",
        null=True,
        blank=True,
        help_text="Categoría del gasto (opcional)",
    )
    date = models.DateTimeField(help_text="Fecha y hora del gasto (no puede ser futura)")
    raw_message = models.TextField(
        blank=True,
        default="",
        help_text="Mensaje original enviado por el usuario (para auditoría)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "expenses"
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "-date"], name="idx_user_date"),
            models.Index(fields=["user", "category"], name="idx_user_category"),
            models.Index(fields=["-date"], name="idx_date_desc"),
        ]

    def __str__(self):
        return f"${self.amount} - {self.description[:50]} ({self.user.username})"

    def clean(self):
        """Validaciones personalizadas."""
        from django.core.exceptions import ValidationError

        if self.date and self.date > timezone.now():
            raise ValidationError({"date": "La fecha del gasto no puede ser futura."})


class DeletedObject(models.Model):
    """
    Papelera de reciclaje - almacena objetos eliminados por 30 días.
    Sistema de soft-delete genérico que funciona con cualquier modelo.
    """

    # Generic Foreign Key para cualquier modelo
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Tipo de objeto eliminado (Expense, Category, etc.)",
    )
    object_id = models.PositiveIntegerField(help_text="ID del objeto original")
    content_object = GenericForeignKey("content_type", "object_id")

    # Snapshot completo del objeto
    object_data = models.JSONField(help_text="Snapshot completo del objeto al momento de eliminarlo")

    # Metadata de eliminación
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="deleted_objects",
        help_text="Usuario que eliminó el objeto",
    )
    deleted_at = models.DateTimeField(auto_now_add=True, help_text="Cuándo se eliminó el objeto")
    reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Razón de eliminación (opcional)",
    )

    class Meta:
        db_table = "deleted_objects"
        verbose_name = "Objeto Eliminado"
        verbose_name_plural = "Objetos Eliminados"
        ordering = ["-deleted_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"], name="idx_content_object"),
            models.Index(fields=["deleted_at"], name="idx_deleted_at"),
        ]

    def __str__(self):
        return f"{self.content_type.model} #{self.object_id} eliminado por {self.deleted_by}"

    @property
    def days_until_permanent_deletion(self):
        """Calcula cuántos días faltan para la eliminación permanente."""
        from datetime import timedelta

        deletion_date = self.deleted_at + timedelta(days=30)
        days_left = (deletion_date - timezone.now()).days
        return max(0, days_left)

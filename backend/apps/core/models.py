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
    Custom User model con integracion de Telegram.
    Extiende AbstractUser de Django para agregar campos especificos del bot.
    """

    telegram_id = models.BigIntegerField(
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="ID unico del usuario en Telegram",
    )
    telegram_username = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Username de telegram (sin @)",
    )
    notification_enabled = models.BooleanField(
        default=True, help_text="Si el usuario quiere recibir notificaciones del bot."
    )

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
    Categorias de gastos.
    Pueden ser personales (user-specific) o globales (is_default=True).
    """

    name = models.CharField(max_length=100, help_text="Nombre de la categoria")
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="categories",
        null=True,
        blank=True,
        help_text="Usuario de la categoria. NULL = categoria global",
    )
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de palabras clave para auto-categorizacion (ej: ['uber', 'taxi'])",
    )
    is_default = models.BooleanField(
        default=False, help_text="Si es una categoria global disponible para todos"
    )
    color = models.CharField(
        max_length=7, blank=True, default="#6B7280", help_text="Color en formato HEX para UI"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categories"
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        indexes = [
            models.UniqueConstraion(
                fields=["name", "user"],
                name="unique_category_per_user",
                condition=models.Q(user__isnull=False),
            )
        ]
        ordering = ["name"]

    def __str__(self):
        if self.is_default:
            return f"{self.name} (Global)"
        return f"{self.name} - {self.user.username  if self.user else 'Sin Usuario'}"


class Expense(models.Model):
    """
    Gastos del usuario.
    Registra cada gasto con su monto, categoria, fecha y mensaje original del bot.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="expenses",
        help_text="Usuario que registro el gasto",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Monto del gasto debe ser mayor a 0",
    )
    description = models.TextField(
        max_length=500,
        help_text="Descripcion del gasto",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="expenses",
        null=True,
        blank=True,
        help_text="Categoria del gasto",
    )
    date = models.DateTimeField(help_text="Fecha y hora del gasto (no puede ser futura)")
    raw_message = models.TextField(
        blank=True,
        default="",
        help_text="Mnesaje original enviado por el usuario (para auditoria)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "expenses"
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        indexes = [
            models.Index(fields=["user", "-date"], name="idx_user_date"),
            models.Index(fields=["user", "category"], name="idx_user_categroy"),
            models.Index(fields=["-date"], name="idx_date_desc"),
        ]

    def __str__(self):
        return f"{self.amount} - {self.description[:50]} ({self.user.username})"

    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError

        if self.date and self.date > timezone.now():
            raise ValidationError({"date": "La fecha del gasto no puede ser futura."})


class DeletedObject(models.Model):
    """
    Pa[elera de reciclaje - almacena objetos eliminados por 30 dias.
    Sistema de soft-delete generico que funciona con cualquier modelo.
    """

    # Gneeric Foreign Key para cualquier modelo
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Tipo de objeto eliminado (Expense, Category, etc)",
    )
    object_id = models.PositiveIntegerField(help_text="ID del objeto original")
    content_object = GenericForeignKey("content_type", "object_id")
    # Snapshot completo del objeto
    object_data = models.JSONField(
        help_text="Snapshot completo del objeto al momento de eliminarla"
    )
    # Metadata de eliminacion
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="deleted_objects",
        help_text="Usuario que elimino el objeto",
    )
    deleted_at = models.DateTimeField(auto_now_add=True, help_text="Cuando se elimino el objeto")
    reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Razon de eliminacion (opcional)",
    )

    class Meta:
        db_table = "deleted_objects"
        verbose_name = "Objeto Eliminado"
        verbose_name_plural = "Objetos Eliminados"
        indexes = [
            models.Index(fields=["content_type", "object_id"], name="idx_content_object"),
            models.Index(fields=["deleted_at"], name="idx_deleted_at"),
        ]

    def __str__(self):
        return f"{self.content_type.model} #{self.object_id} eliminado por {self.deleted_by}"

    @property
    def days_until_permanent_deletion(self):
        """Calcula cuantos dias faltan para la elimnacion permanente."""
        from datetime import timedelta

        deletion_date = self.deleted_at + timedelta(days=30)
        days_left = (deletion_date - timezone.now()).days
        return max(0, days_left)

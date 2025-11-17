"""
Django admin configuration para core models.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Category, DeletedObject, Expense, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin para User customizado."""

    list_display = ["username", "email", "telegram_id", "telegram_username", "is_staff"]
    list_filter = ["is_staff", "is_superuser", "notifications_enabled"]
    search_fields = ["username", "email", "telegram_username"]

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Telegram Integration",
            {
                "fields": (
                    "telegram_id",
                    "telegram_username",
                    "notifications_enabled",
                )
            },
        ),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin para Category."""

    list_display = ["name", "user", "is_default", "color", "created_at"]
    list_filter = ["is_default", "created_at"]
    search_fields = ["name", "user__username"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """Admin para Expense."""

    list_display = ["description", "amount", "user", "category", "date", "created_at"]
    list_filter = ["category", "date", "created_at"]
    search_fields = ["description", "user__username"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "date"


@admin.register(DeletedObject)
class DeletedObjectAdmin(admin.ModelAdmin):
    """Admin para DeletedObject (papelera)."""

    list_display = [
        "content_type",
        "object_id",
        "deleted_by",
        "deleted_at",
        "days_until_permanent_deletion",
    ]
    list_filter = ["content_type", "deleted_at"]
    search_fields = ["object_id", "deleted_by__username"]
    readonly_fields = ["deleted_at", "days_until_permanent_deletion"]
    date_hierarchy = "deleted_at"

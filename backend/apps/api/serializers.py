"""
Serializers para la API REST de SmartExpense.
"""
from django.utils import timezone

from rest_framework import serializers

from apps.core.models import Category, Expense, User
from apps.ml.categorizer import TextNormalizer


class UserSerializer(serializers.ModelSerializer):
    """Serializer básico para User (para nested representations)."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]
        read_only_fields = ["id"]


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer para Category.
    Maneja creación y validación de categorías por usuario.
    """

    expense_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "keywords",
            "is_default",
            "color",
            "expense_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_default", "expense_count", "created_at", "updated_at"]

    def get_expense_count(self, obj):
        """Retorna cantidad de expenses asociados a esta categoría."""
        return obj.expenses.count()

    def validate_name(self, value):
        """Validar que el nombre no esté vacío."""
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre de la categoría no puede estar vacío.")
        return value.strip()

    def validate_keywords(self, value):
        """Validar que keywords sea una lista."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Keywords debe ser una lista.")

        # Normalizamos cada keyword (a minuscula y sin acentos)
        normalizer = TextNormalizer()
        return [normalizer.normalize(str(kw)) for kw in value if kw]

    def validate_color(self, value):
        """Validar formato de color HEX."""
        if value and not value.startswith("#"):
            raise serializers.ValidationError("El color debe estar en formato HEX (#RRGGBB).")
        if value and len(value) != 7:
            raise serializers.ValidationError("El color debe tener formato #RRGGBB (7 caracteres).")
        return value

    def create(self, validated_data):
        """Asociar automáticamente al usuario actual."""
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class ExpenseSerializer(serializers.ModelSerializer):
    """
    Serializer para Expense.
    Maneja creación, validación y representación de gastos.
    """

    category_details = CategorySerializer(source="category", read_only=True)
    user_details = UserSerializer(source="user", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "user",
            "user_details",
            "amount",
            "description",
            "category",
            "category_details",
            "date",
            "raw_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_details",
            "category_details",
            "created_at",
            "updated_at",
        ]

    def validate_amount(self, value):
        """Validar que el monto sea positivo."""
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a 0.")
        # Validar máximo 2 decimales
        if value.as_tuple().exponent < -2:
            raise serializers.ValidationError("El monto no puede tener más de 2 decimales.")
        return value

    def validate_description(self, value):
        """Validar descripción."""
        if not value or not value.strip():
            raise serializers.ValidationError("La descripción no puede estar vacía.")
        if len(value) > 500:
            raise serializers.ValidationError("La descripción no puede exceder 500 caracteres.")
        return value.strip()

    def validate_date(self, value):
        """Validar que la fecha no sea futura."""
        if value > timezone.now():
            raise serializers.ValidationError("La fecha del gasto no puede ser futura.")
        return value

    def validate_category(self, value):
        """Validar que la categoría pertenezca al usuario."""
        if value is None:
            return value
        user = self.context["request"].user

        # Verificar que la categoría sea del usuario o sea global
        if value.user and value.user != user:
            raise serializers.ValidationError("No puedes usar una categoría que no te pertenece.")

        return value

    def validate(self, attrs):
        """Validaciones a nivel de objeto."""
        # Si no se pasa date, usar now()
        if "date" not in attrs or attrs["date"] is None:
            attrs["date"] = timezone.now()

        return attrs

    def create(self, validated_data):
        """Asociar automáticamente al usuario actual."""
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class ExpenseStatsSerializer(serializers.Serializer):
    """
    Serializer para estadísticas de gastos.
    No está vinculado a un modelo, solo para output.
    """

    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    expense_count = serializers.IntegerField()
    average_per_day = serializers.DecimalField(max_digits=10, decimal_places=2)
    by_category = serializers.ListField(child=serializers.DictField())  # Lista de {category_name, total, count}
    date_range = serializers.DictField()  # {start, end}


class ExpenseCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para crear/actualizar expenses.
    No incluye campos nested para evitar complejidad en writes.
    """

    date = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "amount",
            "description",
            "category",
            "date",
            "raw_message",
        ]
        read_only_fields = ["id"]

    def validate_amount(self, value):
        """Validar que el monto sea positivo."""
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a 0.")
        return value

    def validate_description(self, value):
        """Validar descripción."""
        if not value or not value.strip():
            raise serializers.ValidationError("La descripción no puede estar vacía.")
        if len(value) > 500:
            raise serializers.ValidationError("La descripción no puede exceder 500 caracteres.")
        return value.strip()

    def validate_date(self, value):
        """Validar que la fecha no sea futura."""
        if value and value > timezone.now():
            raise serializers.ValidationError("La fecha del gasto no puede ser futura.")
        return value

    def validate_category(self, value):
        """Validar que la categoría pertenezca al usuario."""
        if value is None:
            return value

        user = self.context["request"].user

        if value.user and value.user != user:
            raise serializers.ValidationError("No puedes usar una categoría que no te pertenece.")

        return value

    def validate(self, attrs):
        """Validaciones a nivel de objeto."""
        # Si no se pasa date, usar now()
        if "date" not in attrs or attrs["date"] is None:
            attrs["date"] = timezone.now()

        return attrs

    def create(self, validated_data):
        """Asociar automáticamente al usuario actual."""
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

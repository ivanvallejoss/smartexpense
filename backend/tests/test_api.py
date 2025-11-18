"""
Tests para la API de SmartExpense.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import Category, Expense

User = get_user_model()


@pytest.fixture
def api_client():
    """Cliente API de DRF."""
    return APIClient()


@pytest.fixture
def user_a(db):
    """Usuario A para tests."""
    return User.objects.create_user(
        username="user_a",
        email="usera@example.com",
        password="testpass123",
    )


@pytest.fixture
def user_b(db):
    """Usuario B para tests."""
    return User.objects.create_user(
        username="user_b",
        email="userb@example.com",
        password="testpass123",
    )


@pytest.fixture
def category_user_a(user_a):
    """Categoría de User A."""
    return Category.objects.create(
        name="Comida",
        user=user_a,
        color="#FF5733",
    )


@pytest.fixture
def category_user_b(user_b):
    """Categoría de User B."""
    return Category.objects.create(
        name="Transporte",
        user=user_b,
        color="#3366FF",
    )


@pytest.fixture
def global_category(db):
    """Categoría global (sin usuario)."""
    return Category.objects.create(
        name="Global",
        is_default=True,
        color="#999999",
    )


@pytest.fixture
def expense_user_a(user_a, category_user_a):
    """Expense de User A."""
    return Expense.objects.create(
        user=user_a,
        amount=Decimal("100.50"),
        description="Almuerzo",
        category=category_user_a,
        date=timezone.now() - timedelta(days=1),
    )


@pytest.fixture
def expense_user_b(user_b, category_user_b):
    """Expense de User B."""
    return Expense.objects.create(
        user=user_b,
        amount=Decimal("50.00"),
        description="Taxi",
        category=category_user_b,
        date=timezone.now() - timedelta(days=2),
    )


# ============================================
# TESTS DE EXPENSES
# ============================================


@pytest.mark.django_db
class TestExpensePermissions:
    """Tests de permisos y ownership de expenses."""

    def test_user_cannot_see_other_user_expenses(self, api_client, user_a, user_b, expense_user_a, expense_user_b):
        """User A no puede ver expenses de User B."""
        api_client.force_authenticate(user=user_a)

        # Listar expenses (solo debería ver los suyos)
        url = reverse("expense-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == expense_user_a.id

    def test_user_cannot_access_other_user_expense_detail(self, api_client, user_a, expense_user_b):
        """User A no puede acceder al detalle de un expense de User B."""
        api_client.force_authenticate(user=user_a)

        url = reverse("expense-detail", kwargs={"pk": expense_user_b.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_user_cannot_update_other_user_expense(self, api_client, user_a, expense_user_b):
        """User A no puede actualizar un expense de User B."""
        api_client.force_authenticate(user=user_a)

        url = reverse("expense-detail", kwargs={"pk": expense_user_b.id})
        data = {"amount": "999.99"}
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Verificar que no cambió
        expense_user_b.refresh_from_db()
        assert expense_user_b.amount == Decimal("50.00")


@pytest.mark.django_db
class TestExpenseValidations:
    """Tests de validaciones en expenses."""

    def test_negative_amount_fails(self, api_client, user_a, category_user_a):
        """Amount negativo falla validación."""
        api_client.force_authenticate(user=user_a)

        url = reverse("expense-list")
        data = {
            "amount": "-100.00",
            "description": "Test",
            "category": category_user_a.id,
            "date": timezone.now().isoformat(),
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "amount" in response.data

    def test_zero_amount_fails(self, api_client, user_a, category_user_a):
        """Amount cero falla validación."""
        api_client.force_authenticate(user=user_a)

        url = reverse("expense-list")
        data = {
            "amount": "0.00",
            "description": "Test",
            "category": category_user_a.id,
            "date": timezone.now().isoformat(),
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "amount" in response.data

    def test_future_date_fails(self, api_client, user_a, category_user_a):
        """Date futura falla validación."""
        api_client.force_authenticate(user=user_a)

        future_date = timezone.now() + timedelta(days=1)

        url = reverse("expense-list")
        data = {
            "amount": "100.00",
            "description": "Test",
            "category": category_user_a.id,
            "date": future_date.isoformat(),
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "date" in response.data

    def test_empty_description_fails(self, api_client, user_a, category_user_a):
        """Description vacía falla validación."""
        api_client.force_authenticate(user=user_a)

        url = reverse("expense-list")
        data = {
            "amount": "100.00",
            "description": "",
            "category": category_user_a.id,
            "date": timezone.now().isoformat(),
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "description" in response.data

    def test_description_max_length(self, api_client, user_a, category_user_a):
        """Description mayor a 500 caracteres falla."""
        api_client.force_authenticate(user=user_a)

        url = reverse("expense-list")
        data = {
            "amount": "100.00",
            "description": "A" * 501,  # 501 caracteres
            "category": category_user_a.id,
            "date": timezone.now().isoformat(),
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "description" in response.data


@pytest.mark.django_db
class TestExpenseCRUD:
    """Tests de CRUD completo de expenses."""

    def test_create_expense(self, api_client, user_a, category_user_a):
        """Crear expense exitosamen`te."""
        api_client.force_authenticate(user=user_a)

        url = reverse("expense-list")
        data = {
            "amount": "150.75",
            "description": "Cena en restaurante",
            "category": category_user_a.id,
            "date": timezone.now().isoformat(),
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Expense.objects.filter(user=user_a).count() == 1

        expense = Expense.objects.get(user=user_a)
        assert expense.amount == Decimal("150.75")
        assert expense.description == "Cena en restaurante"
        assert expense.user == user_a

    def test_create_expense_without_date_uses_now(self, api_client, user_a, category_user_a):
        """Crear expense sin date usa timezone.now()."""
        api_client.force_authenticate(user=user_a)

        url = reverse("expense-list")
        data = {
            "amount": "50.00",
            "description": "Test",
            "category": category_user_a.id,
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        expense = Expense.objects.get(user=user_a)
        # Verificar que la fecha es aproximadamente now
        assert (timezone.now() - expense.date).total_seconds() < 10

    def test_list_expenses(self, api_client, user_a, expense_user_a):
        """Listar expenses del usuario."""
        api_client.force_authenticate(user=user_a)

        url = reverse("expense-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_retrieve_expense(self, api_client, user_a, expense_user_a):
        """Obtener detalle de un expense."""
        api_client.force_authenticate(user=user_a)

        url = reverse("expense-detail", kwargs={"pk": expense_user_a.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == expense_user_a.id
        assert Decimal(response.data["amount"]) == expense_user_a.amount

    def test_update_expense(self, api_client, user_a, expense_user_a):
        """Actualizar un expense."""
        api_client.force_authenticate(user=user_a)

        url = reverse("expense-detail", kwargs={"pk": expense_user_a.id})
        data = {"amount": "200.00"}
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        expense_user_a.refresh_from_db()
        assert expense_user_a.amount == Decimal("200.00")

    def test_delete_expense_soft_delete(self, api_client, user_a, expense_user_a):
        """Eliminar expense hace soft delete."""
        api_client.force_authenticate(user=user_a)

        expense_id = expense_user_a.id

        url = reverse("expense-detail", kwargs={"pk": expense_id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verificar que se eliminó
        assert not Expense.objects.filter(id=expense_id).exists()

        # Verificar que está en DeletedObject
        from apps.core.models import DeletedObject

        assert DeletedObject.objects.filter(object_id=expense_id).exists()


@pytest.mark.django_db
class TestExpenseFilters:
    """Tests de filtros en expenses."""

    def test_filter_by_date_from(self, api_client, user_a):
        """Filtrar por fecha desde."""
        api_client.force_authenticate(user=user_a)

        # Crear expenses en diferentes fechas
        Expense.objects.create(
            user=user_a,
            amount=Decimal("100"),
            description="Viejo",
            date=timezone.now() - timedelta(days=10),
        )
        Expense.objects.create(
            user=user_a,
            amount=Decimal("200"),
            description="Nuevo",
            date=timezone.now() - timedelta(days=1),
        )

        # Filtrar últimos 5 días
        date_from = (timezone.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        url = f"{reverse('expense-list')}?date_from={date_from}"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["description"] == "Nuevo"

    def test_filter_by_category(self, api_client, user_a, category_user_a):
        """Filtrar por categoría."""
        api_client.force_authenticate(user=user_a)

        category_2 = Category.objects.create(name="Transporte", user=user_a)

        Expense.objects.create(
            user=user_a,
            amount=Decimal("100"),
            description="Comida",
            category=category_user_a,
            date=timezone.now(),
        )
        Expense.objects.create(
            user=user_a,
            amount=Decimal("50"),
            description="Taxi",
            category=category_2,
            date=timezone.now(),
        )

        url = f"{reverse('expense-list')}?category_id={category_user_a.id}"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["description"] == "Comida"


@pytest.mark.django_db
class TestExpenseStats:
    """Tests del endpoint de estadísticas."""

    def test_stats_calculates_correctly(self, api_client, user_a, category_user_a):
        """Stats calcula totales correctamente."""
        api_client.force_authenticate(user=user_a)

        category_2 = Category.objects.create(name="Transporte", user=user_a)

        # Crear expenses
        Expense.objects.create(
            user=user_a,
            amount=Decimal("100.00"),
            description="Comida 1",
            category=category_user_a,
            date=timezone.now(),
        )
        Expense.objects.create(
            user=user_a,
            amount=Decimal("50.00"),
            description="Comida 2",
            category=category_user_a,
            date=timezone.now(),
        )
        Expense.objects.create(
            user=user_a,
            amount=Decimal("30.00"),
            description="Taxi",
            category=category_2,
            date=timezone.now(),
        )

        url = reverse("expense-stats")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert Decimal(response.data["total_amount"]) == Decimal("180.00")
        assert response.data["expense_count"] == 3

        # Verificar by_category
        by_category = response.data["by_category"]
        assert len(by_category) == 2

        # Primera categoría debería ser Comida (mayor total)
        assert by_category[0]["category_name"] == "Comida"
        assert Decimal(by_category[0]["total"]) == Decimal("150.00")
        assert by_category[0]["count"] == 2


# ============================================
# TESTS DE CATEGORIES
# ============================================


@pytest.mark.django_db
class TestCategoryCRUD:
    """Tests de CRUD de categorías."""

    def test_create_category(self, api_client, user_a):
        """Crear categoría exitosamente."""
        api_client.force_authenticate(user=user_a)

        url = reverse("category-list")
        data = {
            "name": "Nueva Categoría",
            "keywords": ["test", "prueba"],
            "color": "#FF5733",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Category.objects.filter(user=user_a, name="Nueva Categoría").exists()

    def test_cannot_delete_category_with_expenses(self, api_client, user_a, category_user_a, expense_user_a):
        """No se puede eliminar categoría con expenses asociados."""
        api_client.force_authenticate(user=user_a)

        url = reverse("category-detail", kwargs={"pk": category_user_a.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "gasto(s) asociado(s)" in response.data["detail"]

        # Verificar que no se eliminó
        assert Category.objects.filter(id=category_user_a.id).exists()

    def test_can_delete_category_without_expenses(self, api_client, user_a):
        """Se puede eliminar categoría sin expenses."""
        api_client.force_authenticate(user=user_a)

        category = Category.objects.create(name="Sin expenses", user=user_a)

        url = reverse("category-detail", kwargs={"pk": category.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Category.objects.filter(id=category.id).exists()

    def test_cannot_delete_global_category(self, api_client, user_a, global_category):
        """No se puede eliminar categoría global."""
        api_client.force_authenticate(user=user_a)

        url = reverse("category-detail", kwargs={"pk": global_category.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Category.objects.filter(id=global_category.id).exists()

    def test_user_sees_own_and_global_categories(self, api_client, user_a, category_user_a, category_user_b, global_category):
        """Usuario ve sus categorías + globales (pero no las de otros users)."""
        api_client.force_authenticate(user=user_a)

        url = reverse("category-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        category_ids = [cat["id"] for cat in response.data["results"]]
        assert category_user_a.id in category_ids
        assert global_category.id in category_ids
        assert category_user_b.id not in category_ids

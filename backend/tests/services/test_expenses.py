import pytest
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from apps.core.models import Expense
from services.expenses import create_expense, update_expense, delete_expense
from tests.factories import UserFactory, CategoryFactory, ExpenseFactory

pytestmark = pytest.mark.django_db(transaction=True)

class TestExpenseServices:

    async def test_create_expense_success(self):
        # Setup con asgiref porque las factories de factory-boy son síncronas por defecto
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)()

        # Act
        expense = await create_expense(
            user=user,
            amount=1500.50,
            description="Hamburguesa",
            category_id=category.id
        )

        # Assert
        assert expense.id is not None
        assert expense.amount == 1500.50
        assert expense.category == category
        assert expense.raw_message == "Hamburguesa" # Por default toma la description

    async def test_update_expense_success(self):
        user = await sync_to_async(UserFactory)()
        category_old = await sync_to_async(CategoryFactory)()
        category_new = await sync_to_async(CategoryFactory)()
        expense = await sync_to_async(ExpenseFactory)(user=user, category=category_old, amount=100)

        updated_expense = await update_expense(
            user=user,
            expense_id=expense.id,
            amount=200,
            description="Editado",
            category_id=category_new.id
        )

        assert updated_expense.amount == 200
        assert updated_expense.description == "Editado"
        assert updated_expense.category.id == category_new.id

    async def test_update_expense_wrong_user_fails(self):
        owner = await sync_to_async(UserFactory)()
        hacker = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)()
        expense = await sync_to_async(ExpenseFactory)(user=owner)

        # Intentamos actualizar con un usuario que no es el dueño
        with pytest.raises(ObjectDoesNotExist, match="no existe o no tienes permisos"):
            await update_expense(
                user=hacker,
                expense_id=expense.id,
                amount=999,
                description="Hacked",
                category_id=category.id
            )

    async def test_delete_expense_success(self):
        user = await sync_to_async(UserFactory)()
        expense = await sync_to_async(ExpenseFactory)(user=user)

        result = await delete_expense(user=user, expense_id=expense.id)

        assert result is True
        # Verificamos que ya no exista en la DB
        count = await Expense.objects.filter(id=expense.id).acount()
        assert count == 0

    async def test_delete_expense_wrong_user_fails(self):
        owner = await sync_to_async(UserFactory)()
        hacker = await sync_to_async(UserFactory)()
        expense = await sync_to_async(ExpenseFactory)(user=owner)

        with pytest.raises(ObjectDoesNotExist, match="no existe o no te pertenece"):
            await delete_expense(user=hacker, expense_id=expense.id)
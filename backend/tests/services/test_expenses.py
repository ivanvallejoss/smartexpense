"""
Tests del service layer de expenses.
Cubre create_expense, update_expense, delete_expense y restore_expense.
"""
import pytest
from decimal import Decimal
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist

from apps.core.models import Expense, DeletedObject, CategorySuggestionFeedback
from services.expenses import create_expense, update_expense, delete_expense, restore_expense
from tests.factories import UserFactory, CategoryFactory, ExpenseFactory

pytestmark = pytest.mark.django_db(transaction=True)


# ============================================
# CREATE EXPENSE
# ============================================

class TestCreateExpense:

    async def test_creates_with_confirmed_status_by_default(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)()

        expense = await create_expense(
            user=user,
            amount=1500,
            description="Pizza",
            category=category,
        )

        assert expense.id is not None
        assert expense.status == Expense.STATUS_CONFIRMED

    async def test_creates_with_pending_status_when_passed(self):
        user = await sync_to_async(UserFactory)()

        expense = await create_expense(
            user=user,
            amount=1500,
            description="Algo desconocido",
            category=None,
            status=Expense.STATUS_PENDING,
        )

        assert expense.status == Expense.STATUS_PENDING
        assert expense.category is None

    async def test_raw_message_defaults_to_description(self):
        user = await sync_to_async(UserFactory)()

        expense = await create_expense(
            user=user,
            amount=500,
            description="Café",
        )

        assert expense.raw_message == "Café"

    async def test_raw_message_uses_passed_value_when_provided(self):
        user = await sync_to_async(UserFactory)()

        expense = await create_expense(
            user=user,
            amount=500,
            description="Café",
            raw_message="cafe 500",
        )

        assert expense.raw_message == "cafe 500"


# ============================================
# UPDATE EXPENSE
# ============================================

class TestUpdateExpense:

    async def test_updates_fields_correctly(self):
        user = await sync_to_async(UserFactory)()
        cat_old = await sync_to_async(CategoryFactory)(name="Comida")
        cat_new = await sync_to_async(CategoryFactory)(name="Transporte")
        expense = await sync_to_async(ExpenseFactory)(
            user=user, category=cat_old, amount=100, description="Original"
        )

        # Traemos el objeto con select_related como lo haría el endpoint
        expense_obj = await Expense.objects.select_related('category').aget(
            id=expense.id, user=user
        )

        updated = await update_expense(
            user=user,
            expense=expense_obj,
            amount=500,
            description="Actualizado",
            category=cat_new,
        )

        assert updated.amount == Decimal("500")
        assert updated.description == "Actualizado"
        assert updated.category.id == cat_new.id

    async def test_records_feedback_when_category_changes(self):
        user = await sync_to_async(UserFactory)()
        cat_old = await sync_to_async(CategoryFactory)(name="Comida")
        cat_new = await sync_to_async(CategoryFactory)(name="Transporte")
        expense = await sync_to_async(ExpenseFactory)(
            user=user, category=cat_old, amount=100, description="Uber"
        )

        expense_obj = await Expense.objects.select_related('category').aget(
            id=expense.id, user=user
        )

        count_before = await CategorySuggestionFeedback.objects.acount()

        await update_expense(
            user=user,
            expense=expense_obj,
            amount=100,
            description="Uber",
            category=cat_new,
        )

        count_after = await CategorySuggestionFeedback.objects.acount()
        assert count_after == count_before + 1

        feedback = await CategorySuggestionFeedback.objects.select_related(
            'suggested_category', 'final_category'
        ).alatest('created_at')
        assert feedback.suggested_category.id == cat_old.id
        assert feedback.final_category.id == cat_new.id
        assert feedback.was_accepted is False

    async def test_does_not_record_feedback_when_category_unchanged(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(name="Comida")
        expense = await sync_to_async(ExpenseFactory)(
            user=user, category=category, amount=100, description="Pizza"
        )

        expense_obj = await Expense.objects.select_related('category').aget(
            id=expense.id, user=user
        )

        count_before = await CategorySuggestionFeedback.objects.acount()

        await update_expense(
            user=user,
            expense=expense_obj,
            amount=200,
            description="Pizza grande",
            category=category,  # misma categoría
        )

        count_after = await CategorySuggestionFeedback.objects.acount()
        assert count_after == count_before


# ============================================
# DELETE EXPENSE
# ============================================

class TestDeleteExpense:

    async def test_removes_expense_from_main_table(self):
        user = await sync_to_async(UserFactory)()
        expense = await sync_to_async(ExpenseFactory)(user=user)

        await delete_expense(user=user, expense_id=expense.id)

        count = await Expense.objects.filter(id=expense.id).acount()
        assert count == 0

    async def test_creates_record_in_deleted_objects(self):
        user = await sync_to_async(UserFactory)()
        expense = await sync_to_async(ExpenseFactory)(
            user=user, description="Gasto a borrar"
        )

        deleted_obj_id = await delete_expense(user=user, expense_id=expense.id)

        deleted_obj = await DeletedObject.objects.aget(id=deleted_obj_id)
        assert deleted_obj.object_data["description"] == "Gasto a borrar"

    async def test_wrong_user_raises_exception(self):
        owner = await sync_to_async(UserFactory)()
        hacker = await sync_to_async(UserFactory)()
        expense = await sync_to_async(ExpenseFactory)(user=owner)

        with pytest.raises(ObjectDoesNotExist):
            await delete_expense(user=hacker, expense_id=expense.id)


# ============================================
# RESTORE EXPENSE
# ============================================

class TestRestoreExpense:

    async def test_restores_expense_with_original_data(self):
        user = await sync_to_async(UserFactory)()
        category = await sync_to_async(CategoryFactory)(name="Comida")
        expense = await sync_to_async(ExpenseFactory)(
            user=user, category=category, amount=1500, description="Pizza"
        )

        deleted_obj_id = await delete_expense(user=user, expense_id=expense.id)
        restored = await restore_expense(user=user, deleted_object_id=deleted_obj_id)

        assert restored.amount == Decimal("1500")
        assert restored.description == "Pizza"
        assert restored.category.name == "Comida"

    async def test_cleans_deleted_object_after_restore(self):
        user = await sync_to_async(UserFactory)()
        expense = await sync_to_async(ExpenseFactory)(user=user)

        deleted_obj_id = await delete_expense(user=user, expense_id=expense.id)
        await restore_expense(user=user, deleted_object_id=deleted_obj_id)

        count = await DeletedObject.objects.filter(id=deleted_obj_id).acount()
        assert count == 0

    async def test_wrong_user_raises_exception(self):
        owner = await sync_to_async(UserFactory)()
        hacker = await sync_to_async(UserFactory)()
        expense = await sync_to_async(ExpenseFactory)(user=owner)

        deleted_obj_id = await delete_expense(user=owner, expense_id=expense.id)

        with pytest.raises(ObjectDoesNotExist):
            await restore_expense(user=hacker, deleted_object_id=deleted_obj_id)
"""
Tests para los callbacks de botones inline del bot.
Cubre delete, restore y todo el flujo de categorización.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from apps.bot.handlers.callbacks import (
    central_callback_handler,
    on_delete_click,
    on_restore_click,
    on_cat_confirm_click,
    on_cat_list_click,
    on_cat_select_click,
    on_cat_new_click,
)
from apps.core.models import Expense, Category, CategorySuggestionFeedback
from tests.factories import UserFactory, CategoryFactory, ExpenseFactory
from asgiref.sync import sync_to_async

pytestmark = pytest.mark.django_db(transaction=True)


# ============================================
# FIXTURES
# ============================================

@pytest.fixture
def mock_update_cb():
    update = MagicMock()
    update.effective_user.id = 123456789
    update.callback_query = AsyncMock()
    return update


@pytest.fixture
async def base_data():
    """Usuario, dos categorías y un expense listos para usar."""
    user = await sync_to_async(UserFactory)(telegram_id=123456789)
    cat_a = await sync_to_async(CategoryFactory)(name="Comida", user=user)
    cat_b = await sync_to_async(CategoryFactory)(name="Transporte", user=user)
    expense = await sync_to_async(ExpenseFactory)(
        user=user, category=cat_a, amount=1500, description="Pizza"
    )
    return {"user": user, "cat_a": cat_a, "cat_b": cat_b, "expense": expense}


# ============================================
# CENTRAL CALLBACK HANDLER
# ============================================

class TestCentralCallbackHandler:

    async def test_invalid_format_shows_error(self, mock_update_cb):
        mock_update_cb.callback_query.data = "boton_roto"

        await central_callback_handler(mock_update_cb, AsyncMock())

        mock_update_cb.callback_query.answer.assert_called_with(
            "❌ Error: Formato de botón inválido", show_alert=True
        )

    async def test_unknown_action_shows_warning(self, mock_update_cb):
        mock_update_cb.callback_query.data = "hack:99"

        await central_callback_handler(mock_update_cb, AsyncMock())

        mock_update_cb.callback_query.answer.assert_called_with("⚠️ Acción desconocida")


# ============================================
# DELETE Y RESTORE
# ============================================

class TestDeleteAndRestore:

    @patch("apps.bot.handlers.callbacks.delete_expense")
    @patch("apps.bot.handlers.callbacks.get_user_by_telegram_id")
    async def test_delete_success_offers_undo(
        self, mock_get_user, mock_delete, mock_update_cb
    ):
        mock_get_user.return_value = MagicMock()
        mock_delete.return_value = 99

        await on_delete_click(mock_update_cb, AsyncMock(), "55")

        mock_update_cb.callback_query.answer.assert_called_with("🗑️ Gasto eliminado")
        call_args = mock_update_cb.callback_query.edit_message_text.call_args
        assert "🗑️ Gasto eliminado de tu historial" in call_args[0][0]
        assert "reply_markup" in call_args[1]

    @patch("apps.bot.handlers.callbacks.delete_expense")
    @patch("apps.bot.handlers.callbacks.get_user_by_telegram_id")
    async def test_delete_not_found_shows_error(
        self, mock_get_user, mock_delete, mock_update_cb
    ):
        mock_get_user.return_value = MagicMock()
        mock_delete.side_effect = ObjectDoesNotExist("No existe")

        await on_delete_click(mock_update_cb, AsyncMock(), "55")

        mock_update_cb.callback_query.answer.assert_called_with(
            "⚠️ Error", show_alert=True
        )

    @patch("apps.bot.handlers.callbacks.format_expense_confirmation")
    @patch("apps.bot.handlers.callbacks.restore_expense")
    @patch("apps.bot.handlers.callbacks.get_user_by_telegram_id")
    async def test_restore_success_shows_expense(
        self, mock_get_user, mock_restore, mock_format, mock_update_cb
    ):
        mock_get_user.return_value = MagicMock()
        mock_expense = MagicMock()
        mock_expense.id = 55
        mock_restore.return_value = mock_expense
        mock_format.return_value = "✅ Gasto restaurado correctamente"

        await on_restore_click(mock_update_cb, AsyncMock(), "99")

        mock_update_cb.callback_query.answer.assert_called_with("✅ Gasto restaurado")
        mock_update_cb.callback_query.edit_message_text.assert_called_with(
            "✅ Gasto restaurado correctamente", reply_markup=ANY
        )

    @patch("apps.bot.handlers.callbacks.restore_expense")
    @patch("apps.bot.handlers.callbacks.get_user_by_telegram_id")
    async def test_restore_expired_shows_error(
        self, mock_get_user, mock_restore, mock_update_cb
    ):
        mock_get_user.return_value = MagicMock()
        mock_restore.side_effect = ObjectDoesNotExist("Expiró")

        await on_restore_click(mock_update_cb, AsyncMock(), "99")

        mock_update_cb.callback_query.answer.assert_called_with(
            "⚠️ Error", show_alert=True
        )


# ============================================
# CATEGORIZACIÓN — CONFIRMACIÓN
# ============================================

class TestCatConfirm:

    async def test_confirm_records_positive_feedback(
        self, mock_update_cb, base_data
    ):
        data = base_data
        expense = data["expense"]

        count_before = await CategorySuggestionFeedback.objects.acount()

        await on_cat_confirm_click(mock_update_cb, AsyncMock(), str(expense.id))

        count_after = await CategorySuggestionFeedback.objects.acount()
        assert count_after == count_before + 1

        feedback = await CategorySuggestionFeedback.objects.select_related(
            'suggested_category'
        ).alatest('created_at')
        assert feedback.was_accepted is True

    async def test_confirm_edits_message(self, mock_update_cb, base_data):
        data = base_data
        expense = data["expense"]

        await on_cat_confirm_click(mock_update_cb, AsyncMock(), str(expense.id))

        mock_update_cb.callback_query.answer.assert_called_with("✅ Categoría confirmada")
        mock_update_cb.callback_query.edit_message_text.assert_called_once()

    async def test_confirm_expense_not_found_shows_error(self, mock_update_cb):
        await on_cat_confirm_click(mock_update_cb, AsyncMock(), "9999")

        mock_update_cb.callback_query.answer.assert_called_with(
            "⚠️ Error", show_alert=True
        )


# ============================================
# CATEGORIZACIÓN — LISTA
# ============================================

class TestCatList:

    async def test_list_shows_category_buttons(self, mock_update_cb, base_data):
        data = base_data
        expense = data["expense"]

        await on_cat_list_click(mock_update_cb, AsyncMock(), str(expense.id))

        mock_update_cb.callback_query.answer.assert_called_once()
        mock_update_cb.callback_query.edit_message_reply_markup.assert_called_once()

        call_kwargs = mock_update_cb.callback_query.edit_message_reply_markup.call_args[1]
        assert "reply_markup" in call_kwargs


# ============================================
# CATEGORIZACIÓN — SELECCIÓN
# ============================================

class TestCatSelect:

    async def test_select_updates_category_and_confirms_expense(
        self, mock_update_cb, base_data
    ):
        data = base_data
        expense = data["expense"]
        cat_b = data["cat_b"]

        await on_cat_select_click(
            mock_update_cb, AsyncMock(), f"{expense.id}:{cat_b.id}"
        )

        updated = await Expense.objects.select_related('category').aget(id=expense.id)
        assert updated.category.id == cat_b.id
        assert updated.status == Expense.STATUS_CONFIRMED

    async def test_select_records_feedback_when_category_changes(
        self, mock_update_cb, base_data
    ):
        data = base_data
        expense = data["expense"]
        cat_b = data["cat_b"]

        count_before = await CategorySuggestionFeedback.objects.acount()

        await on_cat_select_click(
            mock_update_cb, AsyncMock(), f"{expense.id}:{cat_b.id}"
        )

        count_after = await CategorySuggestionFeedback.objects.acount()
        assert count_after == count_before + 1

        feedback = await CategorySuggestionFeedback.objects.select_related(
            'final_category'
        ).alatest('created_at')
        assert feedback.was_accepted is False
        assert feedback.final_category.id == cat_b.id

    async def test_select_does_not_record_feedback_when_category_unchanged(
        self, mock_update_cb, base_data
    ):
        data = base_data
        expense = data["expense"]
        cat_a = data["cat_a"]  # misma categoría que ya tiene

        count_before = await CategorySuggestionFeedback.objects.acount()

        await on_cat_select_click(
            mock_update_cb, AsyncMock(), f"{expense.id}:{cat_a.id}"
        )

        count_after = await CategorySuggestionFeedback.objects.acount()
        assert count_after == count_before

    async def test_select_expense_not_found_shows_error(
        self, mock_update_cb, base_data
    ):
        data = base_data
        cat_b = data["cat_b"]

        await on_cat_select_click(
            mock_update_cb, AsyncMock(), f"9999:{cat_b.id}"
        )

        mock_update_cb.callback_query.answer.assert_called_with(
            "⚠️ Error", show_alert=True
        )


# ============================================
# CATEGORIZACIÓN — NUEVA CATEGORÍA
# ============================================

class TestCatNew:

    @patch("apps.bot.handlers.callbacks.set_pending_category_state")
    async def test_new_sets_redis_state_and_asks_name(
        self, mock_set_state, mock_update_cb, base_data
    ):
        data = base_data
        expense = data["expense"]
        mock_set_state.return_value = None

        await on_cat_new_click(mock_update_cb, AsyncMock(), str(expense.id))

        mock_set_state.assert_called_once_with(
            telegram_user_id=123456789,
            expense_id=expense.id
        )
        mock_update_cb.callback_query.answer.assert_called_once()
        call_args = mock_update_cb.callback_query.edit_message_text.call_args[0][0]
        assert "nueva categoría" in call_args.lower()
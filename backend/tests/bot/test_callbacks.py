"""
Tests de las acciones de botón, ya agnósticas al canal.
Cubre delete, restore y todo el flujo de categorización.
"""
import pytest
from unittest.mock import MagicMock, patch
from django.core.exceptions import ObjectDoesNotExist
from asgiref.sync import sync_to_async

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

from tests.constants import EXTERNAL_USER_ID

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
async def base_data():
    """Usuario, dos categorías y un expense listos para usar."""
    user = await sync_to_async(UserFactory)(telegram_id=int(EXTERNAL_USER_ID))
    cat_a = await sync_to_async(CategoryFactory)(name="Comida", user=user)
    cat_b = await sync_to_async(CategoryFactory)(name="Transporte", user=user)
    expense = await sync_to_async(ExpenseFactory)(
        user=user, category=cat_a, amount=1500, description="Pizza"
    )
    return {"user": user, "cat_a": cat_a, "cat_b": cat_b, "expense": expense}


# ============================================
# ROUTER DE ACCIONES
# ============================================

class TestCentralCallbackHandler:

    async def test_invalid_format_shows_error(self, make_callback_event, sender):
        # user=None a propósito: el router corta antes de tocarlo
        await central_callback_handler(make_callback_event("boton_roto"), None, sender)

        assert sender.last_ack["text"] == "❌ Error: Formato de botón inválido"
        assert sender.last_ack["alert"] is True
        assert sender.edits == []

    async def test_unknown_action_shows_warning(self, make_callback_event, sender):
        await central_callback_handler(make_callback_event("hack:99"), None, sender)

        assert sender.last_ack["text"] == "⚠️ Acción desconocida"
        assert sender.edits == []

    async def test_despacha_a_la_accion_correcta(
        self, make_callback_event, base_data, sender
    ):
        data = base_data
        await central_callback_handler(
            make_callback_event(f"cat_confirm:{data['expense'].id}"),
            data["user"], sender,
        )

        assert sender.last_ack["text"] == "✅ Categoría confirmada"


# ============================================
# DELETE Y RESTORE
# ============================================

class TestDeleteAndRestore:

    @patch("apps.bot.handlers.callbacks.delete_expense")
    async def test_delete_success_offers_undo(
        self, mock_delete, make_callback_event, sender
    ):
        mock_delete.return_value = 99

        await on_delete_click(make_callback_event("del:55"), MagicMock(), sender, "55")

        assert sender.last_ack["text"] == "🗑️ Gasto eliminado"
        assert "🗑️ Gasto eliminado de tu historial" in sender.last_edit["text"]
        assert sender.callback_ids(sender.last_edit) == ["undo:99"]

    @patch("apps.bot.handlers.callbacks.delete_expense")
    async def test_delete_edita_el_mensaje_original(
        self, mock_delete, make_callback_event, sender
    ):
        """El edit_ref debe ser el del mensaje que tenía el botón."""
        mock_delete.return_value = 99

        await on_delete_click(make_callback_event("del:55"), MagicMock(), sender, "55")

        assert sender.last_edit["edit_ref"] == "294"
        assert sender.replies == []  # edita, no manda mensaje nuevo

    @patch("apps.bot.handlers.callbacks.delete_expense")
    async def test_delete_not_found_shows_error(
        self, mock_delete, make_callback_event, sender
    ):
        mock_delete.side_effect = ObjectDoesNotExist("No existe")

        await on_delete_click(make_callback_event("del:55"), MagicMock(), sender, "55")

        assert sender.last_ack["text"] == "⚠️ Error"
        assert sender.last_ack["alert"] is True

    @patch("apps.bot.handlers.callbacks.format_expense_confirmation")
    @patch("apps.bot.handlers.callbacks.restore_expense")
    async def test_restore_success_shows_expense(
        self, mock_restore, mock_format, make_callback_event, sender
    ):
        mock_expense = MagicMock()
        mock_expense.id = 55
        mock_restore.return_value = mock_expense
        mock_format.return_value = "✅ Gasto restaurado correctamente"

        await on_restore_click(make_callback_event("undo:99"), MagicMock(), sender, "99")

        assert sender.last_ack["text"] == "✅ Gasto restaurado"
        assert sender.last_edit["text"] == "✅ Gasto restaurado correctamente"
        assert sender.callback_ids(sender.last_edit) == ["del:55"]

    @patch("apps.bot.handlers.callbacks.restore_expense")
    async def test_restore_expired_shows_error(
        self, mock_restore, make_callback_event, sender
    ):
        mock_restore.side_effect = ObjectDoesNotExist("Expiró")

        await on_restore_click(make_callback_event("undo:99"), MagicMock(), sender, "99")

        assert sender.last_ack["text"] == "⚠️ Error"
        assert sender.last_ack["alert"] is True


# ============================================
# CATEGORIZACIÓN — CONFIRMACIÓN
# ============================================

class TestCatConfirm:

    async def test_confirm_records_positive_feedback(
        self, make_callback_event, base_data, sender
    ):
        data = base_data
        expense = data["expense"]

        count_before = await CategorySuggestionFeedback.objects.acount()

        await on_cat_confirm_click(
            make_callback_event(f"cat_confirm:{expense.id}"),
            data["user"], sender, str(expense.id),
        )

        assert await CategorySuggestionFeedback.objects.acount() == count_before + 1

        feedback = await CategorySuggestionFeedback.objects.select_related(
            "suggested_category"
        ).alatest("created_at")
        assert feedback.was_accepted is True

    async def test_confirm_edits_message_and_removes_buttons(
        self, make_callback_event, base_data, sender
    ):
        data = base_data
        expense = data["expense"]

        await on_cat_confirm_click(
            make_callback_event(f"cat_confirm:{expense.id}"),
            data["user"], sender, str(expense.id),
        )

        assert sender.last_ack["text"] == "✅ Categoría confirmada"
        assert len(sender.edits) == 1
        # sin options: el teclado desaparece, igual que edit_message_text sin markup
        assert sender.last_edit["options"] is None

    async def test_confirm_expense_not_found_shows_error(
        self, make_callback_event, base_data, sender
    ):
        data = base_data

        await on_cat_confirm_click(
            make_callback_event("cat_confirm:9999"), data["user"], sender, "9999"
        )

        assert sender.last_ack["text"] == "⚠️ Error"
        assert sender.last_ack["alert"] is True
        assert "No se encontró el gasto" in sender.last_edit["text"]


# ============================================
# CATEGORIZACIÓN — LISTA
# ============================================

class TestCatList:

    async def test_list_edita_solo_los_botones(
        self, make_callback_event, base_data, sender
    ):
        """
        Conserva el texto del mensaje: text=None replica
        edit_message_reply_markup.
        """
        data = base_data
        expense = data["expense"]

        await on_cat_list_click(
            make_callback_event(f"cat_list:{expense.id}"),
            data["user"], sender, str(expense.id),
        )

        assert sender.last_ack["text"] == ""      # ack mudo
        assert sender.last_edit["text"] is None
        assert sender.last_edit["edit_ref"] == "294"
        assert any("cat_select" in cb for cb in sender.callback_ids(sender.last_edit))

    async def test_list_preserva_el_layout_de_filas(
        self, make_callback_event, base_data, sender
    ):
        """base_data tiene 2 categorías: una fila de 2 + 'Nueva' sola."""
        data = base_data
        expense = data["expense"]

        await on_cat_list_click(
            make_callback_event(f"cat_list:{expense.id}"),
            data["user"], sender, str(expense.id),
        )

        filas = sender.last_edit["options"]
        assert [len(f) for f in filas] == [2, 1]
        assert filas[-1][0].id == f"cat_new:{expense.id}"


# ============================================
# CATEGORIZACIÓN — SELECCIÓN
# ============================================

class TestCatSelect:

    async def test_select_updates_category_and_confirms_expense(
        self, make_callback_event, base_data, sender
    ):
        data = base_data
        expense, cat_b = data["expense"], data["cat_b"]

        await on_cat_select_click(
            make_callback_event(f"cat_select:{expense.id}:{cat_b.id}"),
            data["user"], sender, f"{expense.id}:{cat_b.id}",
        )

        updated = await Expense.objects.select_related("category").aget(id=expense.id)
        assert updated.category.id == cat_b.id
        assert updated.status == Expense.STATUS_CONFIRMED

    async def test_select_records_feedback_when_category_changes(
        self, make_callback_event, base_data, sender
    ):
        data = base_data
        expense, cat_b = data["expense"], data["cat_b"]

        count_before = await CategorySuggestionFeedback.objects.acount()

        await on_cat_select_click(
            make_callback_event(f"cat_select:{expense.id}:{cat_b.id}"),
            data["user"], sender, f"{expense.id}:{cat_b.id}",
        )

        assert await CategorySuggestionFeedback.objects.acount() == count_before + 1

        feedback = await CategorySuggestionFeedback.objects.select_related(
            "final_category"
        ).alatest("created_at")
        assert feedback.was_accepted is False
        assert feedback.final_category.id == cat_b.id

    async def test_select_does_not_record_feedback_when_category_unchanged(
        self, make_callback_event, base_data, sender
    ):
        data = base_data
        expense, cat_a = data["expense"], data["cat_a"]

        count_before = await CategorySuggestionFeedback.objects.acount()

        await on_cat_select_click(
            make_callback_event(f"cat_select:{expense.id}:{cat_a.id}"),
            data["user"], sender, f"{expense.id}:{cat_a.id}",
        )

        assert await CategorySuggestionFeedback.objects.acount() == count_before

    async def test_select_ofrece_eliminar_despues_de_confirmar(
        self, make_callback_event, base_data, sender
    ):
        data = base_data
        expense, cat_b = data["expense"], data["cat_b"]

        await on_cat_select_click(
            make_callback_event(f"cat_select:{expense.id}:{cat_b.id}"),
            data["user"], sender, f"{expense.id}:{cat_b.id}",
        )

        assert sender.last_ack["text"] == "✅ Categoría actualizada"
        assert sender.callback_ids(sender.last_edit) == [f"del:{expense.id}"]

    async def test_select_expense_not_found_shows_error(
        self, make_callback_event, base_data, sender
    ):
        data = base_data
        cat_b = data["cat_b"]

        await on_cat_select_click(
            make_callback_event(f"cat_select:9999:{cat_b.id}"),
            data["user"], sender, f"9999:{cat_b.id}",
        )

        assert sender.last_ack["text"] == "⚠️ Error"
        assert sender.last_ack["alert"] is True


# ============================================
# CATEGORIZACIÓN — NUEVA CATEGORÍA
# ============================================

class TestCatNew:

    @patch("apps.bot.handlers.callbacks.set_pending_category_state")
    async def test_new_sets_state_and_asks_name(
        self, mock_set_state, make_callback_event, base_data, sender
    ):
        data = base_data
        expense = data["expense"]
        mock_set_state.return_value = None

        await on_cat_new_click(
            make_callback_event(f"cat_new:{expense.id}"),
            data["user"], sender, str(expense.id),
        )

        # El id llega como string desde el evento canónico
        mock_set_state.assert_called_once_with(
            telegram_user_id=EXTERNAL_USER_ID,
            expense_id=expense.id,
        )
        assert sender.last_ack["text"] == ""
        assert "nueva categoría" in sender.last_edit["text"].lower()
        assert sender.last_edit["parse_mode"] == "HTML"
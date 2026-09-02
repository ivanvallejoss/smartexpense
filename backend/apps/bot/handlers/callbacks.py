"""
Manejo de acciones (clicks de botón), agnóstico al canal.

Cada callback recibe el evento con type="callback", donde event.text
lleva el id de la Option elegida ("del:55", "cat_select:12:3").
"""
import logging

from django.core.exceptions import ObjectDoesNotExist

from apps.bot.state import set_pending_category_state
from apps.bot.utils import format_expense_confirmation
from apps.core.models import Category, Expense
from services.channels.events import ChannelEvent
from services.channels.senders import Sender
from services.expenses import delete_expense, restore_expense
from services.ml.helper import record_categorization_feedback
from services.selectors import get_user_categories_or_defaults

from .helpers import category_selection_options, delete_options, undo_options

logger = logging.getLogger(__name__)


# ==================================================================
#                        CATEGORIZACIÓN
# ==================================================================


async def on_cat_confirm_click(event: ChannelEvent, user, sender: Sender, payload: str) -> None:
    expense_id = int(payload)

    try:
        expense = await Expense.objects.select_related("category", "user").aget(
            id=expense_id, user=user
        )

        await record_categorization_feedback(
            expense=expense,
            suggested_category=expense.category,
            accepted=True,
        )

        await sender.ack(event.ack_ref, "✅ Categoría confirmada")
        await sender.edit(
            event.conversation_id,
            event.edit_ref,
            text=format_expense_confirmation(expense, auto_categorized=False),
        )

    except Expense.DoesNotExist:
        await sender.ack(event.ack_ref, "⚠️ Error", alert=True)
        await sender.edit(event.conversation_id, event.edit_ref, text="⚠️ No se encontró el gasto.")


async def on_cat_list_click(event: ChannelEvent, user, sender: Sender, payload: str) -> None:
    """Cambia solo los botones y conserva el texto del mensaje."""
    expense_id = int(payload)
    categories = await get_user_categories_or_defaults(user)

    await sender.ack(event.ack_ref)
    await sender.edit(
        event.conversation_id,
        event.edit_ref,
        options=category_selection_options(expense_id, categories),
    )


async def on_cat_select_click(event: ChannelEvent, user, sender: Sender, payload: str) -> None:
    """payload: "{expense_id}:{category_id}"."""
    expense_id, category_id = payload.split(":")
    expense_id = int(expense_id)
    category_id = int(category_id)

    try:
        expense = await Expense.objects.select_related("category", "user").aget(
            id=expense_id, user=user
        )
        new_category = await Category.objects.aget(id=category_id)

        previous_category = expense.category

        expense.category = new_category
        expense.status = Expense.STATUS_CONFIRMED
        await expense.asave(update_fields=["category", "status", "updated_at"])

        if previous_category != new_category:
            await record_categorization_feedback(
                expense=expense,
                suggested_category=previous_category,
                accepted=False,
                final_category=new_category,
            )

        await sender.ack(event.ack_ref, "✅ Categoría actualizada")
        await sender.edit(
            event.conversation_id,
            event.edit_ref,
            text=format_expense_confirmation(expense, auto_categorized=False),
            options=delete_options(expense.id),
        )

    except (Expense.DoesNotExist, Category.DoesNotExist):
        await sender.ack(event.ack_ref, "⚠️ Error", alert=True)
        await sender.edit(
            event.conversation_id,
            event.edit_ref,
            text="⚠️ No se pudo actualizar la categoría.",
        )


async def on_cat_new_click(event: ChannelEvent, user, sender: Sender, payload: str) -> None:
    expense_id = int(payload)

    await set_pending_category_state(
        channel=event.channel,
        external_user_id=event.external_user_id,
        expense_id=expense_id,
    )

    await sender.ack(event.ack_ref)
    await sender.edit(
        event.conversation_id,
        event.edit_ref,
        text=(
            "📝 ¿Cómo querés llamar a la nueva categoría?\n\n"
            "Enviá el nombre en el siguiente mensaje.\n"
            "Ej: <i>Mascotas</i>, <i>Gimnasio</i>, <i>Regalos</i>"
        ),
        parse_mode="HTML",
    )


# ==================================================================
#                      DELETE Y RESTORE
# ==================================================================


async def on_delete_click(event: ChannelEvent, user, sender: Sender, payload: str) -> None:
    expense_id = int(payload)

    try:
        deleted_object_id = await delete_expense(user=user, expense_id=expense_id)

        await sender.ack(event.ack_ref, "🗑️ Gasto eliminado")
        await sender.edit(
            event.conversation_id,
            event.edit_ref,
            text="🗑️ Gasto eliminado de tu historial.\n\n¿Te equivocaste?",
            options=undo_options(deleted_object_id),
        )

    except ObjectDoesNotExist:
        await sender.ack(event.ack_ref, "⚠️ Error", alert=True)
        await sender.edit(
            event.conversation_id,
            event.edit_ref,
            text="⚠️ No se pudo borrar el gasto (quizás ya no existe).",
        )


async def on_restore_click(event: ChannelEvent, user, sender: Sender, payload: str) -> None:
    deleted_object_id = int(payload)

    try:
        expense = await restore_expense(user=user, deleted_object_id=deleted_object_id)

        await sender.ack(event.ack_ref, "✅ Gasto restaurado")
        await sender.edit(
            event.conversation_id,
            event.edit_ref,
            text=format_expense_confirmation(expense),
            options=delete_options(expense.id),
        )

    except ObjectDoesNotExist:
        await sender.ack(event.ack_ref, "⚠️ Error", alert=True)
        await sender.edit(
            event.conversation_id,
            event.edit_ref,
            text="⚠️ No se pudo restaurar (el registro expiró o ya fue restaurado).",
        )


# ==================================================================
#                       ROUTER DE ACCIONES
# ==================================================================


async def central_callback_handler(event: ChannelEvent, user, sender: Sender) -> None:
    """
    event.text tiene formato "accion:payload".
    """
    data = event.text

    if ":" not in data:
        await sender.ack(event.ack_ref, "❌ Error: Formato de botón inválido", alert=True)
        return

    action_key, payload = data.split(":", 1)

    handler_func = CALLBACK_ROUTES.get(action_key)

    if handler_func:
        await handler_func(event, user, sender, payload)
    else:
        logger.warning(f"Recibido callback desconocido: {action_key}")
        await sender.ack(event.ack_ref, "⚠️ Acción desconocida")


CALLBACK_ROUTES = {
    "del": on_delete_click,
    "undo": on_restore_click,
    "cat_confirm": on_cat_confirm_click,
    "cat_list": on_cat_list_click,
    "cat_select": on_cat_select_click,
    "cat_new": on_cat_new_click,
}

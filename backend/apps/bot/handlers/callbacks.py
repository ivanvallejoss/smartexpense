"""
central_callback_handler is in charge of managing every button event
"""
from django.core.exceptions import ObjectDoesNotExist

from telegram import Update
from telegram.ext import ContextTypes

from services.ml.helper import record_categorization_feedback
from services.selectors import get_user_categories_or_defaults
from services.expenses import delete_expense, restore_expense
from services.users import get_user_by_telegram_id




from .helpers import get_undo_keyboard_markup, get_delete_keyboard_markup

from apps.bot.state import set_pending_category_state
from apps.bot.utils import format_expense_confirmation
from apps.core.models import Expense, Category
from apps.bot.handlers.helpers import get_category_selection_keyboard_markup, get_delete_keyboard_markup

import logging
logger = logging.getLogger(__name__)



# ==================================================================================
#                         CATEGORIZACIÓN
# ==================================================================================

async def on_cat_confirm_click(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """
    El usuario confirmó que la categoría sugerida es correcta.
    Registramos feedback positivo.
    """
    query = update.callback_query
    expense_id = int(payload)
    user = await get_user_by_telegram_id(update.effective_user.id)

    try:
        expense = await Expense.objects.select_related('category', 'user').aget(
            id=expense_id,
            user=user
        )

        await record_categorization_feedback(
            expense=expense,
            suggested_category=expense.category,
            accepted=True,
        )

        await query.answer("✅ Categoría confirmada")
        await query.edit_message_text(
            format_expense_confirmation(expense, auto_categorized=False)
        )

    except Expense.DoesNotExist:
        await query.answer("⚠️ Error", show_alert=True)
        await query.edit_message_text("⚠️ No se encontró el gasto.")


async def on_cat_list_click(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """
    El usuario quiere cambiar la categoría sugerida.
    Mostramos la lista de categorías disponibles.
    """
    query = update.callback_query
    expense_id = int(payload)
    user = await get_user_by_telegram_id(update.effective_user.id)

    categories = await get_user_categories_or_defaults(user)

    await query.answer()
    await query.edit_message_reply_markup(
        reply_markup=get_category_selection_keyboard_markup(
            expense_id=expense_id,
            categories=categories
        )
    )


async def on_cat_select_click(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """
    El usuario seleccionó una categoría de la lista.
    Actualiza el gasto, registra feedback negativo con la categoría final.
    payload tiene formato: {expense_id}:{category_id}
    """
    query = update.callback_query
    user = await get_user_by_telegram_id(update.effective_user.id)

    expense_id, category_id = payload.split(":")
    expense_id = int(expense_id)
    category_id = int(category_id)

    try:
        expense = await Expense.objects.select_related('category', 'user').aget(
            id=expense_id,
            user=user
        )
        new_category = await Category.objects.aget(id=category_id)

        previous_category = expense.category

        # Actualizamos categoría y confirmamos el gasto si estaba pendiente
        expense.category = new_category
        expense.status = Expense.STATUS_CONFIRMED
        await expense.asave(update_fields=['category', 'status', 'updated_at'])

        # Registramos el feedback solo si hubo cambio real
        if previous_category != new_category:
            await record_categorization_feedback(
                expense=expense,
                suggested_category=previous_category,
                accepted=False,
                final_category=new_category,
            )

        await query.answer("✅ Categoría actualizada")
        await query.edit_message_text(
            format_expense_confirmation(expense, auto_categorized=False),
            reply_markup=get_delete_keyboard_markup(expense_id=expense.id)
        )

    except (Expense.DoesNotExist, Category.DoesNotExist):
        await query.answer("⚠️ Error", show_alert=True)
        await query.edit_message_text("⚠️ No se pudo actualizar la categoría.")

async def on_cat_new_click(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """
    El usuario quiere crear una categoría nueva.
    Guardamos el estado en Redis y le pedimos el nombre.
    """
    query = update.callback_query
    expense_id = int(payload)
    telegram_user_id = update.effective_user.id

    await set_pending_category_state(
        telegram_user_id=telegram_user_id,
        expense_id=expense_id
    )

    await query.answer()
    await query.edit_message_text(
        "📝 ¿Cómo querés llamar a la nueva categoría?\n\n"
        "Enviá el nombre en el siguiente mensaje.\n"
        "Ej: <i>Mascotas</i>, <i>Gimnasio</i>, <i>Regalos</i>",
        parse_mode="HTML"
    )


# ==================================================================================
#                             DELETE AND UNDELETE
# ==================================================================================

async def on_delete_click(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """
    Gets the expense_id and user_id of the last expense
    Calls delete_expense to get rid of the expense properly
    """
    query = update.callback_query
    # Simplifying we get the user through the telegram ID
    telegram_id = update.effective_user.id
    user = await get_user_by_telegram_id(telegram_id)

    expense_id = int(payload)

    try:
        deleted_object_id = await delete_expense(user=user, expense_id=expense_id)

        reply_markup = get_undo_keyboard_markup(deleted_object_id)

        await query.answer("🗑️ Gasto eliminado")
        await query.edit_message_text(
            "🗑️ Gasto eliminado de tu historial.\n\n¿Te equivocaste?", 
            reply_markup=reply_markup
        )

    except ObjectDoesNotExist:
        await query.answer("⚠️ Error", show_alert=True)
        await query.edit_message_text("⚠️ No se pudo borrar el gasto (quizás ya no existe).")


async def on_restore_click(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """
    Restaura un gasto desde la papelera de reciclaje.
    """
    query = update.callback_query
    telegram_user = update.effective_user

    user = await get_user_by_telegram_id(telegram_id=telegram_user.id)
    deleted_object_id = int(payload)

    try:
        # Llamamos a nuestro servicio de restauracion
        expense = await restore_expense(user=user, deleted_object_id=deleted_object_id)

        reply_markup = get_delete_keyboard_markup(expense_id=expense.id)
        message = format_expense_confirmation(expense)

        await query.answer("✅ Gasto restaurado")   
        await query.edit_message_text(message, reply_markup=reply_markup)
   
    except ObjectDoesNotExist:
        await query.answer("⚠️ Error", show_alert=True)
        await query.edit_message_text("⚠️ No se pudo restaurar (el registro expiró o ya fue restaurado).")


# ==================================================================================
#                            CALLBACKS ROUTER
# ==================================================================================
async def central_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Generic Function to receive the event and call the specific function
    data: `action:id`
    """
    query = update.callback_query
    data = query.data # Ej: "del:55"
    

    if ":" not in data:
        await query.answer("❌ Error: Formato de botón inválido", show_alert=True)
        return

    # Dividing the function from the id 
    action_key, payload = data.split(":", 1) 
    
    # Mapping the function
    handler_func = CALLBACK_ROUTES.get(action_key)
    
    if handler_func:
        # Execute the corresponding function with the specific "payload"
        await handler_func(update, context, payload)
    else:
        logger.warning(f"Recibido callback desconocido: {action_key}")
        await query.answer("⚠️ Acción desconocida")


# ==================================================================================
#                               Routes 
# ==================================================================================
# It gives the central_callback_handler the route to the specific function for the event
CALLBACK_ROUTES = {
    "del": on_delete_click,
    "undo": on_restore_click,
    "cat_confirm": on_cat_confirm_click,
    "cat_list": on_cat_list_click,
    "cat_select": on_cat_select_click,
    "cat_new": on_cat_new_click,
}
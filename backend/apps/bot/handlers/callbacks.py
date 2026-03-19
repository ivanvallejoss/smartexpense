"""
central_callback_handler is in charge of managing every button event
"""
from django.core.exceptions import ObjectDoesNotExist

from telegram import Update
from telegram.ext import ContextTypes

from services.expenses import delete_expense, restore_expense
from services.users import get_user_by_telegram_id
from .helpers import get_undo_keyboard_markup, get_keyboard_markup
from apps.bot.utils import format_expense_confirmation

import logging
logger = logging.getLogger(__name__)


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

        reply_markup = get_keyboard_markup(expense_id=expense.id)
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
    # "edit": on_edit_click,  <-- Future feature
}
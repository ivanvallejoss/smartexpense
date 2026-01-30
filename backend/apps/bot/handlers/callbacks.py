"""
central_callback_handler is in charge of managing every button event
"""

from telegram import Update
from telegram.ext import ContextTypes
from services.expenses import delete_expense

import logging
logger = logging.getLogger(__name__)

async def on_delete_click(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """
    Gets the expense_id and user_id of the last expense
    Calls delete_expense to get rid of the expense properly
    """
    query = update.callback_query
    
    # Call the logic to delete the expense
    user_id = update.effective_user.id
    was_deleted = await delete_expense(expense_id=payload, user_telegram_id=user_id)
    
    if was_deleted:
        # UX: Feedback positive
        await query.answer("🗑️ Gasto eliminado") # Toast notification
        await query.edit_message_text(f"🗑️ Gasto eliminado correctamente.")
    else:
        # UX: Feedback negative
        await query.answer("⚠️ Error", show_alert=True)
        await query.edit_message_text("⚠️ No se pudo borrar el gasto (quizás ya no existe).")



# --------- Routes ------------
# It gives the central_callback_handler the route to the specific function for the event
CALLBACK_ROUTES = {
    "del": on_delete_click,
    # "edit": on_edit_click,  <-- Future feature
}

# Central logic, like a router
async def central_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Generic Function to receive the event and call the specific function
    """
    query = update.callback_query
    data = query.data # Ej: "del:55"
    
    # just in case
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
        # exception in case it does not exist.
        logger.warning(f"Recibido callback desconocido: {action_key}")
        await query.answer("⚠️ Acción desconocida")
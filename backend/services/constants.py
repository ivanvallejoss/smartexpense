# backend/services/constants.py

"""
Fuente de verdad central para colores y emojis de categorías.

Regla: cualquier lugar del sistema que necesite un color o emoji
de categoría debe importar desde acá. No hardcodear en otro lado.
"""

# Mapeo nombre → color HEX
# Usado por: seed_data.py, ExpenseCategorizer._check_and_create_from_defaults
CATEGORY_COLORS = {
    "Comida":          "#FF5733",
    "Supermercado":    "#33FF57",
    "Transporte":      "#3366FF",
    "Delivery":        "#FF33F5",
    "Servicios":       "#FFC300",
    "Salud":           "#F38181",
    "Entretenimiento": "#C70039",
    "Ropa":            "#900C3F",
    "Hogar":           "#581845",
    "Educación":       "#1E8449",
}

# Mapeo nombre → emoji (fuente primaria)
# Prioridad 1: si la categoría tiene un nombre conocido, usamos este emoji
CATEGORY_EMOJIS = {
    "Comida":          "🍔",
    "Supermercado":    "🛒",
    "Transporte":      "🚗",
    "Delivery":        "🛵",
    "Servicios":       "💡",
    "Salud":           "💊",
    "Entretenimiento": "🎬",
    "Ropa":            "👕",
    "Hogar":           "🏠",
    "Educación":       "📚",
}

# Mapeo HEX → emoji (fuente secundaria / fallback)
# Prioridad 2: si el nombre no está en CATEGORY_EMOJIS pero el color sí está acá
# Cubre categorías custom del usuario con colores del picker del frontend
HEX_TO_EMOJI = {
    "#FF5733": "🔴",
    "#33FF57": "🟢",
    "#3366FF": "🔵",
    "#FF33F5": "🟣",
    "#FFC300": "🟡",
    "#F38181": "🩷",
    "#C70039": "🔴",
    "#900C3F": "🟤",
    "#581845": "🟤",
    "#1E8449": "🟢",
    "#6B7280": "📂",  # color default del modelo
}

# Emoji de último recurso
DEFAULT_EMOJI = "📂"
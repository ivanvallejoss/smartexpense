# backend/services/constants.py

"""
Fuente de verdad central para colores y emojis de categorías.

Regla: cualquier lugar del sistema que necesite un color o emoji
de categoría debe importar desde acá. No hardcodear en otro lado.
"""

from zoneinfo import ZoneInfo

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

# Mapeo de número de mes → nombre en español
# Usado por: selectors.get_month_stats, cualquier superficie que formatee fechas
SPANISH_MONTHS = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

# ---------------------------------------------------------------
#   ZONA HORARIA Y RANGOS TEMPORALES (Fase C — dashboard web)
# ---------------------------------------------------------------


# Zona horaria del usuario. Los datos se guardan en UTC; los bordes de los
# rangos se calculan en esta zona para que "julio" sea julio en Buenos Aires
# y no en UTC. Mismo criterio que get_month_stats().
USER_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

# Rangos relativos del dashboard (B4-S1, enum extendido con "mes").
# valor -> cantidad de meses calendario hacia atras, incluyendo el actual.
RANGOS = {
    "mes": 1,
    "3m": 3,
    "6m": 6,
    "12m": 12,
}
RANGO_DEFAULT = "mes"

RANGO_LABELS = {
    "mes": "Este mes",
    "3m": "Últimos 3 meses",
    "6m": "Últimos 6 meses",
    "12m": "Últimos 12 meses",
}

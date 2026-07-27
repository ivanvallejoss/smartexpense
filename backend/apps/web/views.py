"""
Vistas HTML del dashboard (Fase C, capa C1: SSR sin HTMX).

La view es async porque el sistema lo es: consume services/selectors.py tal como
esta, sin desarmar los wrappers del bot. Eso impone dos reglas:

  1. request.user no se toca. Es perezoso y pega a la base: con usuario logueado
     tira SynchronousOnlyOperation. Se usa await request.auser().
  2. El template no puede evaluar nada perezoso. Todo llega resuelto desde
     get_dashboard_data(): listas, no querysets.

Por la misma razon no se usa LoginRequiredMixin: su dispatch es sync y devuelve
un HttpResponseRedirect que Django intenta await-ear en una view async.
"""
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.views.generic import View

from apps.web.filters import parse_dashboard_filters
from services.constants import RANGO_LABELS, RANGOS, SPANISH_MONTHS
from services.selectors import get_dashboard_data


def _periodo_label(filtros, desde) -> str:
    """Etiqueta del hero. Sin esto el numero grande es ambiguo."""
    if filtros.rango == "mes":
        return f"{SPANISH_MONTHS[desde.month]} {desde.year}"
    return RANGO_LABELS[filtros.rango].lower()


def _build_context(filtros, data):
    chips = [
        {
            "categoria": categoria,
            "activa": categoria.id in filtros.categorias,
            "url": filtros.toggle_categoria(categoria.id).querystring(),
        }
        for categoria in data["categorias"]
    ]

    opciones_rango = [
        {"value": valor, "label": RANGO_LABELS[valor], "selected": valor == filtros.rango}
        for valor in RANGOS
    ]

    return {
        "filtros": filtros,
        "avisos": filtros.avisos,
        "balance": data["balance"],
        "total_gastos": data["total_gastos"],
        "periodo_label": _periodo_label(filtros, data["desde"]),
        "gastos": data["gastos"],
        "chips": chips,
        "opciones_rango": opciones_rango,
        "url_desnuda": "?",
        "url_siguiente": filtros.con_pagina(data["page"] + 1).querystring() if data["has_next"] else None,
        "url_anterior": filtros.con_pagina(data["page"] - 1).querystring() if data["has_previous"] else None,
        "page": data["page"],
        "num_pages": data["num_pages"],
    }


class DashboardView(View):
    template_name = "dashboard/index.html"

    async def get(self, request):
        user = await request.auser()
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        filtros = parse_dashboard_filters(request)
        data = await get_dashboard_data(
            user,
            category_ids=filtros.categorias,
            rango=filtros.rango,
            page=filtros.page,
        )
        return render(request, self.template_name, _build_context(filtros, data))

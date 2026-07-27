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
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import View

from apps.web.filters import parse_dashboard_filters
from services.constants import RANGO_LABELS, RANGOS, SPANISH_MONTHS
from services.expenses import delete_expense
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
        "url_desnuda": reverse("dashboard"),
        "url_actual": filtros.querystring(),
        "url_siguiente": filtros.con_pagina(data["page"] + 1).querystring() if data["has_next"] else None,
        "url_anterior": filtros.con_pagina(data["page"] - 1).querystring() if data["has_previous"] else None,
        "page": data["page"],
        "num_pages": data["num_pages"],
    }


class _SesionRequerida(View):
    """
    Guard de sesion para views async. Es lo unico que comparten la familia de
    lectura y la de mutacion, asi que es lo unico que se hereda: la vista de
    borrado heredaba antes un get() que no aceptaba su argumento de URL y
    devolvia 500 en vez de 405.
    """

    async def usuario(self, request):
        user = await request.auser()
        return user if user.is_authenticated else None


async def _render_dashboard(request, template_name, user, filtros):
    """Carga los datos del estado y renderiza. Unico camino a get_dashboard_data."""
    data = await get_dashboard_data(
        user,
        category_ids=filtros.categorias,
        rango=filtros.rango,
        page=filtros.page,
    )
    return render(request, template_name, _build_context(filtros, data))


class _DashboardBaseView(_SesionRequerida):
    """
    Familia de lectura. Lo unico que distingue a las tres vistas es que template
    renderizan: la completa devuelve el documento, las parciales devuelven su
    region. Comparten filtros y selector, como pide B2.
    """
    template_name = None

    async def get(self, request):
        user = await self.usuario(request)
        if user is None:
            return redirect_to_login(request.get_full_path())

        filtros = parse_dashboard_filters(request)
        respuesta = await _render_dashboard(request, self.template_name, user, filtros)
        return self.finalizar(respuesta, filtros)

    def finalizar(self, respuesta, filtros):
        return respuesta


class DashboardView(_DashboardBaseView):
    template_name = "dashboard/index.html"


class DashboardExpensesView(_DashboardBaseView):
    """Endpoint de partial dedicado (B2): una URL propia por region swappable."""
    template_name = "dashboard/partials/_expense_items.html"


class DashboardResultsView(_DashboardBaseView):
    """
    Endpoint del wrapper #results: lo pide cada cambio de filtro.

    La URL canonica la escribe el server con HX-Replace-Url y no los templates.
    Si se usara hx-replace-url en el HTML, htmx pondria en la barra la URL de
    este endpoint interno, que no es navegable. Es replace y no push porque en
    mobile el back es salir, no deshacer (B4-S2).
    """
    template_name = "dashboard/partials/_results.html"

    def finalizar(self, respuesta, filtros):
        respuesta["HX-Replace-Url"] = reverse("dashboard") + filtros.querystring()
        return respuesta


class DashboardDeleteExpenseView(_SesionRequerida):
    """
    Borrado inline. Es POST y no DELETE porque el baseline sin JS es un <form>,
    y los forms HTML solo hablan GET y POST.

    La respuesta cambia segun el cliente, que es progressive enhancement y no
    una rama oculta: con htmx devuelve #results recalculado (balance y lista
    sincronizados por construccion, es el mismo render de C3); sin htmx redirige
    con Post/Redirect/Get para que F5 no reintente el borrado.
    """
    template_name = "dashboard/partials/_results.html"

    async def post(self, request, expense_id):
        user = await self.usuario(request)
        if user is None:
            return redirect_to_login(request.get_full_path())

        # Volver a la pagina 1 no es un detalle del render: la URL del redirect
        # sale del mismo objeto, asi que las dos no pueden contradecirse.
        filtros = parse_dashboard_filters(request).con_pagina(1)
        es_htmx = request.headers.get("HX-Request") == "true"

        try:
            await delete_expense(user, expense_id)
        except ObjectDoesNotExist:
            return self._error(request, es_htmx, filtros)

        if not es_htmx:
            return redirect(reverse("dashboard") + filtros.querystring())

        return await _render_dashboard(request, self.template_name, user, filtros)

    def _error(self, request, es_htmx, filtros):
        """
        Clase 2 de B5: falla que el usuario no puede corregir. #results queda
        intacto y el aviso va a la franja global via HX-Retarget. El 404 se
        swappea igual porque base.html configura responseHandling (R19).
        """
        if not es_htmx:
            return redirect(reverse("dashboard") + filtros.querystring())

        respuesta = render(
            request,
            "shared/_avisos.html",
            {"avisos": ["Ese gasto ya no existe. Se actualizó la vista."]},
            status=404,
        )
        respuesta["HX-Retarget"] = "#avisos"
        respuesta["HX-Reswap"] = "outerHTML"
        return respuesta

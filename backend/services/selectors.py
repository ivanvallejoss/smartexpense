"""
Service Layer
Logic to show data related to expenses
"""

from apps.core.models import Expense, Category
from django.core.exceptions import ObjectDoesNotExist

from django.core.paginator import Paginator

from services.constants import RANGO_DEFAULT, RANGOS, SPANISH_MONTHS, USER_TZ

from asgiref.sync import sync_to_async

from django.utils import timezone

from django.db.models import Count, Sum, Q
from decimal import Decimal
from typing import Optional

from zoneinfo import ZoneInfo

# ---------------------------------------
#           EXPENSES
# ---------------------------------------

@sync_to_async
def get_expenses(
    user, 
    limit:int=7,
    offset:int=0,
    month:Optional[int]=None,
    year:Optional[int]=None
    ):
    """
    Gets a LIST of expenses for a user
    """
    expenses = Expense.objects.filter(
        user=user,
        status=Expense.STATUS_CONFIRMED
        ).select_related('category')

    if month:
        expenses = expenses.filter(date__month=month)
    if year:
        expenses = expenses.filter(date__year=year)
    
    # filtering by offset & limit
    expenses = expenses.order_by('-date')[offset: offset + limit]
    
    # We need to return a list so we force Django to evaluate the queryset
    # Otherwise we can get an error for SychronousOnlyOperation
    return list(expenses)


@sync_to_async
def get_single_expense(
    user,
    expense_id: int,
):
    """
    Get a single expense + select_related to Category
    """
    try:
        # select_related helps getting the whole category object for this expense when needed it
        expense = Expense.objects.select_related("category").get(
            user=user, id=expense_id
        )
        return expense
    except Expense.DoesNotExist:
        raise ObjectDoesNotExist(
            f"The expense ID: {expense_id} does not belong to any of your expenses."
            )


@sync_to_async
def get_balance(user, month: int=None, year: int=None) -> float:
    """
    Getting the balance of the user.
    It filters by month or year if applied.
    """
    expenses = Expense.objects.filter(user=user, status=Expense.STATUS_CONFIRMED)
    
    if month:
        expenses = expenses.filter(date__month=month)
    if year:
        expenses = expenses.filter(date__year=year)

    resultado = expenses.aggregate(total_spent=Sum('amount'))

    # Devolvemos la propiedad especifica del diccionario
    # o 0.0 si no hay nada
    return resultado['total_spent'] or 0.0


# ---------------------------------------
#               STATS
# ---------------------------------------

@sync_to_async
def get_month_stats(user):
    """
    Function that returns last month expenses.
    """

    user_tz = ZoneInfo("America/Argentina/Buenos_Aires")
    now = timezone.now()
    # We convert the timezone to Buenos Aires to get the correct month start for the User
    local_now = now.astimezone(user_tz)
    local_month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # it used the server timezone
    expenses = Expense.objects.filter(
        user=user, 
        status=Expense.STATUS_CONFIRMED,
        date__gte=local_month_start, 
        date__lte=now
        )

    total_amount = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_count = expenses.count()

    by_category = list(
        expenses.values("category__name", "category__color")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
        )
    
    # We use the local month name
    local_month_name = local_now.strftime("%B %Y")
    local_month_name = f"{SPANISH_MONTHS[local_now.month]} {local_now.year}"

    return {
        "total_amount": total_amount, 
        "total_count": total_count, 
        "by_category": by_category, 
        "month_name": local_month_name}


# -------------------------------------
#              CATEGORY
# -------------------------------------

def get_category_by_id(category_id):
    """
    Obtiene una categoria por su ID.
    """
    try:
        return Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        raise ObjectDoesNotExist(
            f"La categoria con id {category_id} no existe."
            )


@sync_to_async
def get_user_categories_or_defaults(user):
    """
    Retorna todas las categorías disponibles para un usuario:
    sus propias categorías + las globales del sistema.
    """
    categories = list(
        Category.objects.filter(
            Q(user=user) | Q(is_default=True)
        ).order_by('name')
    )
    return categories

@sync_to_async
def get_category_by_id_or_default(user, category_id):
    """
    Busca la categoria por su ID.
    Filtra por si le pertenece al usuario o si es default del sistema.
    """
    try:
        return Category.objects.get(
            Q(id=category_id, user=user) | Q(id=category_id, is_default=True)
            )
    except Category.DoesNotExist:
        raise ObjectDoesNotExist(
            f"The ID category: {category_id} does not belong to any known category or it belongs to another user"
        )

# ---------------------------------------------------------------
#           DASHBOARD WEB (Fase C)
# ---------------------------------------------------------------


DASHBOARD_PAGE_SIZE = 20


def rango_bounds(rango: str):
    """
    Traduce un rango relativo a un par (desde, hasta) de datetimes aware.

    Los bordes se calculan en USER_TZ y despues se comparan contra el campo
    date, que Django almacena en UTC. Es el mismo criterio que get_month_stats
    y evita el bug de date__month: un gasto del 31 a las 22:00 de Buenos Aires
    se guarda como dia 1 en UTC y caeria en el mes equivocado.
    """
    meses = RANGOS.get(rango, RANGOS[RANGO_DEFAULT])

    hasta = timezone.now()
    local_now = hasta.astimezone(USER_TZ)

    inicio_mes_actual = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    year, month = inicio_mes_actual.year, inicio_mes_actual.month
    retroceso = meses - 1
    month -= retroceso
    while month < 1:
        month += 12
        year -= 1

    desde = inicio_mes_actual.replace(year=year, month=month)
    return desde, hasta


def _dashboard_queryset(user, category_ids, desde, hasta):
    """Queryset base del dashboard: confirmados, del rango, de las categorias pedidas."""
    qs = Expense.objects.filter(
        user=user,
        status=Expense.STATUS_CONFIRMED,
        date__gte=desde,
        date__lte=hasta,
    )
    if category_ids:
        qs = qs.filter(category_id__in=category_ids)
    return qs


@sync_to_async
def get_dashboard_data(user, category_ids=(), rango=RANGO_DEFAULT, page=1):
    """
    Devuelve TODO lo que el dashboard necesita, ya resuelto.

    Una sola llamada porque la view es async: cada sync_to_async es un salto al
    threadpool, y sobre todo porque el template no puede tocar la base. Nada de
    lo que sale de aca es perezoso: gastos es una lista con select_related y
    categorias es una lista.
    """
    desde, hasta = rango_bounds(rango)
    qs = _dashboard_queryset(user, category_ids, desde, hasta)

    balance = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    # -id desempata: sin eso dos gastos con la misma fecha pueden repetirse o
    # perderse entre paginas, que es exactamente lo que rompe el scroll infinito.
    paginator = Paginator(
        qs.select_related("category").order_by("-date", "-id"),
        DASHBOARD_PAGE_SIZE,
    )
    pagina = paginator.get_page(page)

    categorias = list(
        Category.objects.filter(Q(user=user) | Q(is_default=True)).order_by("name")
    )

    return {
        "gastos": list(pagina.object_list),
        "balance": balance,
        "total_gastos": paginator.count,
        "page": pagina.number,
        "num_pages": paginator.num_pages,
        "has_next": pagina.has_next(),
        "has_previous": pagina.has_previous(),
        "categorias": categorias,
        "desde": desde,
        "hasta": hasta,
    }

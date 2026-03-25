"""
Tests unitarios para los formateadores de texto del bot.
"""
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import MagicMock

from apps.bot.utils import format_amount, format_stats_message, format_expense_list

class TestFormatAmount:
    def test_format_integer_amount(self):
        """Prueba números enteros."""
        assert format_amount(Decimal('1500')) == '$1.500'
        assert format_amount(Decimal('50')) == '$50'

    def test_format_decimal_amount(self):
        """Prueba números con decimales."""
        assert format_amount(Decimal('1500.50')) == '$1.500,50'
        assert format_amount(Decimal('10.99')) == '$10,99'

    def test_format_millions(self):
        """Prueba números grandes con múltiples separadores de miles."""
        assert format_amount(Decimal('1500000.99')) == '$1.500.000,99'


class TestFormatStatsMessage:
    def test_empty_stats(self):
        """Si no hay gastos, debe devolver un mensaje amigable."""
        result = format_stats_message("Noviembre 2024", Decimal('0'), 0, [])
        assert "No tenés gastos registrados" in result
        assert "Noviembre 2024" in result

    def test_populated_stats_calculates_percentages(self):
        """Debe calcular los porcentajes correctos y asignar emojis."""
        by_category = [
            {"category__name": "Comida", "category__color": "#F54927", "total": Decimal('1000')},
            {"category__name": None, "category__color": "default", "total": Decimal('500')}
        ]
        
        resultado = format_stats_message(
            month_name="Noviembre 2024", 
            total_amount=Decimal('1500'), 
            total_count=2, 
            by_category=by_category
        )
        
        assert "Comida" in resultado
        assert "$1.500" in resultado  # El total
        assert "$1.000" in resultado  # El gasto en comida
        
        # Verificamos que se haya calculado un porcentaje aproximado (66 o 67)
        assert "66%" in resultado or "67%" in resultado or "66.6" in resultado


class TestFormatExpenseList:
    def test_empty_expense_list(self):
        result = format_expense_list([])
        assert "No tienes gastos registrados" in result

    def test_expense_with_description_and_category_renders_both(self):
        exp = MagicMock()
        exp.date = datetime(2026, 3, 14, 15, 0, tzinfo=timezone.utc)
        exp.description = "Supermercado"
        exp.amount = Decimal("1500.50")
        exp.category.name = "Comida"

        result = format_expense_list([exp])

        assert "Supermercado" in result
        assert "Comida" in result
        assert "$1.500,50" in result

    def test_expense_without_description_still_renders_amount(self):
        """
        Una expense sin descripción no rompe el formato —
        el monto siempre se muestra independientemente.
        """
        exp = MagicMock()
        exp.date = datetime(2026, 3, 14, 15, 0, tzinfo=timezone.utc)
        exp.description = ""
        exp.amount = Decimal("500")
        exp.category = None

        result = format_expense_list([exp])

        assert "500" in result

    def test_expense_without_category_omits_category_line(self):
        exp = MagicMock()
        exp.date = datetime(2026, 3, 14, 15, 0, tzinfo=timezone.utc)
        exp.description = "Sin categoria"
        exp.amount = Decimal("300")
        exp.category = None

        result = format_expense_list([exp])

        assert "Sin categoria" in result
        assert "Categoria" not in result

    def test_multiple_expenses_all_rendered(self):
        """
        Dado N expenses, verificamos que aparecen N descripciones
        distintas en el resultado — ninguna se pierde en el formateo.
        """
        expenses = []
        descriptions = ["Pizza", "Uber", "Supermercado"]

        for desc in descriptions:
            exp = MagicMock()
            exp.date = datetime(2026, 3, 14, 15, 0, tzinfo=timezone.utc)
            exp.description = desc
            exp.amount = Decimal("100")
            exp.category = None
            expenses.append(exp)

        result = format_expense_list(expenses)

        for desc in descriptions:
            assert desc in result
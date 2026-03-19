"""
Tests exhaustivos para ExpenseParser.
Coverage objetivo: 100%
"""
from decimal import Decimal
from unittest import mock

import pytest

# Asegúrate de que la ruta de importación sea la correcta en tu proyecto
from services.parser.expense_parser import ExpenseParser


@pytest.fixture
def parser():
    """Fixture del parser."""
    return ExpenseParser()


# ============================================
# CASOS BÁSICOS
# ============================================

class TestBasicCases:
    """Tests de casos básicos de parsing."""

    def test_amount_at_beginning(self, parser):
        result = parser.parse("2000 pizza")
        assert result["success"] is True
        assert result["amount"] == Decimal("2000")
        assert result["description"] == "pizza"
        assert result["error"] is None

    def test_amount_at_end(self, parser):
        result = parser.parse("pizza 2000")
        assert result["success"] is True
        assert result["amount"] == Decimal("2000")

    def test_only_amount_no_description(self, parser):
        result = parser.parse("2000")
        assert result["success"] is True
        assert result["amount"] == Decimal("2000")
        assert result["description"] == "Sin descripcion"

    def test_with_dollar_symbol_prefix(self, parser):
        result = parser.parse("$2000 almuerzo")
        assert result["success"] is True
        assert result["amount"] == Decimal("2000")
        assert result["description"] == "almuerzo"

    def test_without_dollar_symbol(self, parser):
        result = parser.parse("Uber 1500")
        assert result["success"] is True
        assert result["amount"] == Decimal("1500")
        assert result["description"] == "Uber"


# ============================================
# DECIMALES Y SEPARADORES
# ============================================

class TestDecimalsAndSeparators:
    """Tests de manejo de decimales y separadores de miles."""

    def test_comma_decimal_argentine_format(self, parser):
        result = parser.parse("Café 15,50")
        assert result["amount"] == Decimal("15.50")

    def test_dot_decimal_international_format(self, parser):
        result = parser.parse("Café 15.50")
        assert result["amount"] == Decimal("15.50")

    def test_full_argentine_notation(self, parser):
        result = parser.parse("Supermercado $1.500,50")
        assert result["amount"] == Decimal("1500.50")

    def test_dot_as_thousands_separator(self, parser):
        result = parser.parse("$5.000 cena")
        assert result["amount"] == Decimal("5000")

    def test_multiple_thousands_separators(self, parser):
        result = parser.parse("Auto usado $1.500.000")
        assert result["amount"] == Decimal("1500000")


# ============================================
# EDGE CASES & FORMATOS ESPECIALES
# ============================================

class TestEdgeCases:
    """Tests de casos extremos y formatos raros."""

    def test_emoji_in_message(self, parser):
        result = parser.parse("Pizza 🍕 2000 🎉")
        assert result["amount"] == Decimal("2000")
        assert "Pizza" in result["description"]

    def test_extra_spaces(self, parser):
        result = parser.parse("   Pizza   2000   ")
        assert result["amount"] == Decimal("2000")
        assert result["description"] == "Pizza"

    def test_number_inside_word(self, parser):
        # El regex captura números pegados a palabras si no son letras
        result = parser.parse("pizza2000")
        assert result["amount"] == Decimal("2000")

    def test_dollar_at_end(self, parser):
        result = parser.parse("500$ helado")
        assert result["amount"] == Decimal("500")

    def test_amount_in_middle(self, parser):
        result = parser.parse("Compré café $500 en la esquina")
        assert result["amount"] == Decimal("500")
        assert result["description"] == "Compré café en la esquina"


# ============================================
# PRIORIDAD Y WARNINGS
# ============================================

class TestSelectionPriorityAndWarnings:
    """Tests de prioridad de selección y advertencias."""

    def test_dollar_wins_over_larger_number(self, parser):
        result = parser.parse("$20 pizza 2000")
        assert result["amount"] == Decimal("20")
        assert result["warning"] is None # $ elimina la ambigüedad

    def test_multiple_amounts_with_dollar_warns(self, parser):
        result = parser.parse("$50 de $100")
        assert result["amount"] == Decimal("50")
        assert "símbolo $" in result["warning"]

    def test_decimal_wins_over_integer(self, parser):
        result = parser.parse("100 o 15,50")
        assert result["amount"] == Decimal("15.50")
        assert result["warning"] is None

    def test_largest_number_wins_by_default(self, parser):
        result = parser.parse("20 empanadas 1500")
        assert result["amount"] == Decimal("1500")
        assert "mayor" in result["warning"]


# ============================================
# CASOS DE ERROR Y MANEJO DE EXCEPCIONES
# ============================================

class TestErrorCases:
    """Tests de fallos esperados."""

    def test_no_amount_only_text(self, parser):
        result = parser.parse("compré pizza")
        assert result["success"] is False
        assert "monto" in result["error"].lower()

    def test_negative_amount_fails_validation(self, parser):
        """El regex captura el negativo, pero la validación <= 0 lo bloquea."""
        result = parser.parse("-500 pizza")
        assert result["success"] is False
        assert "mayor a 0" in result["error"]

    def test_zero_amount(self, parser):
        result = parser.parse("0 pizza")
        assert result["success"] is False
        assert "mayor a 0" in result["error"]

    def test_empty_string(self, parser):
        result = parser.parse("   ")
        assert result["success"] is False
        assert "vacío" in result["error"]

    def test_only_symbols(self, parser):
        result = parser.parse("$$$ @#%^&*()")
        assert result["success"] is False
        assert "texto válido" in result["error"] or "monto" in result["error"]

    def test_parse_to_decimal_value_error_is_caught(self, parser):
        """Simulamos que el parseo interno falla para verificar que no crashee la app."""
        with mock.patch.object(parser, '_parse_to_decimal', side_effect=ValueError("Formato corrupto")):
            result = parser.parse("2000 pizza")
            assert result["success"] is False
            assert "Error al parsear el monto" in result["error"]


# ============================================
# TEST DIRECTO DE LÓGICA INTERNA (_parse_to_decimal)
# ============================================

class TestInternalParseToDecimal:
    """Validamos el motor de conversión a Decimal al 100%."""

    @pytest.mark.parametrize("input_str, expected", [
        ("1500", Decimal("1500")),
        ("-1500", Decimal("-1500")),
        ("1500,50", Decimal("1500.50")),
        ("1500.50", Decimal("1500.50")),
        ("1.500", Decimal("1500")),
        ("1.500,50", Decimal("1500.50")),
        ("-1.500,50", Decimal("-1500.50")),
        ("10.000.000,99", Decimal("10000000.99")),
    ])
    def test_various_formats(self, parser, input_str, expected):
        assert parser._parse_to_decimal(input_str) == expected
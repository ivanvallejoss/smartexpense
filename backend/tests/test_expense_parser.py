"""
Tests exhaustivos para ExpenseParser.

Coverage objetivo: >95%
"""
from decimal import Decimal

import pytest

from apps.parsers.expense_parser import ExpenseParser


@pytest.fixture
def parser():
    """Fixture del parser."""
    return ExpenseParser()


# ============================================
# CASOS BÁSICOS (5 tests)
# ============================================


class TestBasicCases:
    """Tests de casos básicos de parsing."""

    def test_amount_at_beginning(self, parser):
        """Monto al inicio del mensaje."""
        result = parser.parse("2000 pizza")

        assert result["success"] is True
        assert result["amount"] == Decimal("2000")
        assert result["description"] == "pizza"
        assert result["error"] is None

    def test_amount_at_end(self, parser):
        """Monto al final del mensaje."""
        result = parser.parse("pizza 2000")

        assert result["success"] is True
        assert result["amount"] == Decimal("2000")
        assert result["description"] == "pizza"

    def test_only_amount_no_description(self, parser):
        """Solo monto, sin descripción."""
        result = parser.parse("2000")

        assert result["success"] is True
        assert result["amount"] == Decimal("2000")
        assert result["description"] == "Sin descripcion"

    def test_with_dollar_symbol_prefix(self, parser):
        """Con símbolo $ al inicio."""
        result = parser.parse("$2000 almuerzo")

        assert result["success"] is True
        assert result["amount"] == Decimal("2000")
        assert result["description"] == "almuerzo"

    def test_without_dollar_symbol(self, parser):
        """Sin símbolo $."""
        result = parser.parse("Uber 1500")

        assert result["success"] is True
        assert result["amount"] == Decimal("1500")
        assert result["description"] == "Uber"


# ============================================
# DECIMALES (5 tests)
# ============================================


class TestDecimals:
    """Tests de manejo de decimales."""

    def test_comma_decimal_argentine_format(self, parser):
        """Coma como decimal (formato argentino)."""
        result = parser.parse("Café 15,50")

        assert result["success"] is True
        assert result["amount"] == Decimal("15.50")
        assert result["description"] == "Café"

    def test_dot_decimal_international_format(self, parser):
        """Punto como decimal (formato internacional)."""
        result = parser.parse("Café 15.50")

        assert result["success"] is True
        assert result["amount"] == Decimal("15.50")
        assert result["description"] == "Café"

    def test_full_argentine_notation(self, parser):
        """Notación argentina completa: punto miles, coma decimal."""
        result = parser.parse("Supermercado $1.500,50")

        assert result["success"] is True
        assert result["amount"] == Decimal("1500.50")
        assert result["description"] == "Supermercado"

    def test_no_decimals_integer(self, parser):
        """Sin decimales, número entero."""
        result = parser.parse("Cena 5000")

        assert result["success"] is True
        assert result["amount"] == Decimal("5000")
        assert result["description"] == "Cena"

    def test_one_decimal_digit(self, parser):
        """Un solo dígito decimal."""
        result = parser.parse("Propina 100,5")

        assert result["success"] is True
        assert result["amount"] == Decimal("100.5")
        assert result["description"] == "Propina"


# ============================================
# SEPARADORES DE MILES (3 tests)
# ============================================


class TestThousandsSeparators:
    """Tests de separadores de miles."""

    def test_dot_as_thousands_separator(self, parser):
        """Punto como separador de miles."""
        result = parser.parse("$5.000 cena")

        assert result["success"] is True
        assert result["amount"] == Decimal("5000")
        assert result["description"] == "cena"

    def test_no_thousands_separator(self, parser):
        """Sin separador de miles."""
        result = parser.parse("5000 cena")

        assert result["success"] is True
        assert result["amount"] == Decimal("5000")

    def test_multiple_thousands_separators(self, parser):
        """Múltiples separadores de miles."""
        result = parser.parse("Auto usado $1.500.000")

        assert result["success"] is True
        assert result["amount"] == Decimal("1500000")
        assert result["description"] == "Auto usado"


# ============================================
# EDGE CASES (5+ tests)
# ============================================


class TestEdgeCases:
    """Tests de casos extremos y complejos."""

    def test_multiple_numbers_choose_largest(self, parser):
        """Múltiples números, elegir el más grande."""
        result = parser.parse("Compré 3 pizzas por 2000")

        assert result["success"] is True
        assert result["amount"] == Decimal("2000")
        assert "pizzas" in result["description"]
        assert result["warning"] is not None  # Debe advertir múltiples números

    def test_small_and_large_number_choose_large(self, parser):
        """Número pequeño y grande, elegir el grande."""
        result = parser.parse("15 empanadas 1500")

        assert result["success"] is True
        assert result["amount"] == Decimal("1500")
        assert "empanadas" in result["description"]

    def test_emoji_in_message(self, parser):
        """Emojis en el mensaje (deben ignorarse)."""
        result = parser.parse("Pizza 🍕 2000 🎉")

        assert result["success"] is True
        assert result["amount"] == Decimal("2000")
        assert "Pizza" in result["description"]

    def test_extra_spaces(self, parser):
        """Espacios extras en el mensaje."""
        result = parser.parse(" Pizza 2000 ")

        assert result["success"] is True
        assert result["amount"] == Decimal("2000")
        assert result["description"] == "Pizza"

    def test_very_long_description(self, parser):
        """Descripción muy larga."""
        long_desc = "Compré comida en el supermercado incluyendo verduras frutas y carnes"
        result = parser.parse(f"{long_desc} 5000")

        assert result["success"] is True
        assert result["amount"] == Decimal("5000")
        assert len(result["description"]) > 20

    def test_number_inside_word(self, parser):
        """Número pegado a palabra."""
        result = parser.parse("pizza2000")

        assert result["success"] is True
        assert result["amount"] == Decimal("2000")


# ============================================
# CASOS DE ERROR (7 tests)
# ============================================


class TestErrorCases:
    """Tests de casos que deben fallar."""

    def test_no_amount_only_text(self, parser):
        """Sin monto, solo texto."""
        result = parser.parse("compré pizza")

        assert result["success"] is False
        assert result["error"] is not None
        assert "monto" in result["error"].lower()

    def test_negative_amount(self, parser):
        """Monto negativo debe fallar."""
        result = parser.parse("-500 pizza")

        # El regex no matchea negativos, así que no encuentra monto
        assert result["success"] is False

    def test_zero_amount(self, parser):
        """Monto cero debe fallar."""
        result = parser.parse("0 pizza")

        assert result["success"] is False
        assert "mayor a 0" in result["error"]

    def test_empty_string(self, parser):
        """String vacío."""
        result = parser.parse("")

        assert result["success"] is False
        assert "vacío" in result["error"]

    def test_only_spaces(self, parser):
        """Solo espacios."""
        result = parser.parse(" ")

        assert result["success"] is False
        assert "vacío" in result["error"]

    def test_only_symbols(self, parser):
        """Solo símbolos $$$."""
        result = parser.parse("$$$")

        assert result["success"] is False
        assert result["error"] is not None

    def test_special_characters_only(self, parser):
        """Solo caracteres especiales raros."""
        result = parser.parse("@#%^&*()")

        assert result["success"] is False


# ============================================
# WARNINGS (3 tests)
# ============================================


class TestWarnings:
    """Tests de casos con advertencias."""

    def test_multiple_amounts_with_dollar_warns(self, parser):
        """Múltiples montos con $ genera warning."""
        result = parser.parse("$50 de $100")

        assert result["success"] is True
        assert result["amount"] == Decimal("50")  # Usa el primero
        assert result["warning"] is not None
        assert "símbolo $" in result["warning"]
        assert "primero" in result["warning"]

    def test_multiple_numbers_with_decimals_warns(self, parser):
        """Múltiples números con decimales genera warning."""
        result = parser.parse("15,50 o 20,75")

        assert result["success"] is True
        assert result["warning"] is not None
        assert "decimales" in result["warning"]

    def test_multiple_numbers_without_symbol_warns(self, parser):
        """Múltiples números sin $ genera warning."""
        result = parser.parse("100 o 200")

        assert result["success"] is True
        assert result["warning"] is not None
        assert "números" in result["warning"]


# ============================================
# FORMATOS ESPECIALES (5+ tests)
# ============================================


class TestSpecialFormats:
    """Tests de formatos especiales."""

    def test_dollar_at_end(self, parser):
        """Símbolo $ al final."""
        result = parser.parse("500$ helado")

        assert result["success"] is True
        assert result["amount"] == Decimal("500")
        assert result["description"] == "helado"

    def test_amount_in_middle(self, parser):
        """Monto en el medio del mensaje."""
        result = parser.parse("Compré café $500 en la esquina")

        assert result["success"] is True
        assert result["amount"] == Decimal("500")
        assert "café" in result["description"]
        assert "esquina" in result["description"]

    def test_mixed_format_amount(self, parser):
        """Formato mixto de monto."""
        result = parser.parse("Cena $5.500,50")

        assert result["success"] is True
        assert result["amount"] == Decimal("5500.50")
        assert result["description"] == "Cena"

    def test_small_decimal_amount(self, parser):
        """Monto pequeño con decimales (debe reconocerse)."""
        result = parser.parse("Chicle 2,50")

        assert result["success"] is True
        assert result["amount"] == Decimal("2.50")
        assert result["description"] == "Chicle"

    def test_real_world_argentine_message(self, parser):
        """Mensaje real argentino típico."""
        result = parser.parse("Compré facturas $1.250,50 en la panadería")

        assert result["success"] is True
        assert result["amount"] == Decimal("1250.50")
        assert "facturas" in result["description"]
        assert "panadería" in result["description"]

    def test_uber_like_message(self, parser):
        """Mensaje tipo Uber."""
        result = parser.parse("Uber a casa 1.500")

        assert result["success"] is True
        assert result["amount"] == Decimal("1500")
        assert "Uber" in result["description"]


# ============================================
# PRIORIDAD DE SELECCIÓN (3 tests)
# ============================================


class TestSelectionPriority:
    """Tests de prioridad de selección de monto."""

    def test_dollar_wins_over_larger_number(self, parser):
        """$ gana sobre número más grande."""
        result = parser.parse("$20 pizza 2000")

        assert result["success"] is True
        assert result["amount"] == Decimal("20")
        # El $ tiene prioridad aunque 2000 sea mayor

    def test_decimal_wins_over_integer(self, parser):
        """Número con decimales gana sobre entero más grande."""
        result = parser.parse("100 o 15,50")

        assert result["success"] is True
        # 15,50 tiene formato de dinero (decimales), debe ganar
        assert result["amount"] == Decimal("15.50")

    def test_largest_number_wins_by_default(self, parser):
        """El número más grande gana por defecto."""
        result = parser.parse("20 empanadas 1500")

        assert result["success"] is True
        assert result["amount"] == Decimal("1500")

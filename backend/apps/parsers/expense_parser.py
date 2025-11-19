"""
Parser de expenses desde mensajes en lenguaje natural.

Soporta múltiples formatos argentinos:
- "Pizza 2000" o "2000 pizza"
- Con/sin símbolo $
- Decimales con punto o coma
- Notación argentina (punto como separador de miles)
"""
import re
from decimal import Decimal
from typing import Dict, List


class ExpenseParser:
    """
    Parser robusto para extraer monto y descripción de mensajes de gastos.

    Estrategia de selección de monto (en orden de prioridad):
    1. Presencia de símbolo $ (máxima confianza)
    2. Formato de dinero (decimales, separadores)
    3. Magnitud del número (el más grande)

    Ejemplos:
        >>> parser = ExpenseParser()
        >>> parser.parse("Pizza 2000")
        {'amount': Decimal('2000'), 'description': 'Pizza', 'success': True, ...}

        >>> parser.parse("$1.500,50 supermercado")
        {'amount': Decimal('1500.50'), 'description': 'supermercado', 'success': True, ...}
    """

    # Regex para detectar números con diferentes formatos
    # IMPORTANTE: El orden importa - los patrones más específicos primero
    AMOUNT_PATTERN = re.compile(
        r"""
        (?P<full>                           # Capturar el match completo
            \$?                             # Símbolo $ opcional al inicio
            \s*                             # Espacios opcionales
            (?P<sign>-)?                    # Signo negativo opcional (NUEVO)
            \s*                             # Espacios opcionales después del signo
            (?P<number>                     # Grupo del número
                \d{1,3}(?:\.\d{3})+(?:,\d{1,2})?    # Formato argentino con miles: 1.500 o 1.500,50
                |
                \d+(?:,\d{1,2})                      # Entero con coma decimal: 1500,50
                |
                \d+(?:\.\d{1,2})                     # Entero con punto decimal: 1500.50
                |
                \d+                                  # Solo enteros sin formato: 1500, 2000, etc
            )
            \s*                             # Espacios opcionales
            \$?                             # Símbolo $ opcional al final
        )
        """,
        re.VERBOSE,
    )

    # Emojis comunes a remover
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # símbolos & pictogramas
        "\U0001F680-\U0001F6FF"  # transporte & símbolos
        "\U0001F1E0-\U0001F1FF"  # banderas
        "]+",
        flags=re.UNICODE,
    )

    def parse(self, text: str) -> Dict:
        """
        Parsea un mensaje y extrae monto y descripción.

        Args:
            text: Mensaje del usuario (ej: "Pizza 2000", "$500 café")

        Returns:
            dict con:
                - amount (Decimal): Monto extraído
                - description (str): Descripción del gasto
                - success (bool): Si el parsing fue exitoso
                - error (str|None): Mensaje de error si falló
                - warning (str|None): Advertencias sobre ambigüedades

        Raises:
            No lanza excepciones, retorna success=False en caso de error.
        """
        # Inicializar response
        result = {"amount": None, "description": "", "success": False, "error": None, "warning": None}

        # Validaciones básicas
        if not text or not text.strip():
            result["error"] = "El mensaje está vacío"
            return result

        # Normalizar texto
        normalized = self._normalize_text(text)

        if not normalized:
            result["error"] = "El mensaje no contiene texto válido"
            return result

        # Extraer candidatos a monto
        candidates = self._extract_amount_candidates(normalized)

        if not candidates:
            result["error"] = "No se encontró ningún monto en el mensaje"
            return result

        # Seleccionar el monto correcto
        selected, warning = self._select_amount(candidates)

        if warning:
            result["warning"] = warning

        # Parsear a Decimal
        try:
            amount = self._parse_to_decimal(selected["raw_number"])
        except ValueError as e:
            result["error"] = f"Error al parsear el monto: {e}"
            return result

        # Validar monto
        if amount <= 0:
            result["error"] = f"El monto debe ser mayor a 0 (recibido: {amount})"
            return result

        # Extraer descripción
        description = self._extract_description(normalized, selected)

        # Success!
        result["amount"] = amount
        result["description"] = description
        result["success"] = True

        return result

    def _normalize_text(self, text: str) -> str:
        """
        Normaliza el texto de entrada.

        - Strip espacios
        - Remover emojis
        - Normalizar múltiples espacios
        """
        # Remover emojis
        text = self.EMOJI_PATTERN.sub("", text)

        # Strip y normalizar espacios
        text = " ".join(text.split())

        return text.strip()

    def _extract_amount_candidates(self, text: str) -> List[Dict]:
        """
        Extrae todos los números que podrían ser montos.

        Returns:
            Lista de dicts con:
                - raw: string original del match
                - raw_number: solo el número sin símbolos
                - position: posición en el texto
                - has_symbol: si tiene $
                - has_decimals: si tiene decimales
                - magnitude: valor numérico aproximado
        """
        candidates = []

        for match in self.AMOUNT_PATTERN.finditer(text):
            raw = match.group("full").strip()
            number = match.group("number")
            sign = match.group("sign")  # NUEVO: capturar signo

            # Si tiene signo negativo, agregarlo al número
            if sign:
                number = f"-{number}"

            # Detectar características
            has_symbol = "$" in raw

            # Detectar decimales de forma más precisa
            # Caso 1: coma seguida de 1-2 dígitos (formato argentino)
            has_comma_decimal = "," in number and len(number.split(",")[-1]) <= 2

            # Caso 2: punto seguido de 1-2 dígitos (formato internacional)
            # Pero NO si tiene múltiples puntos (separadores de miles)
            has_dot_decimal = "." in number and number.count(".") == 1 and len(number.split(".")[-1]) <= 2

            has_decimals = has_comma_decimal or has_dot_decimal

            # Calcular magnitud aproximada para comparación
            try:
                magnitude = self._parse_to_decimal(number)
            except ValueError as e:
                print(f"An error has ocurred, {e}")

            candidates.append({"raw": raw, "raw_number": number, "position": match.start(), "has_symbol": has_symbol, "has_decimals": has_decimals, "magnitude": magnitude})

        return candidates

    def _select_amount(self, candidates: List[Dict]) -> tuple:
        """
        Selecciona el candidato correcto basándose en reglas.

        Prioridad:
        1. Si hay $ → usar ese
        2. Si hay formato de dinero (decimales) → usar ese
        3. Usar el de mayor magnitud

        Returns:
            (candidato_seleccionado, warning_message)
        """
        warning = None

        # Filtrar candidatos con $
        with_symbol = [c for c in candidates if c["has_symbol"]]

        # CASO 1: Hay números con $
        if with_symbol:
            if len(with_symbol) > 1:
                warning = f"Se encontraron {len(with_symbol)} montos con símbolo $. " f"Se usó el primero: {with_symbol[0]['raw']}"
            return with_symbol[0], warning

        # CASO 2: Buscar el que tiene formato de dinero (decimales)
        with_decimals = [c for c in candidates if c["has_decimals"]]

        if with_decimals:
            # Si hay múltiples con decimales, usar el de mayor magnitud
            selected = max(with_decimals, key=lambda c: c["magnitude"])

            if len(with_decimals) > 1:
                warning = f"Se encontraron {len(with_decimals)} números con decimales. " f"Se usó el mayor: {selected['raw']}"

            return selected, warning

        # CASO 3: Usar el de mayor magnitud
        # Filtrar números muy pequeños que probablemente sean cantidades (< 20)
        likely_amounts = [c for c in candidates if c["magnitude"] >= 20]

        if not likely_amounts:
            # Si todos son <20, usar el mayor de todos igual
            likely_amounts = candidates

        selected = max(likely_amounts, key=lambda c: c["magnitude"])

        if len(candidates) > 1:
            warning = f"Se encontraron {len(candidates)} números. " f"Se usó el mayor: {selected['raw']}"

        return selected, warning

    def _parse_to_decimal(self, number_str: str) -> Decimal:
        """
        Convierte string a Decimal manejando formato argentino.

        Formatos soportados:
        - "1500" → 1500
        - "-1500" → -1500 (negativo)
        - "1500,50" → 1500.50
        - "1500.50" → 1500.50
        - "1.500" → 1500 (separador de miles)
        - "1.500,50" → 1500.50 (notación argentina)
        - "-1.500,50" → -1500.50 (negativo argentino)

        Args:
            number_str: String con el número

        Returns:
            Decimal parseado

        Raises:
            InvalidOperation: Si no se puede parsear
        """
        # Remover espacios
        number_str = number_str.strip()

        # Detectar y guardar signo negativo
        is_negative = number_str.startswith("-")
        if is_negative:
            number_str = number_str[1:]  # Remover signo temporalmente

        # Detectar formato argentino: "1.500,50"
        if "." in number_str and "," in number_str:
            # Punto es separador de miles, coma es decimal
            number_str = number_str.replace(".", "").replace(",", ".")

        # Detectar si punto es separador de miles: "1.500" (sin coma)
        elif "." in number_str and "," not in number_str:
            # Si hay punto y es parte de separador de miles
            # Ej: "1.500" (mil quinientos) vs "15.50" (quince con cincuenta)
            parts = number_str.split(".")

            # Si la parte después del punto tiene 3 dígitos, es separador de miles
            if all(len(part) == 3 for part in parts[1:]):
                number_str = number_str.replace(".", "")
            # Si tiene 1-2 dígitos, es decimal
            # No hacer nada, ya está en formato correcto

        # Detectar coma como decimal: "1500,50"
        elif "," in number_str:
            number_str = number_str.replace(",", ".")

        # Convertir a Decimal
        result = Decimal(number_str)

        # Aplicar signo negativo si corresponde
        if is_negative:
            result = -result

        return result

    def _extract_description(self, text: str, selected_candidate: Dict) -> str:
        """
        Extrae la descripción removiendo el monto del texto.

        Args:
            text: Texto normalizado completo
            selected_candidate: Candidato seleccionado como monto

        Returns:
            Descripción limpia
        """
        # Remover el monto del texto
        description = text.replace(selected_candidate["raw"], "", 1).strip()

        # Limpiar símbolos $ sobrantes
        description = description.replace("$", "").strip()

        # Si quedó vacío, poner descripción default
        if not description:
            description = "Sin descripcion"

        return description

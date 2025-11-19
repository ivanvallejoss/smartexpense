# Expense Parser

Parser robusto para extraer monto y descripción de mensajes en lenguaje natural (español argentino).

## 📋 Casos Soportados

### ✅ Formatos básicos
```
"Pizza 2000"           → amount: 2000, description: "Pizza"
"2000 pizza"           → amount: 2000, description: "pizza"
"$2000 almuerzo"       → amount: 2000, description: "almuerzo"
"Uber 1500"            → amount: 1500, description: "Uber"
```

### ✅ Decimales (múltiples formatos)
```
"Café 15,50"           → amount: 15.50  (coma decimal - formato argentino)
"Café 15.50"           → amount: 15.50  (punto decimal - internacional)
"$1.500,50 super"      → amount: 1500.50 (notación argentina completa)
```

### ✅ Separadores de miles
```
"$5.000 cena"          → amount: 5000 (punto como separador de miles)
"1.500.000 auto"       → amount: 1500000 (múltiples separadores)
```

### ✅ Casos complejos
```
"Compré 3 pizzas 2000" → amount: 2000 (elige el número más grande)
"15 empanadas 1500"    → amount: 1500 (elige el número más grande)
"$20 pizza 2000"       → amount: 20 ($ tiene prioridad)
"Pizza 🍕 2000"        → amount: 2000 (ignora emojis)
```

---

## 🧠 Lógica de Selección de Monto

Cuando hay múltiples números, el parser usa esta **prioridad**:

### 1. Presencia de símbolo `$` (máxima confianza)
```python
"$500 o 1000"  → Elige 500 (tiene $)
```

### 2. Formato de dinero (decimales)
```python
"100 o 15,50"  → Elige 100 (el mayor, pero 15,50 tiene decimales)
# Si ambos tienen decimales, elige el mayor
```

### 3. Magnitud (el más grande)
```python
"20 empanadas 1500"  → Elige 1500 (mayor)
"3 pizzas 2000"      → Elige 2000 (mayor)
```

### 4. Números pequeños (<20) probablemente son cantidades
```python
"15 empanadas 1500"  → 15 es cantidad, 1500 es monto
```

---

## ⚠️ Warnings y Ambigüedades

El parser genera **warnings** cuando detecta ambigüedad:

```python
result = parser.parse("$50 de $100")
# result['warning'] = "Se encontraron 2 montos con símbolo $. Se usó el primero: $50"
# result['amount'] = 50
```

**Principio:** Ser explícito con el usuario sobre decisiones ambiguas.

---

## ❌ Casos que Fallan

```python
"compré pizza"         → error: "No se encontró ningún monto"
"-500 pizza"           → error: "El monto debe ser mayor a 0"
"0 pizza"              → error: "El monto debe ser mayor a 0"
""                     → error: "El mensaje está vacío"
"   "                  → error: "El mensaje está vacío"
```

---

## 🔧 Uso

```python
from apps.parsers.expense_parser import ExpenseParser

parser = ExpenseParser()

result = parser.parse("Pizza $2.500,50")

# Estructura del resultado:
{
    'amount': Decimal('2500.50'),
    'description': 'Pizza',
    'success': True,
    'error': None,
    'warning': None
}
```

### Manejar errores:

```python
result = parser.parse(user_message)

if not result['success']:
    # Mostrar error al usuario
    print(f"Error: {result['error']}")
else:
    # Crear expense
    amount = result['amount']
    description = result['description']

    # Opcionalmente mostrar warning
    if result['warning']:
        print(f"Nota: {result['warning']}")
```

---

## 🧪 Testing

```bash
# Correr tests
pytest backend/apps/parsers/tests/ -v

# Con coverage
pytest backend/apps/parsers/tests/ --cov=backend/apps/parsers --cov-report=term-missing

# Coverage objetivo: >95%
```

---

## 🚀 Próximas Mejoras

- [ ] **ML/NLP:** Auto-categorización basada en descripción
- [ ] **Fuzzy matching:** "piza" → "pizza"
- [ ] **Fechas relativas:** "ayer", "la semana pasada"
- [ ] **Múltiples gastos:** "2 pizzas $500 c/u"
- [ ] **Divisas:** USD, EUR, etc.

---

## 📚 Recursos

- Tests exhaustivos: `backend/apps/parsers/tests/test_expense_parser.py`
- Script manual: `backend/apps/parsers/manual_test.py`
- Documentación regex: Python `re` module
READMEEOF
cat /tmp/parsers_README.md
Salida

# Expense Parser

Parser robusto para extraer monto y descripción de mensajes en lenguaje natural (español argentino).

## 📋 Casos Soportados

### ✅ Formatos básicos
```
"Pizza 2000"           → amount: 2000, description: "Pizza"
"2000 pizza"           → amount: 2000, description: "pizza"
"$2000 almuerzo"       → amount: 2000, description: "almuerzo"
"Uber 1500"            → amount: 1500, description: "Uber"
```

### ✅ Decimales (múltiples formatos)
```
"Café 15,50"           → amount: 15.50  (coma decimal - formato argentino)
"Café 15.50"           → amount: 15.50  (punto decimal - internacional)
"$1.500,50 super"      → amount: 1500.50 (notación argentina completa)
```

### ✅ Separadores de miles
```
"$5.000 cena"          → amount: 5000 (punto como separador de miles)
"1.500.000 auto"       → amount: 1500000 (múltiples separadores)
```

### ✅ Casos complejos
```
"Compré 3 pizzas 2000" → amount: 2000 (elige el número más grande)
"15 empanadas 1500"    → amount: 1500 (elige el número más grande)
"$20 pizza 2000"       → amount: 20 ($ tiene prioridad)
"Pizza 🍕 2000"        → amount: 2000 (ignora emojis)
```

---

## 🧠 Lógica de Selección de Monto

Cuando hay múltiples números, el parser usa esta **prioridad**:

### 1. Presencia de símbolo `$` (máxima confianza)
```python
"$500 o 1000"  → Elige 500 (tiene $)
```

### 2. Formato de dinero (decimales)
```python
"100 o 15,50"  → Elige 100 (el mayor, pero 15,50 tiene decimales)
# Si ambos tienen decimales, elige el mayor
```

### 3. Magnitud (el más grande)
```python
"20 empanadas 1500"  → Elige 1500 (mayor)
"3 pizzas 2000"      → Elige 2000 (mayor)
```

### 4. Números pequeños (<20) probablemente son cantidades
```python
"15 empanadas 1500"  → 15 es cantidad, 1500 es monto
```

---

## ⚠️ Warnings y Ambigüedades

El parser genera **warnings** cuando detecta ambigüedad:

```python
result = parser.parse("$50 de $100")
# result['warning'] = "Se encontraron 2 montos con símbolo $. Se usó el primero: $50"
# result['amount'] = 50
```

**Principio:** Ser explícito con el usuario sobre decisiones ambiguas.

---

## ❌ Casos que Fallan

```python
"compré pizza"         → error: "No se encontró ningún monto"
"-500 pizza"           → error: "El monto debe ser mayor a 0"
"0 pizza"              → error: "El monto debe ser mayor a 0"
""                     → error: "El mensaje está vacío"
"   "                  → error: "El mensaje está vacío"
```

---

## 🔧 Uso

```python
from apps.parsers.expense_parser import ExpenseParser

parser = ExpenseParser()

result = parser.parse("Pizza $2.500,50")

# Estructura del resultado:
{
    'amount': Decimal('2500.50'),
    'description': 'Pizza',
    'success': True,
    'error': None,
    'warning': None
}
```

### Manejar errores:

```python
result = parser.parse(user_message)

if not result['success']:
    # Mostrar error al usuario
    print(f"Error: {result['error']}")
else:
    # Crear expense
    amount = result['amount']
    description = result['description']

    # Opcionalmente mostrar warning
    if result['warning']:
        print(f"Nota: {result['warning']}")
```

---

## 🧪 Testing

```bash
# Correr tests
pytest backend/apps/parsers/tests/ -v

# Con coverage
pytest backend/apps/parsers/tests/ --cov=backend/apps/parsers --cov-report=term-missing

# Coverage objetivo: >95%
```

---

## 🚀 Próximas Mejoras

- [ ] **ML/NLP:** Auto-categorización basada en descripción
- [ ] **Fuzzy matching:** "piza" → "pizza"
- [ ] **Fechas relativas:** "ayer", "la semana pasada"
- [ ] **Múltiples gastos:** "2 pizzas $500 c/u"
- [ ] **Divisas:** USD, EUR, etc.

---

## 📚 Recursos

- Tests exhaustivos: `backend/apps/parsers/tests/test_expense_parser.py`
- Script manual: `backend/apps/parsers/manual_test.py`
- Documentación regex: Python `re` module

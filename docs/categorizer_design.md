# Categorizador — Diseño de Arquitectura

**Estado:** propuesto
**Alcance:** rediseño del módulo de categorización (`services/ml/`) con enfoque
determinista: pipeline de scoring, representación de keywords, índice de
historial, política de confianza, y los datos necesarios para medir precisión.
**Fuera de alcance:** cualquier incorporación de ML (modelos estadísticos,
embeddings, LLMs). Queda condicionada a una revisión profunda futura, con su
propio ADR. Este diseño no sienta bases para ML: cada decisión se justifica
por sus méritos deterministas.

Decisión formal en
[decision_records/categorizer_scoring_pipeline.md](decision_records/categorizer_scoring_pipeline.md).

---

## 1. Diagnóstico

### 1.1 Flujo actual

```
event.text
  → ExpenseParser.parse()                    (services/parser/expense_parser.py)
  → get_category_suggestion()                (services/ml/helper.py, sync_to_async)
      → ExpenseCategorizer.suggest()         (services/ml/categorizer.py)
          1. historial del usuario           (últimos 100 gastos, re-normalizados)
          2. keywords del usuario            (dict plano, first-match-wins)
          3. DEFAULT_CATEGORY_KEYWORDS       (sugiere nombre; helper auto-crea)
  → handle_message ramifica por floats crudos (apps/bot/handlers/handlers.py:258-291)
      >= 0.8 auto-categoriza | >= 0.5 pide confirmación | else picker
```

El categorizador es una cascada de prioridades donde **la primera coincidencia
gana** y cada nivel descarta al anterior por completo.

### 1.2 Defectos verificados

| # | Defecto | Ubicación | Efecto observable |
| --- | --- | --- | --- |
| D1 | Substring bidireccional `keyword in word or word in keyword` | `categorizer.py:259`, `:358` | Falsos positivos con confianza 0.6: "gas" ⊂ "gaseosa" → Transporte para una bebida; "dia" ⊂ "diario" |
| D2 | No-determinismo: itera un `set` de palabras (`:245`) y un dict de keywords (`:255`) con first-match-wins | `_check_keywords` | El mismo mensaje puede sugerir categorías distintas entre ejecuciones |
| D3 | Colisión de keywords: `self._keyword_map[keyword] = category` — la última gana, en silencio | `categorizer.py:159` | "gas" está en Transporte y Servicios, "expensas" en Servicios y Hogar (`default_keywords.py`); la resolución es arbitraria |
| D4 | La banda 0.5–0.89 del historial se computa y se descarta: `_check_user_history` retorna el mejor match ≥ 0.5, pero `suggest()` solo lo acepta si ≥ 0.9 | `categorizer.py:177` vs `:223-233` | La señal más personalizada del sistema se tira y cae a keywords genéricos |
| D5 | Las categorías globales nunca aportan keywords: `_get_keyword_map` filtra `user=self.user` (`:149`); `_get_user_categories`, que sí carga globales, es código muerto | `categorizer.py:129-133` | El "Level 2/3" documentado en `architecture.md` no existe como está descrito |
| D6 | Feedback write-only: `record_feedback` escribe, nada lee; `get_accuracy_stats()` no tiene llamadores fuera de tests | `categorizer.py:271-335` | El feedback explícito es inerte; no hay visibilidad de precisión en producción |
| D7 | `raw_message` guarda la descripción parseada, no el texto original: el handler no lo pasa y `create_expense` hace fallback a `description` | `handlers.py:259-264` + `expenses.py:35-36` | El mensaje real del usuario se pierde al momento de la escritura; imposible auditar ni evaluar contra mensajes reales |
| D8 | O(100) re-normalización Python por mensaje: escanea los últimos 100 gastos normalizando cada descripción en cada `suggest()` | `categorizer.py:194-204` | Costo lineal en el camino de latencia del usuario, sin índice ni caché |
| D9 | `DIMINUTIVE_SUFFIXES` declarado y jamás aplicado; palabras < 3 chars descartadas; tokens alfanuméricos imposibles (`[a-z]+`) | `categorizer.py:49-62`, `:97` | "cafecito" ≠ "cafe" salvo keyword hardcodeado; "tv" nunca matchea |
| D10 | Umbrales duplicados: 0.8 vive en `helper.is_autocategorized` (código muerto) y en las ramas del handler; las bandas son floats crudos acoplados al adaptador de canal | `helper.py:45-60`, `handlers.py:258,272` | Cambiar la política de confianza exige tocar el handler de cada canal |
| D11 | `confidence` con semántica inconsistente: a veces un ratio de overlap crudo (0.5–1.0), a veces una constante (0.6, 0.8) | `categorizer.py` | El handler compara magnitudes que no son comparables entre sí |

### 1.3 El learning loop no cierra

`architecture.md` ("The learning loop") afirma que una corrección del usuario
ajusta la próxima sugerencia vía `CategorySuggestionFeedback`. Es cierto solo
indirectamente: el `Expense` corregido entra al historial y el Level 1 puede
encontrarlo. El registro de feedback explícito no participa de ninguna
decisión (D6), y por D4 un match de historial con overlap 0.5–0.89 pierde
contra un keyword genérico — exactamente el caso "el usuario corrigió Uber a
Trabajo" que el documento usa de ejemplo.

---

## 2. Arquitectura objetivo

### 2.1 Principio rector

Reemplazar la cascada first-match-wins por tres pasos separados:

1. **Generación de candidatos** — cada fuente (historial, keywords propios,
   keywords globales, fuzzy) emite candidatos con score y evidencia, sin
   descartar a las demás.
2. **Combinación determinista** — un ranker único combina los candidatos con
   pesos por fuente y un orden total de desempate.
3. **Política de confianza** — el score final se mapea a una banda de acción
   (`AUTO | CONFIRM | PICK`) en un único lugar.

Todo contenido en `services/ml/`, cumpliendo el mandato de `architecture.md`
("Service Layer Design"): los handlers no cambian de contrato.

### 2.2 Módulos

```
services/ml/
  normalization.py   # TextNormalizer versionado — única fuente de verdad
  types.py           # dataclasses + Protocols — contrato estable del pipeline
  generators/
    history.py       # candidatos desde UserTokenStat
    keywords.py      # candidatos desde CategoryKeyword (propios y globales)
    fuzzy.py         # rapidfuzz contra el léxico de keywords
  ranker.py          # combinación + orden total de desempate
  policy.py          # score → banda; los umbrales viven SOLO acá
  context.py         # UserContext: artefactos precomputados + caché Redis db2
  categorizer.py     # orquestador — fachada que conserva suggest()
  feedback.py        # record_feedback + tasas de aceptación por categoría
```

`types.py` y `policy.py` son los contratos que no se rompen. El resto es
implementación interna del paquete.

### 2.3 Contratos

```python
@dataclass(frozen=True)
class NormalizedText:
    original: str
    normalized: str
    tokens: tuple[str, ...]          # ordenados, sin stopwords, diminutivos aplicados
    normalizer_version: int          # un cambio de versión invalida índices

@dataclass(frozen=True)
class Evidence:
    source: str        # "history_exact" | "history_overlap" | "user_keyword"
                       # | "global_keyword" | "fuzzy"
    detail: str        # keyword matcheado / id de expense / token
    raw_score: float

@dataclass(frozen=True)
class Candidate:
    category_id: int | None          # None si la categoría default aún no existe
    category_name: str
    score: float                     # [0, 1] dentro del generador
    evidence: tuple[Evidence, ...]

class CandidateGenerator(Protocol):
    name: str
    weight: float                    # peso configurado de la fuente
    def generate(self, text: NormalizedText, ctx: UserContext) -> list[Candidate]: ...

class Band(Enum):
    AUTO = "auto"
    CONFIRM = "confirm"
    PICK = "pick"

@dataclass(frozen=True)
class RankedSuggestion:
    category_id: int | None
    category_name: str
    confidence: float                # score combinado final
    band: Band                       # los handlers consumen esto, nunca floats
    evidence: tuple[Evidence, ...]
    alternatives: tuple[Candidate, ...]   # top-N restante, para pickers acotados
    categorizer_version: str
```

`CategorySuggestion` actual queda como vista de compatibilidad para migrar
`helper.py` y los handlers gradualmente.

Una consecuencia de la interfaz — no un objetivo de este diseño — es que
cualquier fuente futura de candidatos entra como un `CandidateGenerator` más,
sin tocar ranker, policy ni handlers. Si alguna vez se evalúa ML, esa
evaluación tiene su propio ADR (ver §3, "Futuro condicionado").

### 2.4 Combinación y desempate

Por categoría candidata:

```
score(cat) = max(weight_g · score_g)  sobre los generadores que la proponen
           + 0.05 por cada generador adicional de acuerdo   (cap en 1.0)
score(cat) *= ajuste_feedback(cat)
```

- **Ajuste por feedback** — el feedback deja de ser write-only (D6):
  `ajuste = (aceptadas + 1) / (total + 2)` sobre los registros de
  `CategorySuggestionFeedback` del par (usuario, categoría). Es un conteo con
  suavizado, no un modelo: una categoría que el usuario corrige
  sistemáticamente pierde score; una que siempre acepta lo conserva.
- **Orden total de desempate** — elimina D2/D3:
  `(-score, orden_de_fuente[history < user_keyword < global_keyword < fuzzy],
  -aceptaciones_de_feedback, category_id)`, con epsilon `1e-9` para comparar
  floats. Mismo input ⇒ misma salida, siempre. Los keywords duplicados entre
  categorías dejan de colisionar en un dict: son candidatos concurrentes que
  el ranker resuelve con criterio explícito.

Pesos iniciales por fuente: `history 1.0 > user_keyword 0.9 >
global_keyword 0.7 > fuzzy 0.6`. Configurables sin deploy (settings/env).

Pseudocódigo del orquestador:

```python
def suggest(self, description: str) -> RankedSuggestion:
    text = normalize(description)                      # una sola vez
    ctx = UserContext.load(self.user)                  # Redis db2, fallback PG
    candidates = []
    for gen in self.generators:                        # history, user_kw, global_kw, fuzzy
        candidates += gen.generate(text, ctx)
    return self.ranker.rank(candidates, ctx.feedback_rates)
```

### 2.5 Política de confianza

`policy.py` mapea score → `Band`. Los handlers consumen el enum y nunca
comparan floats (resuelve D10/D11). Los cortes iniciales replican los actuales
(0.8 / 0.5) para que el primer deploy tenga cambio de comportamiento cero; se
recalibran con los datos de shadow mode (§4.5).

### 2.6 Representación de keywords: `CategoryKeyword`

Nueva tabla en reemplazo del matching sobre `Category.keywords` (JSONField):

```
CategoryKeyword
  category            FK → Category
  keyword_normalized  str            # normalizado con normalization.py al escribir
  weight              float = 1.0
  source              str ∈ {manual, default}
  unique(category, keyword_normalized)
```

- Arregla D3: un keyword repetido entre categorías produce dos candidatos que
  el ranker resuelve, en vez de una colisión silenciosa en un dict.
- Arregla D5: las categorías globales (`is_default=True`) por fin aportan
  candidatos, con el peso menor de `global_keyword`.
- Transición: dual-read (tabla → fallback JSONField), backfill por migración de
  datos desde `Category.keywords` y `DEFAULT_CATEGORY_KEYWORDS`, luego el
  JSONField deja de usarse para matching. El campo queda expuesto donde ya se
  exponga hasta migrar esos consumidores; el doc de corte fija la fecha del
  dual-read (§6, R2).

### 2.7 Índice de historial: `UserTokenStat`

Nueva tabla que reemplaza el escaneo O(100) de D8:

```
UserTokenStat
  user                FK → User
  token               str
  category            FK → Category
  count               int
  last_seen           datetime
  normalizer_version  int
  unique(user, token, category)
  index(user, token)
```

- Se mantiene por **incrementos en escritura**: crear/confirmar/re-categorizar
  un gasto actualiza los conteos de sus tokens. La lectura (camino de latencia
  del usuario) pasa de re-normalizar 100 descripciones a una consulta indexada.
- Reconstruible desde cero con un management command `rebuild_token_stats`
  (idempotente); obligatorio correrlo cuando cambia `NORMALIZER_VERSION`.
- El generador `history` calcula overlap sobre tokens ya normalizados y usa
  toda la banda ≥ 0.5 como candidatos (arregla D4): un match personal de 0.7
  ya no pierde silenciosamente contra un keyword genérico — compite en el
  ranker con el peso más alto.

Alternativas descartadas: `pg_trgm` (requiere `CREATE EXTENSION` en el
PostgreSQL administrado de Railway — riesgo operativo, y resuelve fuzzy, no
indexación de historial) y un índice solo-Redis (no reconstruible, no
consultable con SQL).

### 2.8 Fuzzy

`rapidfuzz` in-process (`token_set_ratio >= 85` contra el léxico de
`CategoryKeyword`) reemplaza el substring bidireccional (D1). Cubre typos
("piza" → "pizza") sin los falsos positivos de la contención de substrings.
`pg_trgm` queda documentado como alternativa si el léxico crece a un tamaño
donde el matching in-process sea un problema real.

### 2.9 Normalización y pureza

- La normalización vive únicamente en `normalization.py`, se aplica también en
  escritura (al indexar tokens y keywords) y está versionada
  (`NORMALIZER_VERSION`). Aplica los diminutivos hoy declarados y muertos
  (D9), o los elimina del código — pero deja de haber intención no
  implementada.
- `suggest()` sigue sin escribir a la base — el contrato ya testeado
  (`test_suggest_does_not_create_categories_as_side_effect`) se preserva. La
  creación de categorías default sigue confinada a
  `helper.get_category_suggestion` / `create_category_for_user`.

---

## 3. Roadmap

| Etapa | Contenido | Esquema | Rollback |
| --- | --- | --- | --- |
| **0 — Determinismo y bugs** | Orden total de desempate; eliminar substring bidireccional; usar la banda 0.5–0.89 del historial; `raw_message` = texto original; umbrales centralizados en `policy.py`; resolver diminutivos (aplicar o borrar) | Sin cambios | Revert de código |
| **1 — Pipeline de scoring** | Generadores/ranker/policy completos; `CategoryKeyword` + `UserTokenStat` + backfills; rapidfuzz; ajuste por feedback; `UserContext` cacheado en Redis db2 | 2 tablas nuevas (+ `SuggestionDecision`, §4.2) | Flag `CATEGORIZER_V2` (env); shadow mode previo al flip |
| **Futuro — condicionado** | Cualquier señal ML (modelos estadísticos, embeddings, LLMs) | — | — |

La Etapa 0 es deployable sola y de bajo riesgo: puro arreglo de defectos sin
esquema nuevo. La Etapa 1 introduce el pipeline detrás de un flag y solo se
activa después del shadow mode (§4.5).

**Futuro condicionado**: la incorporación de ML no es parte de este diseño y
queda sujeta a una revisión profunda con su propio ADR, con datos de precisión
reales (§4.4) como insumo. Lo único que este diseño garantiza al respecto es
que no la bloquea: entraría por la interfaz `CandidateGenerator` sin
re-arquitectura.

---

## 4. Datos, métricas y evaluación

Nada de esta sección es infraestructura de ML: es lo mínimo para saber si el
categorizador funciona y para poder cambiar la implementación sin adivinar.

### 4.1 `raw_message` verdadero

Fix de una línea en el handler: `create_expense(..., raw_message=event.text)`.
La columna ya existe. Hoy guarda la descripción parseada (D7), lo que hace
imposible auditar decisiones o evaluar el pipeline contra mensajes reales.
Honestidad del doc: el corpus previo al fix es irrecuperable — argumento para
priorizar la Etapa 0 ya.

### 4.2 Registro de decisiones: `SuggestionDecision`

```
SuggestionDecision
  user                 FK → User
  expense              FK → Expense (nullable)
  input_text           str
  tokens               JSON
  candidates           JSON     # todos, con scores y evidence
  chosen_category      FK → Category (nullable)
  band                 str
  categorizer_version  str
  latency_ms           int
  created_at           datetime
```

Retención acotada (90 días, job de limpieza — mismo patrón que los 30 días de
`DeletedObject`). Preferida sobre logs puros porque la evaluación necesita
JOINs con la categoría final del gasto.

### 4.3 Feedback → resultado real

El resultado real de un gasto = `final_category` del **último**
`CategorySuggestionFeedback` asociado (el FK no-OneToOne ya soporta
re-categorizaciones); un gasto confirmado sin feedback = aceptación implícita
de la sugerencia. `get_accuracy_stats()` (hoy sin llamadores) se conecta a un
management command de admin.

### 4.4 Métricas

Fuente: `SuggestionDecision ⋈ CategorySuggestionFeedback`.

| Métrica | Definición |
| --- | --- |
| accuracy@auto | % de decisiones en banda AUTO no corregidas después |
| correction rate por banda | % de sugerencias corregidas, por banda |
| coverage por banda | distribución AUTO / CONFIRM / PICK |
| no-match rate | % de mensajes sin ningún candidato |
| precisión por categoría | corrección relativa por categoría sugerida |

### 4.5 Shadow mode

El pipeline nuevo corre en paralelo dentro del mismo job ARQ: solo registra su
decisión en `SuggestionDecision` con su `categorizer_version`, sin afectar la
respuesta al usuario. La comparación offline entre versiones decide el flip
del flag. El doble cómputo debe caber en el presupuesto de latencia (§5.3).
Shadow mode es obligatorio antes de cualquier cambio de política: los scores
nuevos no son comparables 1:1 con las constantes actuales (§6, R1).

---

## 5. Escala

### 5.1 Multi-canal

El categorizador recibe solo `(user, description)` y se mantiene agnóstico de
canal detrás de `services/ml/` — agregar WhatsApp no lo toca. Dos puntos de
contacto concretos con la ventana de WhatsApp
([multichannel_refactor.md](decision_records/multichannel_refactor.md), §5):

- **Límite de 3 botones**: `RankedSuggestion.alternatives` permite un picker
  de top-3 candidatos en vez de todas las categorías del usuario, resolviendo
  el desborde de opciones sin truncado silencioso.
- **Bandas en `policy.py`**: el handler de WhatsApp consume `Band` y reutiliza
  la política sin duplicar umbrales (hoy duplicaría los floats de
  `handlers.py`).

### 5.2 Volumen

- `UserContext` (tasas de feedback, léxico del usuario, versión) cacheado en
  **Redis db2** — la base que el esquema de particionado ya reserva para caché
  (`architecture.md`, "Redis Partitioning") — bajo `catctx:{user_id}:{version}`.
  Invalidación por bump de versión en cada escritura de gasto/categoría/feedback.
- **Precomputar en escritura** (incrementos a `UserTokenStat`) en vez de en
  lectura: el ratio lectura/escritura es ~1:1 (cada mensaje lee y luego
  escribe), pero la lectura está en el camino de latencia del usuario.
- Índices: `unique(user, token, category)` + `index(user, token)` en
  `UserTokenStat`; los índices existentes de `Expense` no cambian.

### 5.3 Operación

- **Presupuesto de latencia**: `suggest()` p95 < 150 ms — holgado dentro del
  `job_timeout=60` de ARQ y deja lugar al doble cómputo del shadow mode.
- **Workers stateless**: el estado compartido vive en Redis/PG; los workers
  ARQ escalan horizontal sin cambios.
- **Atribución**: cada decisión persiste `categorizer_version`
  (código + pesos + `NORMALIZER_VERSION`), así toda regresión de precisión es
  atribuible a una versión concreta.
- **Logging**: el log estructurado de `helper.py` se extiende con versión,
  banda y candidatos top-N.

---

## 6. Riesgos y tradeoffs

| # | Riesgo | Mitigación |
| --- | --- | --- |
| R1 | Los scores nuevos no son comparables 1:1 con las constantes actuales; un flip directo puede mover mensajes entre bandas y degradar UX aunque la precisión mejore | Shadow mode obligatorio + cortes iniciales que replican 0.8/0.5 |
| R2 | Drift entre JSONField y `CategoryKeyword` durante el dual-read | Fijar fuente de verdad por fase y fecha de corte del dual-read en el plan de implementación |
| R3 | Usuarios nuevos sin historial dependen de keywords globales | Es el comportamiento actual; los pesos por fuente ya privilegian historial cuando existe |
| R4 | Más datos personales persistidos (`raw_message` real, `SuggestionDecision`) | Retención acotada (90 días) alineada con el patrón de `DeletedObject` |
| R5 | Determinismo con floats: empates por redondeo | Epsilon en el ranker + el orden total testeado como contrato (estilo "Testing Philosophy" de `architecture.md`) |
| R6 | Complejidad: de 1 archivo de ~395 líneas a un paquete de ~8 módulos | Justificada solo si los contratos son estables: `types.py` y `policy.py` se declaran interfaz pública del paquete |
| R7 | El corpus de mensajes reales empieza a acumularse recién desde el fix de `raw_message` | Priorizar Etapa 0 |

---

## Pendientes al implementar

- Enmendar el "Categorizer Deep Dive" de `architecture.md`: hoy documenta un
  learning loop que no cierra (§1.3) y niveles de keywords globales que no
  operan (D5).
- Tests de contrato nuevos: orden total de desempate, pureza de `suggest()`
  (ya existe), keywords propios ganan a globales, banda 0.5–0.89 del historial
  compite en el ranker.

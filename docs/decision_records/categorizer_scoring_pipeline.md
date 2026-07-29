# Categorizador — Pipeline de Scoring Determinista

**Estado:** propuesto
**Alcance:** arquitectura del módulo de categorización (`services/ml/`):
pipeline de scoring, representación de keywords, índice de historial, política
de confianza y datos de evaluación.
**Fuera de alcance:** cualquier incorporación de ML (modelos estadísticos,
embeddings, LLMs) — condicionada a una revisión profunda futura con su propio
ADR. Cambios de UX del bot. Migración de consumidores del JSONField de
keywords fuera del matching.

Diseño completo en [../categorizer_design.md](../categorizer_design.md).

---

## Contexto y problema

El categorizador actual es una cascada de prioridades con first-match-wins
sobre estructuras sin orden (`set`/`dict`), lo que produce resultados no
deterministas y colisiones silenciosas de keywords duplicados entre
categorías. El matching parcial usa contención bidireccional de substrings
("gas" matchea "gaseosa"). La señal más personalizada — un match de historial
con overlap 0.5–0.89 — se computa y se descarta, perdiendo contra keywords
genéricos. Las categorías globales nunca aportan keywords pese a estar
documentadas como nivel del sistema. El feedback
(`CategorySuggestionFeedback`) se escribe pero no participa de ninguna
decisión, y no hay ninguna métrica de precisión en producción. Además,
`raw_message` guarda la descripción parseada en vez del mensaje original, y el
historial se re-normaliza en Python (últimos 100 gastos) en cada mensaje.

El detalle defecto por defecto, con referencias a código, está en la tabla
D1–D11 del diseño (§1.2).

---

## Decisión

1. **Pipeline generadores → ranker → policy.** Cada fuente (historial,
   keywords propios, keywords globales, fuzzy) emite candidatos con score y
   evidencia; un ranker único los combina con pesos por fuente; `policy.py`
   mapea el score a una banda de acción (`AUTO | CONFIRM | PICK`). Los
   handlers consumen el enum de banda, nunca floats. Contratos estables en
   `types.py` y `policy.py`.
2. **`CategoryKeyword` como representación del léxico.** Tabla
   `(category, keyword_normalized, weight, source)` en reemplazo del matching
   sobre el JSONField, con dual-read durante la transición. Los keywords
   duplicados pasan de colisión silenciosa a candidatos concurrentes; las
   categorías globales por fin aportan, con peso menor.
3. **`UserTokenStat` como índice del historial.** Conteos
   `(user, token, category)` mantenidos por incrementos en escritura y
   reconstruibles por management command. Elimina el escaneo O(100) del camino
   de latencia y permite usar toda la banda ≥ 0.5 del historial como
   candidatos.
4. **Determinismo por orden total.** Desempate
   `(-score, orden_de_fuente, -aceptaciones_de_feedback, category_id)` con
   epsilon para floats, testeado como contrato.
5. **Feedback como ajuste de score.** Tasa de aceptación suavizada por
   (usuario, categoría) multiplica el score del candidato — el feedback deja
   de ser write-only. Es un conteo, no un modelo.
6. **`raw_message` = texto original del mensaje.** Fix de una línea en el
   handler; hoy se pierde en la escritura.
7. **Shadow mode + feature flag antes de cualquier flip.** El pipeline nuevo
   registra sus decisiones en `SuggestionDecision` (con `categorizer_version`
   y latencia) sin afectar la respuesta; la comparación offline decide la
   activación. Los cortes iniciales replican los actuales (0.8 / 0.5).

---

## Alternativas consideradas

- **LLM como capa de categorización** — descartada por decisión de producto:
  costo por mensaje, latencia y dependencia externa. El enfoque es
  determinista; cualquier señal ML futura queda condicionada a una revisión
  profunda con su propio ADR.
- **`pg_trgm` para fuzzy e índice** — requiere `CREATE EXTENSION` en el
  PostgreSQL administrado de Railway (riesgo operativo) y solo resuelve fuzzy,
  no la indexación del historial. Se prefiere `rapidfuzz` in-process; `pg_trgm`
  queda como alternativa documentada si el léxico crece.
- **Arreglar el JSONField in-place** — mantiene la colisión estructural del
  dict plano y acopla el matching al formato expuesto a otros consumidores.
- **Índice de historial solo en Redis** — no reconstruible ante pérdida, no
  consultable con SQL para evaluación. Redis (db2) queda como caché del
  contexto, no como fuente de verdad.

---

## Consecuencias

- Más código (1 archivo → paquete de ~8 módulos) y 3 tablas nuevas
  (`CategoryKeyword`, `UserTokenStat`, `SuggestionDecision`) a cambio de
  determinismo, explicabilidad (cada sugerencia lleva su evidencia) y
  extensibilidad sin re-arquitectura.
- El contrato de pureza de `suggest()` (no escribe a la base) se preserva y
  sigue testeado; la creación de categorías default sigue confinada al helper.
- La política de confianza se centraliza: un canal nuevo (WhatsApp) consume
  bandas y `alternatives` top-N sin duplicar umbrales ni reventar su límite de
  botones.
- Aumentan los datos personales persistidos (`raw_message` real,
  `SuggestionDecision`): retención acotada de 90 días, alineada con el patrón
  de `DeletedObject`.
- El "Categorizer Deep Dive" de `architecture.md` queda pendiente de enmienda
  al implementar: hoy describe un learning loop y niveles de keywords que no
  operan como dice.
- El corpus de mensajes reales para evaluación empieza a acumularse recién
  desde el fix de `raw_message` — razón para priorizar la Etapa 0 del roadmap.

---

## Referencias

- [../categorizer_design.md](../categorizer_design.md) — diseño completo
  (diagnóstico D1–D11, contratos, roadmap, métricas, escala).
- [multichannel_refactor.md](multichannel_refactor.md) §5 — restricciones del
  canal WhatsApp que este diseño resuelve (límite de botones, umbrales).
- `../architecture.md` — "Service Layer Design" (el cambio queda contenido en
  `services/ml/`), "Redis Partitioning" (db2 para caché), "Testing Philosophy"
  (tests de contrato).

# Decisiones de frontend — Cierre de Fase B

**Proyecto:** SmartExpense · **Fecha de cierre:** 2026-07-27
**Entrada:** Cierre de Fase A (estructura limpia del backend, base `2b43feb`, 8 commits, 242 tests verdes)
**Prerrequisito de:** Fase C (implementación)

> Esta fase no produjo código. Baja la decisión macro —frontend en Django templates + HTMX,
> abandonando React y deprecando Django Ninja— a las decisiones concretas que la componen.
> Cada cierre está redactado para poder explicarse en 60 segundos con su porqué.

**Etiquetado:** DATO = verificado. INFERENCIA = razonamiento sin verificación directa.

---

## Contexto heredado (no se rediscutió)

- **DATO** — Decisión macro cerrada antes de esta fase: Django templates + HTMX. `apps/api` borrada,
  `django-ninja` fuera de `requirements`, `resolve('/api/expenses/')` no resuelve.
- **DATO** — `services/auth.py` vivo y testeado, sin consumidor. Fase A lo preservó (D2) para que B lo consuma.
- **DATO** — `services/selectors.py` y `services/constants.py` existen. La lógica de consulta ya vive fuera de las views.
- **DATO** — `backend/templates/` y `apps/web` reservados por Fase A, sin crear.
- **DATO** — 3 usuarios. Hetzner 4 GB. nginx sirve estáticos, sin build step. Uso primario **mobile**.
- **DATO** — Campo virgen: SmartExpense no tiene templates previos. Cero deuda.

---

## B0 — Adopción del sistema de diseño

**Elegido:** Consumidor estricto, **lenguaje reducido**.

`tokens.css`, `fonts.css` y las fuentes se copian **verbatim** desde la landing. Las extensiones viven
en un bloque marcado de `smartexpense.css`. **Si divergen, gana la landing.**

- **Se hereda:** tipografía (Geist / Geist Mono display), escala `--ink-1..5`, superficies
  (`--mod-*`, `--bg-solid`, `--line`), radius 3px, lenguaje de módulos **quietos**,
  `--amber` como acento único, `--signal` solo para estados vivos.
- **Se descarta:** backdrop animado, señales en gaps, módulos fantasma, `animateMotion`.
- **Criterio de promoción:** una extensión sube a `tokens.css` canónico recién con **2+ consumidores**.

**Porqué:** el sistema ya probó que se porta; falta probar que sabe achicarse. En una herramienta de
uso diario la decoración compite con los datos, que son el producto. El blog ya podó por la misma lógica.

**Evidencia:** DATO — `tokens.css` idéntico byte a byte entre `ivanvallejos.dev` y `blog` (verificado con `diff`).
DATO — ADR del blog: módulos quietos, Alpine eliminado.

---

## B1 — Autenticación web

**Elegido:** **Puente magic-link → sesión Django**, vía única.

`/link` se reactiva y emite el token; `services/auth.py` encuentra su consumidor. La view valida,
hace `login(request, user)` y redirige. El token no sobrevive al redirect.

| # | Sub-decisión |
|---|---|
| S1 | Single-use: `jti` quemado en Redis al consumir, TTL = TTL del token |
| S2 | **TTL del link: 15 minutos** (decisión de Ivan; motivo: no se maneja dinero real) |
| S3 | Sesión rolling **14 días** + `SESSION_SAVE_EVERY_REQUEST` |
| S4 | 302 inmediato a URL limpia tras consumir |
| S5 | Cookie `Secure` + `HttpOnly` + `SameSite=Lax` |

- **Break-glass:** `/admin/login/` para `is_staff`. Ya existe — se documenta en el runbook, no se construye.
  Es lo que hace innecesaria la convivencia de dos flujos de auth.
- **`next_token` descartado:** la sesión rolling ya cubre "volvió en 48 h"; lo que queda afuera es
  cross-device, que `next_token` tampoco resuelve.

**Porqué:** la identidad ya vive en el canal de mensajería (`ChannelIdentity`); una segunda fuente de
verdad para 3 usuarios es inventada. Lo interesante es el puente: stateless (JWT) → stateful (sesión),
traducido una sola vez, en el borde.

**Evidencia:** DATO — `services/auth.py` testeado (Fase A, D2) · DATO — `ChannelIdentity` en `core.models` ·
DATO — Redis en stack (`bot/state.py`).

---

## B2 — Estrategia de partials

**Elegido:** **Endpoints de partial dedicados.** Una URL propia por región swappable; ambas views
comparten `services/selectors.py`.

**Principio 1 — Criterio de admisión.** Default = página completa. Un swap se justifica solo si
(a) la región es chica **y** (b) el reload perdería scroll, foco, un form a medio llenar o contexto visual.

| Interacción | Swap |
|---|---|
| Filtros categoría + rango | Sí |
| Alta de gasto | Sí |
| Borrado de gasto | Sí |
| Navegación entre secciones | No |
| Login / magic-link | No (302, cerrado en B1) |

**Principio 2 — Una sola región por interacción.** Los filtros afectan totales, lista y gráfico:
todos viven en un wrapper único `#results`, un solo swap. OOB **solo** si aparece una región que no
puede vivir dentro del wrapper (ver excepción declarada en B5).

**Organización de templates:**

```
backend/templates/
├── base.html
├── shared/              partials reutilizables
├── dashboard/
│   ├── index.html
│   └── partials/
└── auth/
```

Convención de Bricka (raíz + directorio por vertical + partials dentro del vertical), con la enmienda
de `shared/` en vez de raíz plana.

**Porqué:** un partial pedido por HTTP es un recurso, y los recursos tienen URL — contrato visible en
`urls.py`, testeable con el test client sin fingir headers, sin rama no-HTMX que se pudra por falta de uso.
La duplicación de lógica no aplica porque `selectors.py` ya existe.

**Evidencia:** DATO — Bricka usa URL dedicada en producción · DATO — `services/selectors.py` (Fase A).

---

## B3 — Alpine.js

**Elegido:** **Alpine.js NO entra.**

**Escalera de admisión** (se baja solo si el escalón anterior no alcanza):

1. HTML/CSS nativo — `<select>`, `<dialog>`, `<details>`, `<input type="date">`, `:has()`, `:target`
2. HTMX — si el estado tiene que llegar al server de todos modos
3. Vanilla JS puntual — **techo duro: ~10 líneas por caso, sin estado compartido entre componentes**
4. Reapertura de B3

**Casos resueltos:** dropdown de categoría → chips con `hx-get` · confirmación de borrado → `<dialog>` nativo ·
fecha → `<input type="date">` nativo. **Date picker custom descartado**: estético, no funcional, y de lo
más fácil de romper en accesibilidad y mobile.

**Porqué:** los tres casos identificados los cubre HTML nativo + HTMX, y el caso que sí justificaría Alpine
—campos condicionales— no existe: el form replica la lógica plana de los mensajes. El blog ya sacó Alpine
en la misma situación.

**Evidencia:** DATO — blog eliminó Alpine (ADR 2026-07-25) · DATO — form sin campos condicionales ·
DATO — Bricka usa Alpine, pero con forms densos y multiusuario: contexto distinto.

---

## B3.5 — Gráficos del dashboard

**Elegido:** **SVG inline server-side**, dentro del wrapper `#results`.

**Paleta categórica — OKLCH con lightness y chroma fijos, solo rota el hue:**

| Rol | Hue | Notas |
|---|---|---|
| Marca | 70 | `--amber`, `oklch(0.78 0.13 70)` — reservado |
| Estado vivo | 155 | `--signal`, `oklch(0.72 0.12 155)` — reservado |
| Error / peligro | 25 | **reservado** — resuelve la tensión *b* del ADR del blog |
| Categoría 1–6 | 122 · 195 · 235 · 275 · 315 · 350 | `L 0.78 · C 0.12` |

- **Fuente de verdad: Python** (`services/constants.py`), resuelta a **hex literal**. El CSS espeja
  para usos no-gráficos (chips, badges). Motivo: los rasterizadores livianos no soportan `oklch()` ni CSS vars.
- **Asignación:** `color_slot` persistido en `core.Category`, **elegido por el usuario**. Nunca por ranking —
  si el color siguiera al ranking, la misma categoría cambiaría de color al cambiar de rango.
- **Overflow:** top 6 + fila agregada **"Otros"** en `--ink-4`. No es una categoría: no existe en la base,
  no se puede crear ni colorear. Es el resto.
- **Forma:** barras horizontales ordenadas por monto. Torta descartada (comparar longitudes es más preciso
  que comparar ángulos, y las etiquetas largas entran).
- **Sin tooltips.** Valores impresos en el SVG, siempre visibles: en mobile no existe el hover.
- Vive en el bloque de extensión de `smartexpense.css`. **Candidato a CIMIENTO v3, sin promover.**

**Porqué:** un color que codifica datos es portador de información, no decoración — extiende la regla del
ADR en vez de romperla. Rotar solo el hue mantiene a todos los colores como hermanos del ámbar. Y el
render server-side es lo único que deja al bot generar el mismo gráfico.

**Evidencia:** DATO — tokens ya en OKLCH · DATO — `--signal` ya es un punto del mismo círculo (L≈0.72, C≈0.12) ·
DATO — Telegram `sendPhoto` y WhatsApp Cloud API aceptan JPEG/PNG, no SVG · DATO — uso primario mobile.

---

## B4 — Estado de filtros y navegación

**Elegido:** **Querystring**, con `hx-replace-url`.

| # | Sub-decisión |
|---|---|
| S1 | Params: `?cat=` (repetible) + `?rango=` (relativo: 3m/6m/12m). Contrato público |
| S2 | **`hx-replace-url`**, no `push`: la URL refleja el estado actual sin acumular historial |
| S3 | Sin params → rango por defecto, todas las categorías. La URL desnuda es válida y útil |
| S4 | Helper de parseo **único**, compartido por la vista completa y la parcial |
| S5 | Params inválidos → caen al default + aviso en la franja global (ver B5) |

- **Categoría: selección múltiple** desde el día uno (`getlist('cat')`). Chips toggle renderizados
  **dentro** de `#results`; cada chip trae el `hx-get` del estado resultante de tocarlo. Cero JS.
- **Filtro temporal = rango, no mes puntual.** Motivo: un mes puntual convierte el gráfico de evolución
  mensual en una sola barra, y ambos gráficos viven en el mismo wrapper.

**Porqué:** el filtro es *qué recurso mirás*, no un detalle de interacción — en la URL, ambas views parsean
lo mismo con el mismo helper y recarga, compartir y bookmark salen gratis. `replace` en vez de `push` porque
el sistema es mobile-first y ahí el back es el gesto de navegación, no de deshacer.

**Evidencia:** DATO — uso primario mobile · DATO — B2 endpoint dedicado + wrapper único ·
DATO — sin Alpine (B3), el estado no tiene dónde vivir en cliente que no sea el DOM.

---

## B5 — Errores y estados de carga

Tres clases separadas, tres respuestas distintas.

### Clase 1 — Validación (el usuario puede corregir)

**Re-render del form con errores inline.** El server devuelve el form con `form.errors`; HTMX swappea con
`outerHTML`; los errores salen junto a cada campo. Validación server-side como fuente única de verdad, cero JS.

**Excepción declarada al Principio 2 de B2:** el alta exitosa toca dos regiones que no pueden compartir
wrapper (el form arriba, `#results` abajo). Responde con el form limpio **+ fragmento OOB para `#results`**.
Cumple la condición que B2 dejó prevista: es uso legítimo, no una grieta.

### Clase 2 — Falla técnica (el usuario no puede corregir)

**`HX-Retarget` a una franja global de avisos.** `#results` queda intacto: el usuario ve el error *y*
sigue viendo sus datos. Reintenta, anda, el aviso se va, nunca perdió nada.

Se descartó el partial de error dentro del target por **destructivo**: un timeout de Redis no debería
costar la vista que estabas leyendo.

> **La franja global NO es un toast.** Sin timer, sin stack, no flota, no necesita JS. Es un `<div>` que
> el server llena o deja vacío. **El trigger 3 de B3 no se dispara: Alpine sigue afuera.**

### Clase 3 — Estados vacíos (no son errores)

Server-side dentro de `#results`, en `--ink-3`, **sin rojo y sin ícono de error**:

| Vacío | Mensaje | Acción |
|---|---|---|
| Sin gastos en absoluto | "Todavía no registraste gastos" | Apuntar al form / al bot |
| El filtro no matchea | "Ningún gasto en este rango" | Link para limpiar filtros (= URL desnuda de S3) |

### Indicadores de carga

**Barra fina ámbar global** (`hx-indicator`) para cualquier request. Se descartó el skeleton local: con
respuestas de ~50 ms aparece y desaparece antes de que el ojo lo registre, y eso es flicker.

**Regla complementaria:** las acciones lentas llevan feedback **propio en el disparador** — el botón se
deshabilita y cambia de texto mientras dura (`hx-disabled-elt`, clase `htmx-request`). Sin JS. Aplica al
export a Excel.

**Porqué:** validación, falla técnica y vacío tienen causas distintas y el usuario puede hacer cosas
distintas con cada una; meterlas en un mecanismo único es el error clásico. Lo destructivo se evita
siempre que haya algo que perder.

**Evidencia:** DATO — hue 25 reservado en B3.5 · DATO — form propio con select + numérico + texto ·
INFERENCIA — latencias sub-100 ms con 3 usuarios en Hetzner.

---

## Riesgos aceptados conscientemente

| # | De | Riesgo | Mitigación / estado |
|---|---|---|---|
| R1 | B0 | SmartExpense se verá más sobrio que landing y blog | Aceptado: sacrificio parcial del valor de portfolio visual |
| R2 | B1 | El token viaja en query string → **aparece en el access log de nginx** | TTL 15 min + single-use. Acotado, **no eliminado** |
| R3 | B1 | Dependencia del bot para el login normal | Break-glass vía `/admin/login/` |
| R4 | B1 | Cross-device tiene fricción: el link nace en el dispositivo del bot | Si duele, la respuesta es un código corto tipeable, no un refresh token |
| R5 | B1 | Nunca se confirmó si los usuarios tienen password usable | La opción de login clásico quedó sin evaluar a fondo. Hueco registrado |
| R6 | B2 | Más entradas en `urls.py` | Precio de que el contrato sea explícito |
| R7 | B2 | El wrapper `#results` puede crecer de más | Señal: si incluye regiones que nunca cambian juntas, **se parte** (no se parchea con OOB) |
| R8 | B2 | `shared/` diverge levemente de Bricka | Dos convenciones que recordar. Reversible |
| R9 | B3 | Vanilla JS acumulado que reimplemente Alpine peor | Techo de 10 líneas + triggers. Si un trigger salta y no reabrimos, la mitigación falló |
| R10 | B3.5 | **INFERENCIA sin verificar:** distinguibilidad de 6 hues a L y C fijos | **Mirarlo en monitor antes de Fase C** |
| R11 | B3.5 | Deuteranopia: 122 y 350 no se distinguen | Barras etiquetadas y ordenadas: el color es refuerzo, no único canal |
| R12 | B3.5 | Construir SVG a mano cuesta más que Chart.js | Acotado a dos gráficos simples |
| R13 | B3.5 | La paleta duplicada Python↔CSS puede divergir | Python manda; el CSS se genera o se checkea |
| R14 | B3.5 | **INFERENCIA:** `oklch()` requiere browsers ~2023+ | Verificar si importa algún cliente fuera de eso |
| R15 | B4 | El back no deshace filtros | Consciente: en mobile se prioriza salir sobre deshacer |
| R16 | B4 | Los links con `?rango=` **derivan**: quien lo abra después ve otros datos | Aceptado: "últimos 6 meses" *es* la intención, no una fecha |
| R17 | B4 | Multi-select luce poco en el gráfico de composición | Rinde en la lista, no en el gráfico |
| R18 | B4 | **INFERENCIA:** el `<select>` de rango pierde foco al swappear | Si molesta → `hx-preserve`. Riesgo menor |
| R19 | B5 | HTMX no swappea respuestas no-2xx por defecto | Requiere configurar `responseHandling` o devolver 200 con el partial de error |

---

## Disparadores de reapertura declarados

| Decisión | Se reabre si… |
|---|---|
| **B3** (Alpine) | Aparece estado de UI compartido entre elementos que no son padre/hijo · un tercer archivo de vanilla JS o uno de más de ~30 líneas · B5 pide toasts con timer y stack (**no ocurrió**) |
| **B3.5** (gráficos) | Se necesita un gráfico que no sean barras o líneas simples · más de 6 categorías con color propio simultáneo |
| **B4** (filtros) | Se quiere filtrar por **mes puntual** y ver evolución mensual al mismo tiempo. Eso rompe la opción de rango |
| **B5** (carga) | El export a Excel pasa a ser **async** vía ARQ: el patrón de UI cambia a polling |
| **B0** (diseño) | Una extensión de `smartexpense.css` aparece en un **segundo consumidor** → sube a `tokens.css` canónico |

---

## Entradas a Fase C

**Bloqueantes**

- `SITE_URL` / `BASE_URL` — estacionado en §5 de Fase A. **Sin esto el bot no sabe qué URL emitir** (B1).

**Backend**

- Campo `color_slot` en `core.Category` + migración + slots para las categorías pre-cargadas.
- Paleta definida en `services/constants.py`, resuelta a hex literal.
- Reactivación de `link_command` (`/link`) emitiendo el token.
- Quema de `jti` en Redis (single-use).

**Frontend**

- Creación de `apps/web` y `backend/templates/`.
- Copia verbatim de `tokens.css`, `fonts.css` y las dos fuentes variables.
- Helper de parseo de querystring compartido entre `DashboardView` y `DashboardResultsView`.
- Template tag de barras horizontales, reutilizable entre composición por categoría y evolución mensual.
- Configuración de `responseHandling` de HTMX para el retarget de errores.

**Verificaciones previas**

- Distinguibilidad de la paleta en monitor (R10).
- Soporte de `<input type="month">` en Firefox/Safari desktop — si falla, el rango va con `<select>`.
- Soporte de `oklch()` en los browsers que importen (R14).

**Al cierre de Fase B**

- Borrar `frontend/` (React), según D1b de Fase A.

---

## Puertas abiertas (fuera de alcance)

- **Gráficos por Telegram / WhatsApp.** El render server-side lo hace viable: falta un paso de rasterizado
  SVG→PNG. Ninguna de las dos plataformas renderiza SVG como imagen, y con un motor JS habría hecho falta
  Chromium headless en un Hetzner de 4 GB. Feature futura, decisión ya no bloqueada.
- **Export a Excel** y profundización del categorizador (Pandas / Polars). Si el export se vuelve async,
  dispara la reapertura de B5.
- **CIMIENTO v3:** la paleta categórica y el hue de error son candidatos a canónico si aparece un
  segundo consumidor.


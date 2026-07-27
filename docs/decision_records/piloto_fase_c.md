# Cierre de Fase C — Piloto del dashboard en Django templates + HTMX

**Proyecto:** SmartExpense · **Base:** `c5754b9` (main) · **Rama:** `feature/dashboard-ssr-c1`
**Entrada:** Cierre de Fase A (backend limpio) + Decisiones de frontend de Fase B
**Prerrequisito de:** Fase D (sistema visual) y Fase E (limpieza post-piloto)

> La fase construyó una sola vista —el dashboard principal— en cinco capas, cada una
> verificable antes de la siguiente. El objetivo no era tener el dashboard: era averiguar
> si el enfoque de la Fase B aguanta la complejidad real antes de comprometer el resto
> de las vistas.

**Etiquetado:** DATO = verificado. INFERENCIA = razonamiento sin verificación directa.

---

## 1. Estado real del piloto

### Capas construidas

| Capa | Qué | Estado |
| --- | --- | --- |
| C1 | SSR pelado: vista, balance, lista paginada, filtros por form GET | Cerrada |
| C2 | Paginación HTMX con centinela `revealed` | Cerrada |
| C3 | Filtros de categoría y rango sobre `#results` | Cerrada |
| C4 | Borrado inline con balance sincronizado | Cerrada |
| C5 | Revisión de conjunto y refactor | Cerrada |

### Verificado por Ivan en su entorno

- **DATO** — El dashboard responde con sesión; el redirect a `/admin/login/` funciona.
- **DATO** — Balance, filtros de categoría múltiple y rango, y paginación funcionan
  **con JavaScript deshabilitado**. El baseline de progressive enhancement existe.
- **DATO** — La URL refleja el estado, se conserva al recargar y es compartible.
- **DATO** — El chip activo se des-clickea: su propio `href` es el estado sin él.
- **DATO** — Filtrar actualiza lista y balance en un solo request; la barra muestra
  `/dashboard/?cat=…` y nunca el endpoint interno.
- **DATO** — Borrar baja el balance en el mismo request, respeta los filtros activos,
  y sin JS redirige sin repetir el POST al recargar.
- **DATO** — El registro queda en `DeletedObject`.

### Verificado solo por la suite

- **DATO** — 280 tests verdes (242 heredados + 38 de la fase). Cero regresión en el bot.
- **DATO** — Paginación estable con gastos de fecha idéntica: 25 gastos recorridos
  página por página dan 25 ids distintos. Es lo que justifica el `order_by("-date", "-id")`.
- **DATO** — El endpoint de error del borrado responde 404 con `HX-Retarget: #avisos`
  y su cuerpo no contiene `id="results"`.

### No verificado

- **SIN DATO** — Traza de red del scroll infinito: no se confirmó con la pestaña Network
  que haya exactamente una request por página. Se verificó por inspección del HTML y por
  el comportamiento observado, no por traza.
- **SIN DATO** — El centinela con listas largas de verdad. Se probó con ~60 gastos
  sembrados, no con volumen real.
- **SIN DATO** — Comportamiento en browsers que no sean el de desarrollo de Ivan.
- **SIN DATO** — Latencia real: todo se midió en local, no contra el Hetzner.

---

## 2. Veredicto honesto: ¿HTMX sostuvo la complejidad?

**Sí, con tres puntos donde crujió.** Ninguno es descalificante, pero los tres son
específicos y vale la pena poder contarlos.

### Crujido 1 — B2 se contradice consigo mismo en el borrado

El criterio de admisión de B2 dice que un swap se justifica cuando el reload perdería
el scroll. El Principio 2 dice que una interacción toca una sola región, y para el
borrado esa región es `#results` completo. Pero swappear `#results` **reconstruye la
lista desde la página 1**: si borrás un gasto después de scrollear cinco páginas,
perdés el scroll igual. El swap no evitó lo que el criterio de admisión decía que
tenía que evitar.

Se aceptó conscientemente para el piloto. Las salidas posibles son sacar solo el `<li>`
con `hx-swap="delete"` y mandar el balance por OOB —que conserva el scroll pero fuerza
la excepción de B5 en un caso donde las regiones **sí** pueden compartir wrapper—, o
partir `#results` según la señal que R7 ya tenía declarada. Es la decisión más
interesante que dejó la fase y no está tomada.

### Crujido 2 — "cero JS" empuja lógica al servidor, y eso tiene un costo de descubrimiento

Dos casos concretos. Si el HTML usara `hx-replace-url`, htmx escribiría en la barra la
URL del endpoint interno `/dashboard/resultados/`, que no es navegable; hubo que mover
la responsabilidad al server con el header `HX-Replace-Url`. Y htmx no swappea respuestas
no-2xx por defecto (R19), así que sin el `<meta name="htmx-config">` los errores
desaparecen en silencio.

Las dos soluciones son buenas —una sola fuente de verdad, cero JS— pero ninguna es
obvia leyendo el HTML. Alguien que abra `_results.html` no ve dónde se decide la URL.
El costo de HTMX no es el runtime: es que el comportamiento se reparte entre atributos,
headers y configuración.

### Crujido 3 — la mutación tuvo que preguntar si el cliente tiene JavaScript

B2 eligió endpoints de partial dedicados justamente para no tener ramas que dependan de
headers. Funcionó para las tres vistas de lectura. Pero el borrado necesita responder
distinto según el cliente: con htmx devuelve `#results`, sin htmx redirige con
Post/Redirect/Get para que F5 no reintente. Eso obliga a leer `HX-Request`.

No es una violación de B2 —la regla era sobre las vistas de lectura— pero marca el
límite: la simetría se sostiene mientras leés, y se rompe cuando mutás.

### Lo que sostuvo mejor de lo esperado

El baseline de C1 no fue trabajo tirado: cada capa posterior fue **agregar atributos** a
HTML que ya funcionaba. El chip pasó de `<a href>` a `<a href hx-get>`; el centinela es
un link que además se auto-pide. En ningún momento hubo una rama HTMX y otra sin HTMX
conviviendo, salvo el caso del borrado. Haber hecho C1 primero fue lo que hizo barato
todo lo demás.

Y la decisión de B2 de que los partials tengan URL propia se pagó sola en los tests: las
tres vistas de lectura se testean con el test client sin fingir un solo header.

---

## 3. Deuda técnica registrada

| # | Deuda | Origen | Fase de resolución |
| --- | --- | --- | --- |
| D1 | El borrado resetea la lista a la página 1 | C4, crujido 1 | Fase D, con el scroll real delante |
| D2 | Sin `hx-replace-url` en la paginación: recargar tras scrollear vuelve al principio | C2, decidido | Fase D si molesta |
| D3 | Sin navegación "Anterior" sin JS: solo el botón atrás del navegador | C2 | Fase D |
| D4 | Sesión vencida durante el scroll: el 302 al login se swappearía dentro de la lista | C2 | Con B1 implementado |
| D5 | `hx-confirm` en lugar del `<dialog>` nativo que nombró B3 | C4, sustitución declarada | Fase D, cuando haya estilos |
| D6 | Sin separador de miles en los montos | C1 | Fase D |
| D7 | Tamaño de página fijo en 20, sin validar contra uso real | C1 | Fase D |
| D8 | `USER_TZ` es constante global, no preferencia por usuario | C1 | Cuando exista un segundo huso |
| D9 | El bot y la web calculan "este mes" con código distinto (`get_month_stats` vs `rango_bounds`) | C1 | Unificar cuando el bot muestre rangos |

### Enmienda a la Fase B

**B4-S1** — El enum de `?rango=` se extendió con `mes` (mes en curso), que pasa a ser el
default. Sigue siendo un rango relativo, así que no contradice la decisión: la extiende.
Motivo: el hero balance coincide así con el número que ya reporta el bot.
**Consecuencia registrada:** con `rango=mes` el gráfico de evolución mensual de B3.5 es
una sola barra. Se resuelve en Fase D dándole al gráfico su propia ventana temporal en
vez del rango del filtro.

**B3** — Se sustituyó `<dialog>` nativo por `hx-confirm` para la confirmación de borrado.
El principio de B3 se respeta (nada de Alpine, nativo primero); la solución nombrada no.
Reversible en Fase D.

### Confirmaciones de riesgos de la Fase B

- **R18 se confirmó como no problema.** El `<select>` de rango no pierde foco de forma
  molesta al swappear. No hizo falta `hx-preserve`.
- **R9 no se disparó.** Cero archivos de vanilla JS. El techo de 10 líneas ni se rozó:
  la fase terminó con exactamente cero líneas de JavaScript propio.
- **R6 se confirmó.** `urls.py` pasó de 1 a 4 entradas para una sola vista. Es el precio
  del contrato explícito y se pagó sin dolor.

---

## 4. Insumo para la Fase E — qué quedó redundante

`apps/api` ya se había borrado en Fase A (commit `c1b993f`). Lo que el piloto aporta es
la verificación de qué capacidades suyas quedaron efectivamente cubiertas y cuáles no.

| Endpoint que existía | ¿Cubierto por el piloto? |
| --- | --- |
| `GET /expenses/` (lista con filtros) | **Sí** — `DashboardView` + `DashboardExpensesView` |
| `GET /balances/` | **Sí** — el hero, dentro del mismo render |
| `DELETE /expenses/{id}/` | **Sí** — `DashboardDeleteExpenseView`, con el mismo soft-delete |
| `POST /expenses/` (alta) | **No** — solo por bot. B5 lo tiene diseñado, no construido |
| `PUT /expenses/{id}/` (edición) | **No** — sin equivalente web ni diseño |

**Conclusión:** el borrado de `apps/api` no dejó ningún hueco funcional que el piloto haya
revelado. Las dos capacidades sin cubrir —alta y edición desde la web— no son deuda de la
API borrada: son features que nunca tuvieron consumidor, porque el frontend React no llegó
a usarlas en producción.

Lo que **sí** hay que revisar en Fase E:

- `services/auth.py` sigue sin consumidor. El piloto usó el break-glass de `/admin/login/`
  y no tocó el magic link. B1 sigue entero sin implementar, y con él quedan `link_command`
  y la quema de `jti` en Redis.
- `frontend/` (React) sigue en el repo. D1b de Fase A dijo que se borra al cierre de Fase B;
  la Fase B cerró y no se borró. El piloto ya no lo usó como referencia visual: los
  templates se escribieron sin mirarlo. **Se puede borrar sin costo.**
- `SITE_URL` / `BASE_URL` sigue estacionado desde Fase A. Bloquea B1, no bloqueó a C.

---

## 5. Estado del código al cierre

``` bash
backend/apps/web/          filters.py  views.py  urls.py        (~230 líneas)
backend/templates/         base.html + dashboard/ + shared/     (~150 líneas)
backend/services/          +rango_bounds, +get_dashboard_data, +USER_TZ, +RANGOS
backend/static/vendor/     htmx.min.js 2.0.10 (51 KB, vendoreado)
backend/tests/web/         38 tests en 4 archivos + conftest
```

**Cuatro rutas, cuatro vistas, dos familias.** `_SesionRequerida` es lo único que
comparten lectura y mutación; `_DashboardBaseView` agrupa las tres vistas de lectura, que
se distinguen **solo** por qué template renderizan. Toda la lógica de querystring vive en
`apps/web/filters.py` y todo el acceso al ORM en `services/selectors.py`.

### Bugs encontrados durante la fase

Los tres los encontró la suite o una prueba deliberada, ninguno llegó a producción:

1. `Paginator.get_page()` no falla fuera de rango: devuelve la última página. El fragmento
   inyectaba el estado vacío en medio de la lista. La guarda ahora mira la página pedida.
2. `GET` al endpoint de borrado devolvía **500**, no 405: la vista heredaba un `get()` que
   no aceptaba su argumento de URL. Herencia por inercia, corregida en C5.
3. `LoginRequiredMixin` es incompatible con views async, y `request.user` **funciona con
   usuario anónimo** y explota con usuario logueado. Se detectó antes de escribir C1,
   probándolo en vez de asumirlo.

---

## 6. Entradas a Fase D

- Copia verbatim de `tokens.css`, `fonts.css` y las dos fuentes variables (B0).
- Estilar las clases que el piloto dejó puestas: `hero-balance`, `chip`, `chip--activo`,
  `expense-item`, `franja-avisos`, `cargar-mas`, `estado-vacio`.
- El gráfico de B3.5, que quedó fuera del piloto a propósito, con su `color_slot` en
  `core.Category`, la migración y la paleta en `services/constants.py`.
- Decidir D1 (reset de la lista al borrar) con el scroll estilado delante.
- Separador de miles en los montos.
- Verificar R10 (distinguibilidad de los 6 hues) en monitor, que sigue sin hacerse.

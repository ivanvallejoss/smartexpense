# Frontend Fase D — Sistema de tokens y estilado del piloto

## Resultado

El piloto de Fase C está estilado con el sistema Minimalismo Editorial,
tokenizado como sistema reutilizable entre SmartExpense, la landing y el
blog. Verificado por Ivan sección por sección (hero → filtros → lista →
estados) en su entorno.

Archivos:

- `backend/static/css/tokens.css` — copia VERBATIM del canónico de la
  landing (Cimiento v2). No se edita en este repo.
- `backend/static/css/fonts.css` — verbatim (Geist / Geist Mono variables,
  self-hosted en `backend/static/fonts/`).
- `backend/static/css/smartexpense.css` — extensiones `--se-*` +
  componentes del dashboard. Documentación de contrato en el header del
  archivo.

## Arquitectura de compartición (confirma B0)

Consumidor estricto: copia verbatim del canónico; si divergen, gana la
landing. Extensiones locales con prefijo `--se-*`. Promoción al canónico
recién con 2+ consumidores (se copia, no se comparte en runtime — los tres
sistemas son servicios separados). Al promover, se quita el prefijo.

Primera candidata a promoción identificada: la regla de `focus-visible`
para `select`/`input` (el canónico solo cubre `a`/`button`); sube cuando la
landing incorpore formularios.

## Paleta de categorías

Colores de DATOS, no de marca (`--amber` sigue siendo el único acento).
Mecanismo: luminancia y croma compartidos (`--se-cat-l: 0.72`,
`--se-cat-c: 0.11`), varía solo el hue → refactor de paleta completa = dos
líneas. Seis slots: 5 (rosa), 40 (terracota), 195 (teal), 240 (celeste),
285 (lavanda), 330 (malva).

Medido (coloraide, WCAG 2.1 / ΔE2000):

- Contraste ≥ 6.6:1 sobre la superficie más clara (`--mod-warm`) → AA
  texto chico con margen. Cierra R10 con número.
- Distinguibilidad mínima entre todos los pares, incluyendo `--amber` y
  `--signal`: ΔE 13.0.
- Zonas de hue vetadas: 60–125 (ámbar/mostaza — la mostaza además vetada
  por decisión estética de Ivan) y 135–175 (reservada a `--signal`). El
  veto mostaza costó bajar la ΔE mínima de 15.9 a 13.0; aceptado.
- No hay "verde bosque" literal: la zona verde pertenece a `--signal`
  (semántico de estados vivos) y un verde de categoría a h=135 queda a
  ΔE 8.5 de signal — confundible en una app financiera.

La paleta es extensible a landing/blog por el mecanismo de promoción
estándar. El mapeo categoría→slot lo definirá `Category.color_slot`
(pendiente, ver deuda).

## Adaptaciones del sistema editorial a dashboard (material case study)

1. **Fondo sólido, no gradiente fijo.** El `background-attachment: fixed`
   del canónico es lenguaje de landing; en una lista con scroll infinito
   repinta constantemente y compite con los datos.
2. **`scroll-behavior: smooth` condicionado.** Interfiere con swaps de
   HTMX y con usuarios que pidieron menos movimiento; anulado bajo
   `prefers-reduced-motion`, junto con todas las transiciones.
3. **`a:hover { opacity: .82 }` anulado en controles.** Bajar opacidad a
   un control interactivo en dark lo hace parecer deshabilitado; chips y
   centinela hacen hover por color/borde.
4. **Ancho de contenido propio** (`--se-content-max: 640px`): una columna
   de datos, no el `--container` de 1100px de la landing.
5. **Cifras siempre `tabular-nums`** (regla dura de la fase), en Geist
   Mono weight 500, alineadas a la derecha en columna estable.
6. **Sin rojo destructivo.** Borrar es botón fantasma: el sistema no tiene
   token de peligro y la confirmación es la barrera real. Introducir un
   semántico nuevo requiere su propia discusión.
7. **Sin hover de fila.** La fila del ledger no navega; un highlight
   sugeriría interactividad que no existe.
8. **Ámbar como estado seleccionado** (chip activo) y como registro de
   aviso (franja 404 sobre `--mod-warm`): el acento único trabajando,
   nunca decorando.

## Accesibilidad (D5, medido)

- Contraste de texto: `--ink` 17.5:1, `--ink-2` 11.8:1, `--ink-3` 8.0:1
  sobre `--bg-solid`; `--amber` 9.6:1. `.aviso` sobre `--mod-warm`:
  15.5/8.5.
- **Hallazgo:** `--ink-4` da 4.36:1 sobre `--bg-solid` — falla AA para
  texto chico (4.5:1). El canónico no se toca; regla local del sistema:
  **`--ink-4`/`--ink-5` solo para texto ≥18px o elementos no textuales**
  (bordes hover: umbral UI 3:1, pasa). Tres usos corregidos a `--ink-3`.
- Foco visible ámbar en todos los interactivos, extendido a
  `select`/`input`.
- `prefers-reduced-motion` respetado (scroll y transiciones).
- Touch target del botón Borrar ≥44px por padding propio, sin inflar la
  densidad de fila (cómoda, 14px).

## A verificar en uso (decisiones reversibles de una línea)

- Tamaño del hero: activo `clamp(..., 4rem)`, alternativa 3rem comentada.
- Densidad de fila: cómoda (14px); compacta (10px) anotada.

## Deuda visual pendiente

1. **Colores de categoría en la lista**: requieren `Category.color_slot`
   (campo + migración) y envolver la categoría en su propio span en
   `_expense_items.html`. Las clases `.cat-1..6` ya están listas en CSS.
2. **`<dialog>` de confirmación de borrado** (hereda D5 de Fase C): el
   `hx-confirm` nativo funciona y es accesible; el dialog estilado es
   costo/beneficio bajo frente a lo pendiente. Implica template +
   atributos, no solo CSS.
3. **Separador de miles** (hereda D6 de Fase C): es template
   (`humanize`/filtro es-AR), no CSS. El hero display lo hace visible.
4. **Componentes sin tokenizar aún**: dialog, formularios de alta (no
   existen en el piloto), gráfico B3.5 (consumirá `--se-cat-*`).
5. **Candidata de refactor del canónico** (decisión de la landing, no de
   acá): separar `tokens.css` en tokens puros + `base.css`, para que los
   consumidores no hereden estilos de landing que luego pisan (hoy:
   override de `body { background }`).

## Nota de infraestructura (dev)

En dev los estáticos se sirven vía `staticfiles_urlpatterns()` (finders)
porque uvicorn no autoserve como runserver; servir desde `STATIC_ROOT`
exigía `collectstatic` en cada cambio. Prod sin cambios (nginx, ver
`static_files.md` — agregar esta nota ahí).

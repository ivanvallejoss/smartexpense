# Decisiones cerradas — canales, identidad y acceso

Documento vivo. Todo lo de acá se discutió con evidencia y está cerrado: **no se
reabre**. Si el código contradice algo de este documento, el código está viejo —
reportalo, no revises la decisión.

Lo que **no** está acá está abierto. La ausencia de una decisión no es permiso
para tomarla; ver "Qué NO decidir por tu cuenta" en `CLAUDE.md`.

---

## Identidad

**El `lid` es la clave canónica de WhatsApp.** Entra en el
`CharField(max_length=64)` de `ChannelIdentity.external_id` sin migración: ese
campo no tiene validators, ni regex, ni supuesto de formato telefónico.

**`phone` nunca participa del lookup de identidad.** Es evidencia para
reconciliar o para disparar una vinculación; nunca selecciona una fila. Dejarlo
participar volvería la clave no determinista — dependería de qué campos llegaron
en *ese* mensaje.

Neonize puede entregar cuatro combinaciones, y el diseño tiene que sobrevivir las
cuatro:

| `Sender` | `SenderAlt` | Situación | Clave |
|---|---|---|---|
| lid | phone | caso feliz | lid |
| lid | vacío | contacto no resuelto | lid |
| phone (modo PN) | lid | chat direccionado por teléfono | lid, desde `SenderAlt` |
| phone | vacío | sin lid disponible | **no hay clave canónica** |

El cuarto caso rompe la premisa y todavía no tiene resolución.

**`Expense.user` apunta a `User`, no a `ChannelIdentity`.** No se cambia. Toda la
capa de gastos, analytics y auth filtra por `User` y es agnóstica de canal.

**`User` ya es la entidad de convergencia.** `ChannelIdentity → User` es la
indirección que permite N canales por persona. No hace falta un nivel más: lo que
falta es la *operación* de vinculación, no la estructura.

---

## Normalización

**La normalización vive en el productor.** El worker nunca ve un payload crudo de
ningún canal. `ChannelEvent.from_dict()` lanza `TypeError` ante claves
desconocidas a propósito.

Matiz que hay que tener presente, porque el docstring viejo lo conflacionaba:
`multichannel_refactor.md` D6 sí contempla un **Bridge Python** que llama a
`normalize()`. Lo que no existe es un gateway Go llamándola — el ADR del gateway
decide que Go es platform-agnostic y reenvía el payload crudo.

Excepción viva: `process_telegram_message` en `apps/bot/worker.py` normaliza
payloads crudos. Es el alias deprecado de compatibilidad para jobs encolados
antes del deploy de la Fase 5, con remoción prevista.

---

## Grants

Un solo store en Redis, consumo con `GETDEL` — un solo uso por construcción.

**Abierto en canal.** Cualquier canal puede canjearlo; el canal consumidor se
registra solo para auditoría.

**Cerrado en propósito.** `web_access` y `channel_link` son propósitos distintos
con entropías distintas, y un grant de uno no se canjea en el otro. Propósito
equivocado = miss, igual que vencido. El motivo es de entropía: un código de seis
dígitos es aceptable para vincular un canal, pero como credencial web es débil —
si el propósito fuera abierto, la entropía del sistema quedaría fijada por el
transporte más pobre.

| | `web_access` | `channel_link` |
|---|---|---|
| Transporte | URL | 6 dígitos tipeados |
| Entropía | `secrets.token_urlsafe(32)` | 10⁶ |
| TTL | ~15 min | ~10 min |
| Canje | vista → `login()` → sesión | handler → `attach_identity_to_user` |

**Dirección: del canal establecido al canal nuevo.** El grant se emite donde la
identidad ya resuelve a un `User` y se consume donde todavía no. Es una propiedad
de **rol**, no de canal: ningún canal está cableado a un lado. Al revés, el
ataque es *"reenviale este código al bot"* y la víctima ejecuta la acción en el
canal en el que confía.

**El JWT sale.** Con consumo de un solo uso la firma no compra nada, y
`services/auth.py` es lo único que importa `jwt` en todo el repo. `issue_grant` lo
reemplaza y PyJWT deja de ser necesario.

**Tres relojes distintos, y un invariante:**

- TTL del grant → ventana de ataque. Parámetro de **seguridad**.
- TTL del estado de onboarding → memoria conversacional. Parámetro de **UX**.
- `TTL(estado) ≥ TTL(grant)`. Si el estado muere primero, el usuario vuelve con un
  código válido y el bot lo parsea como gasto.

El TTL también acota el tamaño del espacio de claves vivo: la entropía necesaria
escala con los grants concurrentes, no con los usuarios totales.

---

## Acceso web

**El magic link es la única puerta.** Sin contraseña, sin OAuth, sin registro
web. La sesión es una consecuencia, no un requisito de producto.

**El canje es POST, nunca GET.** Ver `docs/trampas.md`, sección de prefetch.

**Sesión deslizante:** `SESSION_COOKIE_AGE = 3 días` +
`SESSION_SAVE_EVERY_REQUEST = True`. Esa expiración es la única señal de
revocación que existe, porque no hay contraseña que cambiar.

Pendiente de la unidad correspondiente: `LOGIN_URL` apunta hoy a
`/admin/login/`, un formulario que ningún usuario del bot puede usar.

---

## Onboarding

**Estrategia: bifurcación explícita.** Ante una identidad desconocida en un canal
con la política encendida, el bot pregunta antes de crear nada.

Se descartaron:

- *Cuenta provisional* ("guest checkout") y *just-in-time*: las dos dejan que los
  datos diverjan antes de ofrecer la vinculación, y traen de vuelta el merge.
- *Nunca crear sin vincular*: rompe el onboarding de quien llega primero por
  WhatsApp.
- *Matching automático por atributo compartido*: da assurance falsa.

El eje que decide no es la elegancia sino **qué proporción de identidades nuevas
ya son usuarios existentes**. Hoy esa proporción es casi 1; en un lanzamiento
público se invierte. Por eso la política es un flag por canal, simétrico a
`NORMALIZERS` y `SENDERS`.

**El primer mensaje no se pierde.** Se guarda junto al estado de onboarding y se
reproduce cuando la identidad se resuelve. Si alguien escribe `cafe 2500` como
primer mensaje y recibe una pregunta, ese gasto no puede quedar en el aire.

**Consecuencia estructural:** `worker.py` crea el `User` **antes** de `dispatch()`,
así que la bifurcación vive en el worker, no en un handler. El estado pendiente va
en Redis con TTL — mismo patrón que `cat_state` en `apps/bot/state.py` — así que
no requiere cambio de esquema.

---

## Por qué la secuencia importa más que el diseño

Hoy hay **cero** `ChannelIdentity` de WhatsApp. Si la vinculación entra antes del
primer mensaje real de WhatsApp, no hay nada que fusionar nunca. Si WhatsApp sale
primero, se hereda una población de cuentas partidas y hay que construir una
máquina de merge que toca cuatro caminos de FK (`Expense`, `Category`,
`DeletedObject.deleted_by`, `CategorySuggestionFeedback`) más el `unique` de
`username`.

**Todo este arco existe para que ese merge no nazca.**

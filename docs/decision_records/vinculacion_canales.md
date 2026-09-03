# Vinculación de canales y acceso web — Decision Record

**Proyecto:** SmartExpense · **Fecha:** 2026-09-03 · **Base:** `2c297f8` (main)
**Alcance:** el arco de vinculación de identidades de canal y el acceso web. Fija
el *qué* y el *por qué*; el *cómo* es de las unidades 3 a 6b.
**Prerrequisito de:** unidades 3 a 6b.
**Reemplaza a:** `docs/decisiones_canales.md`, eliminado en esta unidad. Ese
documento registraba las mismas decisiones sin su fundamento y con una
enumeración de FK incorrecta (ver 2.2). Mantener los dos garantizaba deriva.

**Etiquetado:** DATO = verificado contra el repo en la fecha de arriba, con
archivo y línea. INFERENCIA = deducido de esos datos. SIN DATO = no verificado.

---

## 1. El problema

`get_or_create_user_by_channel` resuelve una identidad de canal a un `User`, y si
no la encuentra, crea uno.

**DATO** — `backend/services/identities.py:119-129`: el lookup filtra por
`(channel, external_id)`; si devuelve `None`, cae en
`_create_user_with_identity` (`:31-62`), que abre transacción y ejecuta
`User.objects.create` (`:50`) más el `ChannelIdentity` asociado (`:55-61`). No
hay rama intermedia.

La función no distingue dos preguntas que hoy parecen la misma:

- ¿Existe esta identidad de canal?
- ¿Existe la **persona** detrás de esta identidad, en algún otro canal?

Con un solo canal en producción las dos preguntas tienen la misma respuesta
siempre, y la confusión es literalmente invisible: si la identidad de Telegram no
está, la persona tampoco. Por eso la función es correcta hoy y va a estar
incorrecta el día que entre el segundo canal, sin que cambie una sola línea.

Ese día, cada persona que ya usa el bot por Telegram y escriba por WhatsApp nace
como un `User` distinto: gastos propios, categorías propias, papelera propia,
dashboard propio. Nadie lo reporta como bug — la cuenta "funciona". Simplemente
la persona tiene dos.

**DATO** — `backend/apps/bot/worker.py:69-75`: la creación ocurre **antes** de
`dispatch()` (`:87`). El `User` ya existe cuando el primer handler se ejecuta.
Esto es central para la sección 8: cualquier bifurcación tiene que vivir en el
worker, porque cuando un handler corre ya es tarde.

---

## 2. Por qué la secuencia importa más que el diseño

Un diseño de vinculación bueno implementado tarde es peor que uno mediocre
implementado a tiempo, y la razón es que el costo del retraso no es lineal: es
una población de datos partidos que hay que reunificar a mano.

### 2.1 Hoy no hay nada que fusionar

No hay ninguna `ChannelIdentity` de WhatsApp. Lo que se puede verificar en el
repo es algo más fuerte que un conteo: que la tabla **no puede** contener una
fila de WhatsApp por construcción.

**DATO** — el único escritor de `ChannelIdentity` en el camino de ingesta es
`_create_user_with_identity` (`backend/services/identities.py:55`), y el `channel`
que recibe viene de `canonical.channel` (`backend/apps/bot/worker.py:70`), es
decir del evento ya normalizado.

**DATO** — un evento solo existe si hay normalizador: `NORMALIZERS` contiene una
sola entrada, telegram (`backend/services/channels/registry.py:14-17`), y
`normalize()` lanza `UnknownChannel` para cualquier otro canal (`:28-34`). No
existe el paquete `services/channels/whatsapp/`.

**DATO** — no hay ruta HTTP por donde entre otro canal:
`backend/apps/bot/urls.py:11` (`telegram/webhook/`) y `:15` (alias legacy) son las
dos únicas, y las dos apuntan a la misma vista específica de Telegram.

**DATO** — `build_default_senders()` registra un solo sender, telegram
(`backend/services/channels/registry.py:38-47`).

**DATO** — el backfill histórico insertó exclusivamente `channel="telegram"`
(`backend/apps/core/migrations/0005_backfill_channel_identities.py:10,26`).

**INFERENCIA** — de los cinco datos anteriores: ninguna fila con
`channel="whatsapp"` pudo originarse en el código. El cero se sostiene.

**SIN DATO** — el conteo directo contra la base de producción no se corrió en
esta unidad: no hay base local (`backend/db.sqlite3` no existe; `DATABASE_URL`
cae al default sqlite en `backend/config/settings.py:38`). La afirmación queda
respaldada por la imposibilidad estructural, no por un `SELECT`.

**La consecuencia es la tesis de este documento:** si la vinculación entra antes
del primer mensaje real de WhatsApp, no hay nada que fusionar nunca. El merge no
se resuelve — no nace. Si WhatsApp sale primero, se hereda una población de
cuentas partidas y hay que construir la máquina de merge.

### 2.2 Qué costaría esa máquina

Enumerado leyendo `backend/apps/core/models.py`, no de memoria.

**FK directas a `User` (DATO):**

| Referencia | Línea | `on_delete` | Nota |
|---|---|---|---|
| `Category.user` | `:54-61` | CASCADE | nullable: `NULL` = categoría global |
| `Expense.user` | `:112-117` | CASCADE | |
| `DeletedObject.deleted_by` | `:244-250` | SET_NULL | papelera |
| `ChannelIdentity.user` | `:306-311` | CASCADE | la tabla del propio problema |

**Alcanzado de forma transitiva (DATO):** `CategorySuggestionFeedback`
(`:174-203`) **no tiene FK a `User`** — apunta a `Expense` (`:183-188`) y a
`Category` (`:189-195`, `:197-203`). Un merge lo afecta, pero por arrastre de sus
padres, no como camino propio. La distinción importa porque cambia qué se
reasigna y qué se recalcula.

**Superficies de unicidad que un merge rompe antes de tocar una FK (DATO):**

- `username` único, heredado de `AbstractUser` (`:12`). Dos cuentas de la misma
  persona tienen dos usernames válidos y uno tiene que morir.
- `User.telegram_id` con `unique=True` (`:18-24`). Campo deprecado y sin
  consumidor, pero la restricción sigue en la base.
- `unique_category_per_user` (`:83-89`). Dos usuarios con una categoría homónima
  —el caso esperable, no el raro: "Comida" en ambos lados— colisionan al
  fusionarse. No es reasignar una FK: es decidir qué categoría sobrevive y
  re-apuntar sus gastos.
- `unique_identity_per_channel` sobre `(channel, external_id)` (`:341-346`), que
  es lo que hace que el merge sea de `User` y no de identidades.

Esa última fila es la que convierte el trabajo de "reasignar cuatro FK" en un
procedimiento con criterio de resolución, ventana de inconsistencia y decisiones
irreversibles por cada par de cuentas. **Todo este arco existe para no
escribirlo.**

---

## 3. Identidad

### 3.1 El LID es la clave canónica de WhatsApp

**DATO** — `ChannelIdentity.external_id` es
`CharField(max_length=64)` sin validators, sin regex y sin supuesto de formato
telefónico (`backend/apps/core/models.py:318-321`). El LID entra sin migración.

El fundamento de que sea `CharField` y no un entero está escrito en el propio
modelo (`:288-291`): el denominador común entre canales es una cadena. Telegram
usa enteros, WhatsApp usa `xxxxxxxx@lid`. Tipar la columna al canal más específico
habría obligado a migrar el esquema en cada canal nuevo — exactamente el
acoplamiento que `ChannelIdentity` vino a romper cuando reemplazó a
`User.telegram_id`.

### 3.2 El teléfono es evidencia, no clave

**DATO** — el docstring del modelo ya lo registra
(`backend/apps/core/models.py:293-296`): el teléfono no vive en esta tabla y nunca
participa del lookup.

El argumento no es de privacidad ni de tamaño de columna. Es de **determinismo**.
Un mensaje entrante puede traer LID, teléfono, los dos o uno solo. Si el teléfono
pudiera seleccionar una fila, la clave de identidad dependería de qué campos
trajo *ese* mensaje en particular: el mismo remitente resolvería a una fila o a
otra según cómo el proveedor armó ese payload. Una clave que depende del
transporte no es una clave.

El segundo argumento es de duración: un número cambia de dueño, un LID no
(`:296`). Un teléfono reciclado haría que una persona nueva heredara los gastos de
otra — el peor fallo posible en este dominio, porque no da error: da datos ajenos
con apariencia de propios.

Lo que el teléfono sí hace es servir de evidencia para reconciliar cuentas o para
disparar una vinculación. La distinción es exacta: **puede motivar una acción,
nunca autorizarla.**

### 3.3 Los cuatro estados que el diseño tiene que sobrevivir

Neonize puede entregar cuatro combinaciones de `Sender` / `SenderAlt`:

| `Sender` | `SenderAlt` | Situación | Clave |
|---|---|---|---|
| lid | phone | caso feliz | lid |
| lid | vacío | contacto no resuelto | lid |
| phone (modo PN) | lid | chat direccionado por teléfono | lid, desde `SenderAlt` |
| phone | vacío | sin lid disponible | **no hay clave canónica** |

Los tres primeros casos convergen al mismo valor por rutas distintas, y eso es
precisamente lo que hace viable la regla de 3.2: el LID está disponible en todos,
solo cambia de qué campo se lee.

El cuarto rompe la premisa. **Queda abierto y declarado como tal** (sección 9) —
no tiene resolución y no se le inventa una acá. Lo que sí está decidido es que no
se resuelve degradando a teléfono: eso sería reintroducir la clave no
determinista por la puerta de atrás, y en el caso exacto en que menos información
hay para detectar el error.

### 3.4 `User` ya es la entidad de convergencia

**DATO** — `Expense.user` apunta a `User`
(`backend/apps/core/models.py:112-117`), no a `ChannelIdentity`. Toda la capa de
gastos, analytics y auth filtra por `User` y es agnóstica de canal —
`services/selectors.py` y `services/expenses.py` no saben por qué canal llegó
nadie.

`ChannelIdentity → User` es ya la indirección que permite N canales por persona.
No hace falta un nivel más de abstracción: lo que falta es la **operación** de
vinculación, no la estructura. Agregar una entidad "Persona" por encima de `User`
sería resolver con esquema un problema que es de procedimiento, y arrastraría la
migración de las cuatro FK de la sección 2.2 sin necesidad.

---

## 4. Quién normaliza

Había dos versiones circulando en `docs/`, y una era falsa. Esta es la buena.

**La normalización le pertenece al productor.** Quien recibe el payload crudo lo
normaliza y encola el evento canónico. El worker nunca ve un payload crudo de
ningún canal.

**DATO** — `backend/services/channels/registry.py:20-34` ya lo dice así, con el
matiz correcto: cuando aterrice v2, el productor será el **Bridge Python**,
porque el gateway Go es platform-agnostic y reenvía el payload sin tocarlo.
Normalizar sigue siendo trabajo del lado Python.

**DATO** — `multichannel_refactor.md:219-235` (D6) sostiene lo mismo desde antes:
el ADR 002 del gateway decide que Go es platform-agnostic, y por eso el Bridge es
quien llama `normalize()`. Los dos documentos coinciden; **no hay contradicción
entre este ADR y `multichannel_refactor.md`.**

Lo que era falso —y ya no existe en el repo— era la afirmación de que un gateway
**Go** llamaba a `normalize()`. Se corrigió en la unidad 2. Queda registrada acá
para que el próximo que encuentre la idea en un log de conversación sepa que fue
descartada, no olvidada.

El fundamento de fondo: `ChannelEvent.from_dict()` lanza `TypeError` ante claves
desconocidas a propósito (**DATO** —
`backend/services/channels/events.py:57-66`). Un worker que aceptara payloads
crudos no podría tener ese contrato, porque no habría un esquema único que
validar. La frontera de normalización es lo que hace que el evento canónico sea
verificable.

**Excepción viva (DATO):** `process_telegram_message`
(`backend/apps/bot/worker.py:113+`) normaliza payloads crudos. Es el alias
deprecado de compatibilidad para jobs encolados antes del deploy de la Fase 5,
con remoción prevista. Es deuda con fecha de vencimiento, no una segunda
arquitectura.

---

## 5. Grants

Un solo store en Redis, consumo con `GETDEL`. El un-solo-uso no es una validación
que alguien tenga que recordar escribir: es una propiedad de la operación de
lectura. Si el canje leyera y borrara en dos pasos, dos canjes concurrentes
podrían pasar los dos — el mismo error que ya se corrigió en la idempotencia del
webhook, donde el `GET` + `SET` no atómico se reemplazó por un `SET(nx=True)`
(`webhook_idempotency.md:98-101`). Acá se evita de entrada.

### 5.1 Abierto en canal

Cualquier canal puede canjear un grant; el canal consumidor se registra solo para
auditoría.

El motivo es que atar el grant a un canal de consumo no compra seguridad y sí
cuesta funcionalidad. No compra seguridad porque el secreto es el código: quien lo
tiene puede canjearlo, y exigir que lo haga desde un canal específico no agrega
una barrera que un atacante que ya tiene el código no pueda sortear. Y cuesta
funcionalidad porque el caso de uso natural —vincular un canal nuevo— es
justamente aquel en el que el canal de consumo todavía no está asociado a nadie.

### 5.2 Cerrado en propósito

`web_access` y `channel_link` son propósitos distintos y un grant de uno no se
canjea en el otro. Propósito equivocado = miss, igual que vencido.

| | `web_access` | `channel_link` |
|---|---|---|
| Transporte | URL | 6 dígitos tipeados |
| Entropía | `secrets.token_urlsafe(32)` | 10⁶ |
| TTL | ~15 min | ~10 min |
| Canje | vista → sesión | handler → vinculación de identidad |

El argumento es de **entropía**, y es el que explica por qué esta cerradura sí y
la del canal no. Un código de seis dígitos es aceptable para vincular un canal:
se tipea a mano, y el TTL corto más el espacio de claves vivo lo acotan. Como
credencial web es débil. Si el propósito fuera abierto, un código de seis dígitos
emitido para vincular serviría para abrir el dashboard, y **la entropía efectiva
del sistema quedaría fijada por su transporte más pobre**. El propósito cerrado es
lo que permite tener dos niveles de entropía sin que el más bajo contamine al más
alto.

Corolario de diseño: cada propósito nuevo trae su propia decisión de entropía. No
se hereda.

### 5.3 Dirección: del canal establecido al nuevo

El grant se emite donde la identidad ya resuelve a un `User`, y se consume donde
todavía no.

Es una propiedad de **rol**, no de canal: ningún canal está cableado a un lado.
Telegram no es "el emisor" ni WhatsApp "el receptor" — lo que define el rol es
cuál de las dos identidades ya está resuelta en ese momento.

El argumento de seguridad es un ataque concreto. Si el grant se emitiera en el
canal nuevo, el ataque es *"reenviale este código al bot"*: el atacante consigue
un código en su propio canal y convence a la víctima de canjearlo. La víctima
ejecuta la acción **en el canal en el que confía**, con el aspecto de una
operación legítima, y el resultado es que la cuenta de la víctima queda vinculada
a una identidad del atacante. Con la dirección invertida el ataque no se arma: el
código nace del lado de quien ya está autenticado, y quien lo canjea es quien
tiene que probar algo, no quien ya lo probó.

### 5.4 El JWT sale

**DATO** — `backend/services/auth.py` es el único módulo de producción que
importa `jwt` (`:5`); el resto de las apariciones son tests
(`backend/tests/services/test_services_auth.py`). `PyJWT==2.10.1` está en
`backend/requirements.txt:7` sostenido por ese único consumidor.

**DATO** — `generate_magic_link_token` no tiene consumidor en producción:
`link_command` está deshabilitado y su docstring lo explica
(`backend/apps/bot/handlers/handlers.py:139-158`) — el magic link apuntaba al
frontend React, abandonado junto con la API JSON que validaba el token.

Con consumo de un solo uso, la firma no compra nada. Un JWT resuelve el problema
de verificar un token **sin estado compartido**; acá el estado compartido es
obligatorio, porque el `GETDEL` es lo que garantiza el uso único. Teniendo que ir
a Redis igual, firmar es criptografía que se paga y no se usa: la existencia de la
clave en el store ya es la prueba de validez, y su ausencia la prueba de que
venció o se usó.

El beneficio colateral es que la dependencia se va con el último consumidor.
**INFERENCIA** — al reemplazar `services/auth.py` por la emisión de grants, PyJWT
deja de ser necesario.

---

## 6. Los tres relojes

Hay tres TTL en juego y confundirlos es lo que produce bugs que parecen de UX y
son de seguridad, o al revés.

1. **TTL del grant** → define la ventana de ataque. Parámetro de **seguridad**.
   Se elige por cuánto tiempo se tolera que un código robado siga sirviendo.
2. **TTL del estado de onboarding** → define la memoria conversacional. Parámetro
   de **UX**. Se elige por cuánto tarda una persona en contestarle a un bot.
3. **TTL de idempotencia** → ya existe y es independiente de los dos anteriores;
   se elige por el techo de reintentos del canal (**DATO** —
   `webhook_idempotency.md:41-46`, 24h por el máximo de Telegram).

**El invariante: `TTL(estado) ≥ TTL(grant)`.**

El fundamento es la falla concreta que evita. Si el estado muere primero, el
usuario vuelve con un código todavía válido y el bot ya no recuerda que estaba
esperando un código — así que lo parsea como lo que parsea todo texto suelto: un
gasto. Un código de seis dígitos como monto. El grant sigue vivo, sin nadie
esperándolo, y la persona recibe la confirmación de un gasto que no hizo.

Que los dos números vengan de razonamientos distintos —seguridad y UX— es
justamente por qué el invariante hay que escribirlo: nada en el proceso de elegir
cada uno por separado garantiza la relación entre ellos.

**DATO** — el patrón de estado con TTL en Redis ya existe y no requiere cambio de
esquema: `STATE_TTL = 300` en `backend/apps/bot/state.py:14`, con claves
namespaceadas por canal (`:19-20`) precisamente para que dos usuarios con el mismo
id nativo en canales distintos no compartan estado.

**DATO** — las particiones de Redis por propósito están definidas en
`backend/services/infrastructure/redis_client.py:26-30` (jobs=0, state=1,
cache=2).

Nota de dimensionamiento: el TTL también acota el tamaño del espacio de claves
vivo. La entropía necesaria escala con los **grants concurrentes**, no con los
usuarios totales — por eso 10⁶ es defendible para `channel_link` a esta escala, y
por eso ese razonamiento hay que rehacerlo si la escala cambia.

---

## 7. Acceso web

### 7.1 El magic link es la única puerta

Sin contraseña, sin OAuth, sin registro web.

El fundamento es que el producto ya tiene un canal autenticado. La persona
demostró quién es cuando le escribió al bot; pedirle además una contraseña es
agregar un secreto nuevo, con su recuperación, su rotación y su superficie de
fuga, para probar algo que ya está probado. OAuth agrega un tercero y un flujo de
consentimiento por el mismo motivo nulo.

**La sesión es una consecuencia, no un requisito de producto.** Nadie pidió
"quiero una cuenta web": pidieron ver sus gastos en una pantalla más grande. La
sesión existe porque HTTP no recuerda, no porque el producto la haya querido.

### 7.2 El canje es POST, nunca GET

**DATO** — `docs/trampas.md:86-93`: Telegram y WhatsApp hacen un GET a cualquier
link que se mande, para armar la preview.

Un endpoint de magic link que consuma el token en el GET queda consumido por el
crawler del propio canal antes de que el humano toque nada. Y por 5.1, el consumo
es un `GETDEL`: cuando la persona hace clic, el código ya no existe. El síntoma
sería "el magic link nunca funciona", y la causa no estaría en el código de auth.

Por eso el GET renderiza una página con un botón y el POST consume. **DATO** — el
protocolo `Sender` ya expone `disable_preview` por la misma razón
(`backend/services/channels/senders.py:59-70`), y su docstring registra que los
canales sin ese concepto lo ignoran en silencio.

Esta es una trampa que solo se descubre en producción y con un canal real. Está
escrita antes de implementar para que no haya que descubrirla.

### 7.3 Sesión deslizante

`SESSION_COOKIE_AGE = 3 días` + `SESSION_SAVE_EVERY_REQUEST = True`.

El fundamento del deslizamiento es que la expiración es la **única señal de
revocación que existe**: no hay contraseña que cambiar ni sesión que invalidar
desde ningún lado. Una expiración absoluta obligaría a re-canjear un magic link
cada tres días incluso a quien usa el dashboard todos los días; una expiración
que no expira nunca dejaría una cookie robada válida para siempre. El
deslizamiento hace que el reloj mida lo que importa: tiempo sin uso.

Corolario: mientras el magic link no exista, el único login web es el del admin
—un formulario que ningún usuario del bot puede usar, porque ningún usuario del
bot tiene contraseña—. **DATO** — está asumido explícitamente como break-glass en
`backend/config/settings.py:89-91`.

---

## 8. Onboarding

### 8.1 Estrategia: bifurcación explícita

Ante una identidad desconocida en un canal con la política encendida, el bot
**pregunta antes de crear nada**.

Se descartaron tres alternativas, y el motivo de cada una es distinto:

- **Cuenta provisional ("guest checkout") y just-in-time.** Las dos crean el
  `User` y ofrecen la vinculación después. El problema no es la fricción: es que
  entre la creación y la vinculación los datos **divergen**. Cuando la persona
  acepta vincular, ya hay gastos en las dos cuentas — y eso es exactamente la
  máquina de merge de la sección 2.2, que es el costo que todo este arco existe
  para evitar. Descartadas por reintroducir el problema que resuelven.

- **Nunca crear sin vincular.** Elimina la divergencia por construcción, pero
  rompe el onboarding de quien llega primero por WhatsApp: sin cuenta previa no
  hay nada a lo que vincularse, así que la primera persona que use el canal nuevo
  queda sin poder empezar. Descartada por cerrarle la puerta al usuario nuevo para
  proteger al existente.

- **Matching automático por atributo compartido** (nombre, teléfono, lo que sea).
  Es la única que no molesta a nadie, y es la peor: da **assurance falsa**. Une
  cuentas sin que ninguna de las dos partes lo confirme, y cuando se equivoca no
  falla — entrega los gastos de otra persona con apariencia de propios. Es la
  misma clase de error que 3.2 rechaza para el teléfono, aplicada al nivel de la
  cuenta entera.

### 8.2 El eje real de la decisión

Lo que decide entre bifurcar y no bifurcar no es la elegancia del flujo: es **qué
proporción de identidades nuevas ya son usuarios existentes**.

Hoy esa proporción es casi 1 — todos los que van a escribir por WhatsApp ya usan
Telegram, y preguntar acierta casi siempre. En un lanzamiento público se invierte:
la mayoría de las identidades nuevas son personas nuevas, y preguntarle a cada
una si ya tiene cuenta es fricción pura en el peor momento posible.

Por eso la política **no es una constante del sistema sino un flag por canal**,
simétrico a `NORMALIZERS` y `SENDERS` (**DATO** — el patrón de registro por canal
ya existe: `backend/services/channels/registry.py:14-17` y `:38-47`). La misma
pregunta tiene respuestas distintas para Telegram y para WhatsApp, y las va a
tener otra vez cuando la proporción cambie. Cablear la decisión sería tener que
rediscutirla en código.

### 8.3 El primer mensaje no se pierde

Se guarda junto al estado de onboarding y se reproduce cuando la identidad se
resuelve.

El fundamento es la escena concreta: alguien escribe `cafe 2500` como primer
mensaje y recibe una pregunta sobre vinculación de cuentas. Si ese gasto se
descarta, el primer contacto de la persona con el producto es que el producto no
hizo lo único que hace. En un registrador de gastos personales, perder el dato es
peor que cualquier fricción de onboarding: el gasto ya ocurrió en el mundo, y
pedirle a la persona que lo vuelva a tipear es pedirle que confíe en que esta vez
sí.

### 8.4 Consecuencia estructural

**DATO** — `backend/apps/bot/worker.py:69-75` crea el `User` antes de `dispatch()`
(`:87`).

Por lo tanto la bifurcación vive en el **worker**, no en un handler. Cuando un
handler corre, el `User` ya existe y la decisión ya se tomó — un handler no puede
implementar una política sobre algo que sucedió antes de que él existiera. Esto no
es una preferencia de diseño: es la lectura del orden actual del pipeline.

El estado pendiente va en Redis con TTL, mismo patrón que `cat_state`
(`backend/apps/bot/state.py:14,19-20`), así que **no requiere cambio de esquema**.
Es deliberado: una tabla de onboardings pendientes agregaría una migración, una
FK más a la lista de 2.2 y un ciclo de vida que habría que limpiar a mano. El TTL
lo limpia solo.

---

## 9. Qué queda explícitamente abierto

Una sola cosa, y es una decisión no tomada — no una decisión tomada sin
construir. Lo segundo vive en `docs/plan_unidades.md`, que es documento vivo y
puede dejar de ser cierto cuando se implemente; este registro no.

**El cuarto estado `Sender`/`SenderAlt`: teléfono sin LID** (sección 3.3).

No hay clave canónica y no hay resolución. El diseño de las secciones 3.1 y 3.2
depende de que el LID esté disponible en alguno de los dos campos, y este caso es
el único en que no lo está. Lo único cerrado es que no se resuelve degradando a
teléfono, por lo argumentado en 3.2.

**SIN DATO** — con qué frecuencia ocurre en la práctica. Neonize lo declara
posible; no hay medición contra tráfico real, y no puede haberla hasta que
WhatsApp exista. Esa frecuencia es lo que debería decidir si el caso se resuelve
o se rechaza con un mensaje al usuario.

---

## 10. Relacionados

- `multichannel_refactor.md` — D6 (quién normaliza), el contrato de
  `ChannelEvent` y el protocolo `Sender`. Coincide con la sección 4.
- `multichannel_webhook_routing.md` — por qué la ruta lleva el canal en el path.
- `webhook_idempotency.md` — el precedente de atomicidad citado en 5.1 y el TTL
  de idempotencia de la sección 6.
- `docs/trampas.md` — prefetch de preview (7.2).
- `docs/plan_unidades.md` — el orden de las unidades que implementan esto, y la
  deuda decidida pendiente de construcción.

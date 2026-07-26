# Refactor Multi-Canal — Cierre de Sesión

**Estado:** completado
**Alcance:** desacoplar el pipeline de Telegram. Telegram queda como única
implementación, funcionando idéntico a antes.
**Fuera de alcance:** WhatsApp. Este documento es el insumo de esa ventana.

---

## 1. Checklist del contrato

### Punto 1 — Evento canónico

**Estado: cumplido con superset aditivo.**

Los seis campos del contrato están, con los mismos nombres y tipos:

```python
{
    "channel": "telegram",
    "external_user_id": "7721833653",
    "text": "cafe 2500",
    "message_id": "422661426",
    "timestamp": 1753440000,
    "raw": { ... },
}
```

Se agregaron cinco campos. Ninguno rompe lo que la otra ventana ya asume:

| Campo | Tipo | Por qué existe |
| --- | --- | --- |
| `type` | `"message"` \| `"callback"` | Sin esto un click de botón no tiene representación. Los caminos de confianza media y baja dependen de botones |
| `conversation_id` | `str` | Destino de respuesta. Sin esto, un mensaje de grupo recibe la respuesta por privado |
| `edit_ref` | `str \| None` | Handle opaco del mensaje a editar. El worker lo recibe y lo devuelve sin leerlo |
| `ack_ref` | `str \| None` | Handle opaco para acusar recibo de una acción |
| `profile` | `dict` | `{username, first_name, last_name}`. Alimenta la resolución de identidad |

`edit_ref` y `ack_ref` son deliberadamente opacos: el worker nunca los parsea.
Eso permitió mantener la firma `reply(external_user_id, text)` del contrato
en vez de pasarle el evento entero al sender.

**`message_id` cambió de semántica** respecto del contrato. Ver desviación D2.

Definido en `services/channels/events.py`.

### Punto 2 — Task única

**Estado: cumplido.**

`process_message(ctx, event: dict)` en `apps/bot/worker.py`. La normalización
vive en el productor; el worker nunca ve un payload crudo de ningún canal.

Convive temporalmente `process_telegram_message`, un alias deprecado que
normaliza payloads crudos, para los jobs encolados antes del deploy. Se
elimina en el deploy siguiente.

### Punto 3 — ChannelIdentity

**Estado: cumplido.**

`apps/core/models.py`. FK a `User`, campos `channel` y `external_id`,
unicidad garantizada sobre `(channel, external_id)`.

Migración `0004_channelidentity` (esquema) y `0005_backfill_channel_identities`
(datos, reversible). Backfill verificado: 1 usuario, 1 identidad, 0 huérfanos.
Rollback probado en ambas direcciones.

Se usa `UniqueConstraint` en vez de `unique_together` — equivalente moderno y
consistente con `Category` en el mismo archivo. La garantía es idéntica.

`User.telegram_id` **no se eliminó**: `services/auth.py` lo firma como `sub`
del JWT del magic link y `apps/api/auth.py` lo resuelve. Se escribe en
paralelo para el canal Telegram. Migrar auth a `User.id` es trabajo aparte.

### Punto 4 — Dispatcher de respuesta

**Estado: cumplido con superset aditivo.**

`SENDERS: dict[str, Sender]` en `services/channels/senders.py`, poblado en el
arranque del worker vía `build_default_senders()`.

`reply(external_user_id, text)` mantiene exactamente la firma del contrato.
Los parámetros extra son keyword-only con default. Se agregaron dos verbos
que el contrato no contemplaba y sin los cuales no hay paridad:

| Verbo | Usos en el código real |
| --- | --- |
| `reply` | 8 llamadas, con y sin botones, dos con `parse_mode="HTML"` |
| `edit` | 6 ediciones de texto + 1 que cambia solo los botones conservando el texto |
| `ack` | mudo, con toast, y con alerta |

Sin `ack`, Telegram deja el spinner del botón girando en cada click.
Sin `edit`, los flujos de categorización mandan mensajes nuevos en vez de
editar el existente.

### Punto 5 — Idempotencia

**Estado: cumplido, con una segunda capa que el contrato no pedía.**

`_job_id=f"{channel}:{message_id}"` según contrato. Verificado en runtime:
las claves de resultado aparecen como `arq:result:telegram:422661426`.

Se conservó además la clave explícita con TTL de 24hs, porque **`_job_id`
solo no alcanza**. Verificado contra el source de arq 0.27/0.28:

- `enqueue_job` hace `WATCH` + `exists(job_key, result_key)` en una
  transacción y retorna `None` si el id ya existe. Es atómico.
- Pero su ventana es `keep_result`, que por default son **3600 segundos**.
  Telegram reintenta hasta 24 horas.

| Capa | Ventana | Cubre |
| --- | --- | --- |
| Clave explícita | 24h | Reentrega tardía |
| `_job_id` | ~1h | Reentrega inmediata, atómicamente |

La clave pasó de `processed_updated:{update_id}` en db0 a
`idempotency:{channel}:{message_id}` en db2, alineándose con el esquema de
particionado y con el ADR 003 del gateway Go. El `GET`+`SET` no atómico se
reemplazó por `SET(nx=True, ex=TTL)`, cerrando una carrera entre entregas
simultáneas.

### Punto 6 — Estado conversacional

**Estado: cumplido con formato distinto al contrato.** Ver desviación D8.

`cat_state:{channel}:{external_user_id}` en db1. Verificado en vivo:

``` python
"SET"  "cat_state:telegram:7721833653" "92" "EX" "300"
"MGET" "cat_state:telegram:7721833653" "cat_state:7721833653"
"DEL"  "cat_state:telegram:7721833653" "cat_state:7721833653"
```

Compatibilidad por lectura dual en un solo `MGET` — sin round-trip extra en
el camino caliente. No hubo migración de datos: con TTL de 5 minutos, el
formato viejo se extingue solo. Se elimina el fallback en un release.

---

## 2. Restricciones

| Restricción | Estado |
| --- | --- |
| No tocar parseo ni categorización | Cumplido. `services/parser/` y `services/ml/` sin un solo cambio |
| Cero cambio de comportamiento visible | Cumplido salvo D11 (texto de un mensaje de error) |
| Tests existentes pasan | Cumplido. Los de `tests/bot/` se reescribieron porque cambiaron las firmas; la cobertura se conservó o amplió |
| Tests nuevos: normalizador, dispatcher, resolución de usuario | Cumplido, más router de despacho y semántica de errores del worker |
| Commits particionados | Cumplido, 8 commits |

### Commits

| # | Alcance |
| --- | --- |
| 1 | `ChannelIdentity` + migración + backfill |
| 2 | Evento canónico + normalizador Telegram |
| 3 | Registro `SENDERS` + adapter de salida |
| 4a | Handlers desacoplados de PTB |
| 4b | `process_message` + router propio |
| 4c | Estado conversacional namespaced |
| 5 | Corte del webhook |
| 6 | Limpieza de código muerto |

Las fases 1 a 3 son puramente aditivas: nada las llama, suite verde, riesgo
cero. La 4a es la única no desplegable por sí sola — deja las importaciones
rotas hasta la 4b.

---

## 3. Desviaciones

### D1 — PTB era el router, no un cliente

`ptb_app.process_update()` ruteaba todo vía `CommandHandler`,
`MessageHandler` y `CallbackQueryHandler`. Cumplir el contrato exigió
escribir un router propio, manejo de errores propio, y reescribir 6 handlers
y 6 callbacks.

PTB sobrevive **solo como cliente HTTP de la API de Telegram**, encapsulado
en `services/channels/telegram/outbound.py`. Ningún otro módulo lo importa.
`apps/bot/setup.py` se eliminó.

### D2 — `message_id` no es el `message_id` de Telegram

El contrato define `message_id` como "id nativo del canal". En Telegram,
`message.message_id` es único **por chat**, no globalmente: `telegram:293`
colisionaría entre chats distintos.

`message_id` es el `update_id`, que sí es único global por bot. El
`message.message_id` nativo sigue accesible vía `raw` y vía `edit_ref`.

**Para WhatsApp:** `wamid` ya es globalmente único y encaja directo. La
definición operativa es "identificador de entrega único por canal".

### D3 — `external_user_id` es `from.id`, no `chat.id`

El contrato dice `chat.id`. Se usa `from.id` por dos razones:

1. Todo el código previo resolvía por `effective_user.id`, y el backfill de
   `ChannelIdentity` sale de `User.telegram_id`, que **es** `from.id`. Con
   `chat.id` la migración de datos era imposible: no existe ese valor en la base.
2. Identidad y destino son conceptos distintos que solo coinciden por
   accidente en chats privados.

El destino viaja en `conversation_id`, con default a `external_user_id`.

**Para WhatsApp:** `wa_id` cumple los dos roles; `conversation_id` queda inerte.

### D4 — `_job_id` no reemplaza la idempotencia explícita

Ver punto 5 del checklist. Ambas capas conviven por diferencia de ventana.

### D5 — Botones y clicks no entraban en el contrato

`Sender.reply(external_user_id, text)` no puede expresar botones ni edición,
y el evento canónico no tenía forma de representar un click. Resuelto con
superset aditivo (`type` en el evento, `options`/`edit_ref` en el sender).

### D6 — El normalizador no vive en el webhook

El contrato dice que la normalización vive en el productor. Pero el ADR 002
del gateway Go decide que Go es platform-agnostic y reenvía el payload crudo:
cuando v2 aterrice, quien normaliza es el **Bridge Python**.

Por eso `services/channels/` es un paquete agnóstico de Django views y de
todo SDK de mensajería. Verificado:

```python
import services.channels.registry
assert "telegram" not in sys.modules
assert "django.http" not in sys.modules
```

El Bridge llamará `normalize(envelope["source"], envelope["payload"])` y
`enqueue_job("process_message", event.to_dict(), _job_id=job_id_for(event))`.

### D7 — La idempotencia estaba en db0

Movida a db2. Ver punto 5.

### D8 — El estado usa el nombre completo del canal

El contrato dice `tg:{chat_id}`. Se usa `cat_state:{channel}:{external_user_id}`:

- `telegram` ya es el identificador de canal en `SENDERS`, `job_id_for` y
  `idempotency:*`. Un código corto `tg` crea un segundo vocabulario y una
  tabla de equivalencias que mantener.
- El prefijo `cat_state:` permite que db1 aloje otros tipos de estado.
- Es `external_user_id`, no `chat_id`: el flujo de categoría pendiente le
  pertenece a la persona. Mismo criterio que D3.

### D9 — El nombre de la task rompía los jobs en vuelo

Mitigado con el alias deprecado `process_telegram_message`.

### D10 — `parse_mode` es una fuga de vocabulario de Telegram

Es el único parámetro no neutral del `Sender`. Se dejó así a propósito: la
alternativa era un tipo `RichText` con renderizado por canal, sobre-ingeniería
para dos llamadas.

**Costo para la ventana de WhatsApp:** `format_expense_list` emite `<code>`,
`<b>`, `<i>`, y `link_command` emite `<a href="...">`. WhatsApp no renderiza
nada de eso — usa `*negrita*`, `_cursiva_`, y autolinkea URLs crudas. **Esos
dos textos necesitan una versión por canal.** Están localizados en
`apps/bot/utils.py`.

### D11 — Único cambio visible de comportamiento

Si la resolución de identidad falla durante un mensaje de texto, el usuario
ve "Ocurrió un error al procesar tu mensaje" en vez de "Ocurrió un error al
guardar tu gasto". Antes esa resolución vivía dentro de `handle_message` y la
atrapaba su propio `except`; ahora vive en el router.

Solo difiere el texto, solo en un camino de fallo.

### D12 — Semántica de reintentos, explicitada

`docs/decision_records/arq_retry.md` describía reintentos que en la práctica
no ocurrían: el `error_handler` de PTB atrapaba toda excepción de handler y no
la re-lanzaba, con lo cual el `raise` del worker era inalcanzable.

Al sacar PTB hubo que decidirlo explícitamente. Los reintentos se partieron
según si hubo efectos laterales:

- **Antes del dispatch** (parseo, lookup del sender, resolución de identidad):
  nada se escribió. La excepción se propaga y ARQ reintenta.
- **Dentro del dispatch**: el handler pudo haber creado un `Expense` antes de
  fallar. Reintentar lo duplicaría. La excepción se absorbe, se loguea
  completa y se le avisa al usuario.

Es el mismo razonamiento con el que ese ADR rechazó la DLQ — la task no es
idempotente — aplicado consistentemente. El ADR quedó enmendado.

### D13 — Bug preexistente preservado

`history_command` manda **dos** mensajes cuando no hay gastos: falta un
`return`. Se preservó deliberadamente; arreglarlo violaba "cero cambio
visible" y contaminaba el diff. Va en un commit propio.

### D14 — `link_command` sigue atado a Telegram

El JWT del magic link usa `User.telegram_id` como `sub`. Un usuario sin
`telegram_id` no puede generar link. Hay un guard que hoy es inalcanzable y
responde "El acceso al dashboard todavía no está disponible en este canal".

**Bloqueante para WhatsApp** si se quiere paridad de features. Requiere
migrar el esquema de auth a `User.id`.

---

## 4. Verificación

**Suite:** verde. 192 tests antes del corte, con `tests/bot/` reescrito y
`tests/channels/` agregado.

**E2E manual sobre Telegram**, con webhook real vía ngrok:

| Verificación | Resultado |
| --- | --- |
| Gasto de confianza alta | Guardado + botón Eliminar |
| Botones Eliminar / Deshacer | Editan el mensaje original |
| Confianza media → Cambiar | Cambian los botones, el texto se conserva |
| Nueva categoría | Estado en db1 con clave namespaced, flujo callback → mensaje |
| `/stats`, `/history 3`, `/link` | Correctos, argumentos parseados |
| Comando inexistente | Silencio, igual que PTB |
| Foto / sticker | Descartado en el webhook, sin tocar Redis |

**Evidencia en Redis** (`localhost:6389`):

- db0: `arq:result:telegram:{update_id}` — job ids legibles
- db1: `cat_state:telegram:{id}`, TTL 300, `MGET` de un round-trip, `DEL` de ambos formatos
- db2: `idempotency:telegram:{update_id}`, TTL ~86400
- **Hueco en la numeración**: falta `...422` en db0 y db2 a la vez, exactamente
  el update no procesable. El filtro cortó antes de tocar Redis.

---

## 5. Qué necesita saber la ventana de WhatsApp

**Agregar un canal son cuatro archivos y ninguna modificación al worker:**

1. `services/channels/whatsapp/__init__.py` — `CHANNEL = "whatsapp"`
2. `services/channels/whatsapp/inbound.py` — `normalize(payload) -> ChannelEvent | None`
3. `services/channels/whatsapp/outbound.py` — clase con `reply`, `edit`, `ack`, `startup`, `shutdown`
4. Dos líneas en `services/channels/registry.py`: una en `NORMALIZERS`, otra en `build_default_senders()`

El webhook de WhatsApp es propio, pero solo valida firma y llama
`normalize(...)` + `enqueue_job("process_message", ...)`.

**Cuatro problemas conocidos que la abstracción expone en vez de esconder:**

1. **Límite de botones.** Telegram permite N botones inline. WhatsApp: 3
   botones, o listas de 10 por sección. `category_selection_options` emite N
   categorías + "Nueva categoría" y revienta ese límite. El `Sender` debe
   levantar `OptionsNotSupported`, nunca truncar en silencio.
2. **No existe `edit`.** WhatsApp no puede editar un mensaje enviado. El
   adapter tiene que emular mandando uno nuevo. Es una degradación aceptable
   pero visible.
3. **No existe `ack`.** Debe ser no-op. Nunca puede propagar excepción.
4. **HTML.** Ver D10.

**Contratos que no hay que romper:**

- `Option.id` vuelve como `event.text` cuando el usuario elige. El formato
  `"accion:payload"` lo consume `CALLBACK_ROUTES` sin cambios.
- El layout de filas es explícito: `grid(cats, 2) + row(nueva)`. Aplanarlo
  cambia la disposición visible.
- `message_id` debe ser único global por canal, o la idempotencia falla.

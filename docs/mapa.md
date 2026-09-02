# Mapa del repo

Documento vivo. Para orientarse rápido antes de explorar.

```
backend/
  apps/
    bot/          ingesta y despacho de mensajes
      views.py        webhook: verifica, normaliza, idempotencia, encola
      worker.py       worker ARQ: resuelve identidad y despacha
      dispatcher.py   rutea evento canónico → handler
      routing.py      tablas de comandos y callbacks
      state.py        estado conversacional en Redis, con TTL
      handlers/       comandos, mensajes de texto, callbacks
    core/         models.py — User extendido, ChannelIdentity, Expense, Category
    web/          dashboard SSR (views async)
  config/         settings.py, urls.py
  services/
    channels/     abstracción de canal — leer antes de tocar nada de canales
      events.py       ChannelEvent, el DTO canónico
      registry.py     NORMALIZERS por canal
      senders.py      protocolo Sender, Option/Rows
      telegram/       inbound.py (normalizador), outbound.py (sender)
    identities.py resolución de identidad de canal → User
    auth.py       emisión de tokens
    selectors.py  lecturas para dashboard y comandos
    expenses.py   escrituras de gasto
    parser/       parseo de texto libre a gasto
    ml/           categorizador
    infrastructure/redis_client.py   pools por propósito
  tests/          espeja la estructura de backend/
docs/
  decision_records/   ADRs — registros fechados, no se reescriben
  mapa.md             este archivo
  trampas.md          trampas conocidas del entorno
  decisiones_canales.md   decisiones cerradas de canales e identidad
  plan_unidades.md    plan de trabajo en curso
```

---

## El flujo de un mensaje, de punta a punta

```
webhook (apps/bot/views.py)
  → normalize()                   ← la normalización vive acá, en el productor
  → ChannelEvent                  ← DTO canónico
  → idempotencia: SET NX idempotency:{channel}:{message_id}, TTL 24h
  → enqueue_job con _job_id = f"{channel}:{message_id}"
        ↓  cola ARQ sobre Redis
  worker (apps/bot/worker.py)
  → ChannelEvent.from_dict()      ← lanza TypeError ante claves desconocidas
  → get_sender(channel)
  → get_or_create_user_by_channel()
  → dispatch()                    ← apps/bot/dispatcher.py
  → handler                       ← apps/bot/handlers/
```

**Dónde vive cada responsabilidad:**

- **Normalizar** — en el productor. Nunca en el worker.
- **Idempotencia** — en el productor, antes de encolar. `SET NX` con TTL de 24h.
- **Resolver identidad** — en el worker, antes de despachar.
- **Estado conversacional** — Redis, con TTL, claves scopeadas por canal.
- **Reglas de negocio** — `services/`, agnósticas de canal.

---

## Notas de estructura

`dispatcher.py` vive separado de `routing.py` para evitar un ciclo de imports.
Está documentado en su docstring; no los unifiques.

El protocolo `Sender` es `@runtime_checkable`, pero eso solo verifica presencia
de métodos, nunca firmas. No hay chequeo estático que atrape un cambio de firma.

Los canales que no soportan un concepto lo ignoran en silencio en vez de fallar
—`ack()` en canales sin acuse, `disable_preview` donde no hay preview, `edit()`
emulado con un mensaje nuevo. Ese es el criterio del protocolo.

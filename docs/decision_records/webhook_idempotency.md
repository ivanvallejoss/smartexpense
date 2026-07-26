# Webhook Idempotency — Decision Record

## Problem

Telegram may deliver the same webhook multiple times if it doesn't receive
a `200 OK` in time. Without idempotency, each redelivery creates a new job
in Redis and potentially a duplicate expense for the user.
Telegram → webhook → Redis (job A, update_id: 99)
Telegram → webhook → Redis (job B, update_id: 99)  ← duplicate on timeout

ARQ also guarantees at-least-once delivery — if the worker crashes after
processing but before acknowledging, the job is re-enqueued. This is a second,
independent source of duplicates.

## Defense Layers

The problem has two distinct origins requiring separate solutions:

| Source | Frequency | Solution |
| --- | --- | --- |
| Telegram webhook redelivery | High (network timeouts) | Idempotency at webhook level |
| ARQ re-enqueue on worker crash | Low (production crash) | Documented in [ARQ RETRY](arq_retry.md) |

The webhook defense was implemented first — it covers the most frequent case
and the most impactful one for real users.

## Implementation

### Idempotency key

`update_id` from Telegram is used as the idempotency key. Telegram guarantees
each update has a unique, sequential `update_id` — it never repeats across
different messages.

```python
idempotency_key = f"processed_update:{update_id}"
```

### 24-hour TTL

Telegram retries webhook delivery for a maximum of 24 hours before giving up.
Storing the key longer wastes Redis space with no operational benefit.

```python
IDEMPOTENCY_TTL = 60 * 60 * 24  # 24 hours
```

### Payloads without update_id

A Telegram payload always includes `update_id`. Its absence indicates a
malformed request or unexpected origin. Rejected with 400 and logged as
a warning to track irregularities.

## The Tradeoff: at-most-once vs at-least-once

The order of operations in the webhook is intentional:

```python
# 1. Mark as processed BEFORE enqueuing
await redis.set(idempotency_key, "1", ex=IDEMPOTENCY_TTL)

# 2. Enqueue the job
await redis.enqueue_job("process_telegram_message", payload)
```

**Why mark before enqueuing?**

If the process fails between the two operations, the outcome depends on order:

**Mark after enqueuing (at-least-once):**
enqueue_job ✓ → process fails → key never saved
→ Telegram retries → enqueue_job again → duplicate expense

**Mark before enqueuing (at-most-once):**
redis.set ✓ → process fails → job never enqueued
→ Telegram retries → key exists → request discarded
→ message is lost

**Decision: at-most-once.** A lost message the user can resend manually is
less severe than a duplicate expense in a personal finance system. Data
integrity takes priority over delivery guarantee.

## Complete Flow

Telegram → webhook
→ validate secret token
→ validate JSON
→ validate update_id present
→ query Redis: does processed_update:{update_id} exist?
→ YES: log info + return 200 (no enqueue)
→ NO:  set processed_update:{update_id} TTL=24h
enqueue_job → return 200

## Amendment — Two-layer idempotency and channel namespacing (Fase 5, multi-canal)

Three changes came with the multi-channel refactor.

**Atomicity.** The original `GET` then `SET` was not atomic: two simultaneous
deliveries of the same update could both pass the `GET` before either wrote.
Replaced with a single `SET(nx=True, ex=TTL)`. The ordering guarantee is
unchanged — the key is still written before enqueuing (at-most-once).

**Second layer via `_job_id`.** Jobs are now enqueued with
`_job_id=f"{channel}:{message_id}"`. Verified against arq 0.28: `enqueue_job`
performs `WATCH` + `exists(job_key, result_key)` inside a transaction and
returns `None` if the id is already present.

The two layers have different windows and neither replaces the other:

| Layer | Window | Covers |
| --- | --- | --- |
| Explicit key | 24h (Telegram's retry ceiling) | Late redelivery |
| `_job_id` | ~1h (arq `keep_result`, default 3600s) | Immediate redelivery, atomically |

**Key location and naming.** Moved from db0 to db2, aligning with the Redis
partition scheme and with the Go Gateway's ADR 003. Renamed from
`processed_updated:{update_id}` to `idempotency:{channel}:{message_id}` —
which also resolves a long-standing mismatch, since this document always
said `processed_update:` while the code said `processed_updated:`.

For Telegram, `message_id` is the `update_id`: `message.message_id` is unique
per chat, not globally, and would collide across chats as a dedup key.

Migration cost: keys written under the old name expire on their own within
24h. During that window a late redelivery would not find its marker — covered
in practice by the `_job_id` layer, since Telegram retries within seconds.

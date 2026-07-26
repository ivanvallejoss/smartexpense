# ARQ Retry Logic & Dead Letter Queue — Decision Record

## Problem

In production, `process_telegram_message` can fail for different reasons:

- Momentary PostgreSQL downtime
- Network timeout
- Unhandled exception in categorization logic

Without retry configuration, a failed job disappears silently:
User sends "Pizza 2000" → job fails → lost with no recoverable record

## Context: ARQ Maintenance Mode

ARQ has been in maintenance-only mode since 2024 — no new features, only
critical fixes. Relevant for long-term planning (potential future migration)
but doesn't affect what can be implemented today.

## Options Considered

### Option A — Basic retry with enriched logging

Configure `max_tries` in `WorkerSettings` and log the full payload when
a job exhausts all retries.

```python
class WorkerSettings:
    max_tries = 3
```

**Pros:**

- Single line of configuration
- No additional infrastructure
- ARQ handles backoff automatically
- Covers ~95% of transient failures (momentary DB downtime, network spikes)

**Cons:**

- Log retention is limited on Railway
- Manual recovery: read the log, copy the payload, re-enqueue by hand
- If 50 messages fail at 3am, you find out when a user complains

### Option B — Retry + manual Dead Letter Queue in Redis

When a job exhausts retries, persist the payload to Redis under a specific
key instead of letting it die silently.

```python
async def process_telegram_message(ctx, payload):
    try:
        ...
    except Exception as e:
        if ctx["job_try"] >= MAX_TRIES:
            redis = await get_redis("jobs")
            key = f"dlq:telegram:{ctx['job_id']}"
            await redis.set(key, json.dumps(payload), ex=DLQ_TTL)
            logger.error("Job moved to DLQ", extra={"job_id": ctx["job_id"]})
        raise
```

**Pros:**

- Programmatic recovery: re-enqueue failed messages when the issue resolves
- Inspectable at any time, independent of log retention
- Failure metrics without reading logs

**Cons:**

- Operational complexity: requires a mechanism to inspect and reprocess the DLQ
- ARQ has no native DLQ — has to be implemented manually
- Requires defining TTL for messages in the DLQ
- Requires an admin endpoint or script for reprocessing

## Decision: Option A

### 1. Scale doesn't justify the complexity

SmartExpense has fewer than 5 active users. The operational cost of maintaining
a manual DLQ (monitoring, reprocessing, TTL management) exceeds the benefit
at the current scale.

### 2. Idempotency first

Option B is only safe if `process_telegram_message` is idempotent. If the same
message is processed twice from the DLQ, it must not create a duplicate expense.
Adding that guarantee before it's needed is overengineering.

### 3. Option A solves the actual problem

95% of production failures are transient. Three retries with automatic backoff
resolve them without manual intervention.

### 4. Clear evolution path

Option A doesn't close the door to Option B. If the system grows and message
loss becomes a real risk, the DLQ can be added on top of the same foundation.
The `"jobs"` slot in `redis_client.py` is already reserved.

## Implementation

```python
class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [process_telegram_message]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 60
    max_tries = 3
```

Enriched logging when retries are exhausted:

```python
async def process_telegram_message(ctx, payload):
    try:
        ...
    except Exception as e:
        logger.error(
            "Job failed after max retries",
            extra={
                "job_id": ctx["job_id"],
                "try": ctx["job_try"],
                "payload": payload,
            },
            exc_info=True
        )
        raise
```

## Related

- Worker-level idempotency — extending the at-most-once guarantee to cover ARQ re-enqueue scenarios after worker crashes (backlog)

## Amendment — Retry semantics split by stage (Fase 4b, multi-canal)

The original decision assumed `process_telegram_message` failures would be
retried. In practice they were not: PTB's `error_handler` caught every
handler exception, replied to the user, and never re-raised — so the
worker's `raise` was effectively unreachable.

Removing PTB's dispatcher forced this to be made explicit. Retries are now
split by whether side effects have occurred:

- **Before dispatch** (event parsing, sender lookup, identity resolution):
  nothing has been written. Exceptions propagate and ARQ retries. This is
  the transient-failure case the original decision targeted.
- **Inside dispatch**: the handler may have already created an Expense
  before failing. Retrying would duplicate it. Exceptions are absorbed,
  logged with full context, and surfaced to the user.

This is the same reasoning that rejected the DLQ in Option B — the task is
not idempotent — applied consistently to retries. Worker-level idempotency
remains the prerequisite for widening retry coverage.

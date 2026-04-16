---

## Redis Database Partitioning

Redis supports 16 logical databases within a single instance. SmartExpense
uses this to isolate concerns without requiring separate Redis instances:

```python
# services/infrastructure/redis_client.py
_DATABASES = {
    "jobs":  0,   # ARQ job queue
    "state": 1,   # Conversation state (pending category flows)
    "cache": 2,   # Reserved: rate limiting, future cache
}
```

This means a `FLUSHDB` on database 1 (clearing stale conversation state)
never touches the job queue in database 0. Each concern can be monitored,
inspected, and managed independently.

All Redis connections are managed by a single module — no other file
in the codebase creates a Redis connection directly.

---

## Key Tradeoffs

### at-most-once delivery (webhook idempotency)

When the webhook marks an `update_id` as processed *before* enqueuing
the job, a failure between the two operations loses the message.
The alternative — marking after enqueuing — risks processing the same
message twice, creating duplicate financial records.

**Decision:** prefer losing a message (user can resend) over duplicating
a financial record (requires manual correction).

### 200 OK on Redis failure

If Redis is unavailable, the webhook returns `200 OK` and logs the error
rather than returning a 5xx. A 5xx response causes Telegram to retry
the webhook indefinitely, which would generate a retry storm against an
already degraded service.

**Decision:** silent message loss is preferable to a retry loop that
prevents recovery.

### Soft-delete via snapshot vs flag

A `is_deleted` flag on the `Expense` model would require filtering every
query. A JSON snapshot in a separate `DeletedObject` table keeps the
main table clean and allows restoration even when referenced records
(categories) no longer exist.

**Decision:** separate table with JSON snapshot, hard-delete the original.

---

## Testing Philosophy

Tests are written against contracts, not implementations. Each test
documents a system guarantee:

```python
async def test_suggest_does_not_create_categories_as_side_effect(self):
    """
    suggest() never writes to DB regardless of the path it takes.
    """
```

The distinction matters: if a test breaks because the implementation
changed but the contract was preserved, the test is wrong. If a test
breaks because the contract changed, something important happened.

The webhook tests use `RequestFactory` instead of Django's `AsyncClient`
to avoid triggering Django's URL loading, which causes NinjaAPI to
attempt duplicate registration. This is documented in
[`docs/decisions/testclient_conflict_resolution.md`](decisions/testclient_conflict_resolution.md).
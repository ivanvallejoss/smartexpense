# SmartExpense — Architecture Deep Dive

This document explains the non-obvious decisions behind SmartExpense's design.
It's written for someone who wants to understand not just *what* the system does,
but *why* it's structured the way it is and what tradeoffs were made along the way.

For a high-level overview, start with the [README](../README.md).
For specific decision records, see [decision_records/](decision_records/).

---

## System Components

SmartExpense runs as five independent services in production:

| Service | Runtime | Responsibility |
| --- | --- | --- |
| **Webhook** | Uvicorn (ASGI) | Receives Telegram updates, validates, enqueues to Redis |
| **Worker** | ARQ | Consumes jobs from Redis, runs business logic, writes to DB |
| **PostgreSQL** | Railway managed | Persistent storage for users, expenses, categories |
| **Redis** | Railway managed | Job queue (db 0), conversation state (db 1), cache (db 2) |
| **Frontend** | Railway static | React SPA — reads from the REST API, renders the dashboard |

Each service is deployed independently within a Railway project. They communicate
through Railway's private network — PostgreSQL and Redis are not exposed to the
public internet. Only the webhook and frontend services have public URLs.

The webhook and worker are intentionally separated into two processes. This is
the core architectural decision of the system, explained in the next section.

---

## Request Lifecycle

A complete trace of what happens when a user sends "Pizza 2000" to the bot:

Telegram delivers POST /bot/webhook/ with the update payload
Webhook validates:

Secret token in X-Telegram-Bot-Api-Secret-Token header
Valid JSON body
update_id present

Webhook checks Redis db 0:

If processed_update:{update_id} exists → return 200 OK (discard)
If not → set processed_update:{update_id} with 24h TTL

Webhook enqueues job to Redis db 0:
await redis.enqueue_job("process_telegram_message", payload)
Webhook returns 200 OK to Telegram (milliseconds after receiving the request)
ARQ worker picks up the job from Redis db 0:

Reconstructs the Telegram Update object from the payload
Routes it through PTB's handler system

handle_message runs:

Parses "Pizza 2000" → {amount: 2000, description: "Pizza"}
Calls get_category_suggestion(user, "Pizza")

ExpenseCategorizer.suggest() runs:

Checks user's expense history (highest priority)
Checks user's category keywords
Falls back to DEFAULT_CATEGORY_KEYWORDS
Returns CategorySuggestion(category, confidence, reason)

Based on confidence level:

≥ 0.8 → create expense, send confirmation to user
≥ 0.5 → create expense, ask user to confirm category
< 0.5 → create expense with STATUS_PENDING, show category picker

Expense written to PostgreSQL
Bot sends reply to user via Telegram API

Steps 1–5 happen in the webhook process. Steps 6–11 happen in the worker process.
The webhook never touches the database.

---

## Service Layer Design

The codebase separates business logic from delivery mechanisms:
apps/bot/        — Telegram adapter (input delivery mechanism)
apps/api/        — REST API adapter (input delivery mechanism)
services/        — Business logic (knows nothing about Telegram or HTTP)

This separation exists because **the bot is just one way to interact with the system**.
The same `create_expense()` service function is called from the Telegram handler,
from the REST API endpoint, and from tests — none of them need to know how
the others work.

Within `services/`, there's a further split:
services/expenses.py    — Write operations (create, update, delete, restore)
services/selectors.py   — Read operations (get_expenses, get_balance, get_month_stats)
services/ml/            — Categorization logic (suggest, feedback, learning)

`selectors.py` exists as a separate module from `expenses.py` for two reasons.
First, it makes the intent of every import explicit — when a handler imports
from `selectors`, it's signaling a read-only operation. Second, it enforces
a discipline: reads have no side effects, writes are always explicit. The
categorizer's `suggest()` function follows the same rule — it never writes
to the database regardless of the path it takes.

The ML module scales independently of the bot. If the categorization logic
becomes more sophisticated (embeddings, a separate inference service), that
change is contained within `services/ml/` and the rest of the system doesn't
change.

---

## Categorizer Deep Dive

`ExpenseCategorizer.suggest()` runs three levels of matching in priority order:

### Level 1 — User history (confidence 0.9–1.0)

Scans the user's last 100 expenses. If "pizza" appears in a past expense
categorized as "Delivery", future "pizza" expenses get the same category.

This is the core of the learning loop. The system doesn't learn from a global
model — it learns from each user's individual behavior. Two users can have
"pizza" mapped to different categories (one to "Delivery", another to "Food")
and the system handles both correctly.

Matching uses normalized text comparison (accents removed, lowercase) and
word-level overlap scoring. An exact description match returns confidence 1.0.
A partial word overlap returns a confidence proportional to the overlap ratio,
with a minimum threshold of 0.5 to filter noise.

### Level 2 — User category keywords (confidence 0.6–0.8)

Each category stores a `keywords` JSONField. If the user has a "Transport"
category with keywords `["uber", "taxi", "cabify"]`, any expense containing
those words matches at this level.

User categories take priority over global defaults — if a user has customized
their "Transport" category with their own keywords, that definition wins.

### Level 3 — System defaults (confidence 0.6–0.8)

`DEFAULT_CATEGORY_KEYWORDS` in `services/ml/default_keywords.py` contains
keyword lists for the 10 default categories, optimized for Argentine Spanish.
This is the fallback for new users with no history and no custom categories.

### The learning loop

When a user corrects a suggestion, the system records a `CategorySuggestionFeedback`
entry with the suggested category, the final category, and whether the suggestion
was accepted. On the next expense, Level 1 matching will find this history and
adjust accordingly.

This means the system's accuracy improves over time without retraining. A user
who consistently corrects "Uber" from "Transport" to "Work" will eventually see
"Work" suggested automatically — the history overrides the keyword default.

### Why history takes priority over keywords

Keywords encode general patterns. History encodes individual behavior.
How people spend money is highly personal — the same word can mean different
things to different users. A rigid keyword system would be accurate on average
but wrong for many individuals. History-first produces a system that starts
generic and becomes personal with use.

---

## Async Model

The system is fully async at the HTTP layer. Django runs under Uvicorn (ASGI),
and the webhook view is an async function that never blocks the event loop.

Within the service layer, there's an inconsistency worth noting:

**`sync_to_async` wrappers** appear throughout `services/expenses.py` and
`services/selectors.py`. These originated when the stack used Celery (which
is synchronous) as the task queue. When the stack migrated to ARQ (natively
async), the wrappers were kept for stability rather than rewritten.

**Native async ORM** (`aget()`, `acreate()`, `asave()`) appears in newer parts
of the codebase — handlers, callbacks, and some service functions. Django 4.1+
supports async ORM natively without thread pool overhead.

The result is a codebase with two async patterns coexisting. Both are correct
and produce the same behavior. The difference is implementation detail:
`sync_to_async` runs the ORM call in a thread pool and releases the event loop
while waiting. Native async ORM suspends the coroutine directly. At the current
scale, the performance difference is negligible.

Migrating `sync_to_async` wrappers to native async ORM is tracked as known
technical debt — a mechanical refactor with no behavior change, deferred in
favor of higher-priority work.

---

## Redis Partitioning

Redis supports 16 logical databases within a single instance. SmartExpense
uses three to isolate concerns without requiring separate Redis instances:

```python
_DATABASES = {
    "jobs":  0,   # ARQ job queue — Telegram message processing
    "state": 1,   # Conversation state — pending category creation flows
    "cache": 2,   # Reserved — rate limiting, future cache
}
```

**Why partition instead of using a single database?**

Operational isolation. A `FLUSHDB` on database 1 (clearing stale conversation
state after a bug) never touches the job queue in database 0. Each database
can be monitored, inspected, and managed independently. If a conversation state
key is corrupted, it can't interfere with job processing.

All Redis connections are managed by a single module —
`services/infrastructure/redis_client.py`. No other file in the codebase
creates a Redis connection directly. This means connection pooling, URL
construction, and database routing are all in one place.

The `"cache"` database (db 2) is reserved for per-user rate limiting, a planned
feature that would use the existing Redis instance without additional infrastructure.

---

## Production Deploy

Five services run within a single Railway project, connected through Railway's
private network:

Internet ──────────► Webhook (Uvicorn) ──► Redis ◄── Worker (ARQ)
                                                           │
Internet ──────────► Frontend (React)                      ▼
                          │                           PostgreSQL
                          │ (public URL)
                          ▼
                     REST API (Uvicorn)

**What's exposed to the internet:** the webhook URL (Telegram needs it),
the REST API URL (the frontend consumes it via public URL), and the frontend
itself. The frontend authenticates every request to the API using JWT tokens
issued by the Magic Link flow — CORS headers restrict which origins the
browser accepts responses from.

**What's not exposed:** Redis and PostgreSQL have no public URLs.

**Configuration:** each service reads its environment variables from Railway's
secret management system. No `.env` files exist in production. The `Procfile`
defines the commands Railway uses to start the webhook and run migrations on deploy.

---

## Key Tradeoffs

### at-most-once delivery (webhook idempotency)

Marking `update_id` as processed *before* enqueuing means a failure between
the two operations loses the message. The alternative — marking after enqueuing
— risks processing the same message twice, creating duplicate financial records.

**Decision:** prefer losing a message (user can resend) over duplicating a
financial record (requires manual correction). See
[decision_records/webhook_idempotency.md](decision_records/webhook_idempotency.md).

### 200 OK on Redis failure

If Redis is unavailable, the webhook returns `200 OK` and logs the error
rather than returning a 5xx. A 5xx response causes Telegram to retry
the webhook indefinitely, generating a retry storm against an already
degraded service.

**Decision:** silent message loss is preferable to a retry loop that
prevents recovery.

### Soft-delete via snapshot vs flag

A `is_deleted` flag on the `Expense` model would require filtering every
query and risks leaking deleted records if a filter is missed. A JSON snapshot
in a separate `DeletedObject` table keeps the main table clean and allows
restoration even when referenced records (categories) no longer exist.

**Decision:** separate table with JSON snapshot, hard-delete the original.

### ARQ over Celery

Celery requires a separate broker (RabbitMQ or Redis in broker mode) and
has significant configuration overhead. ARQ uses Redis directly as a queue
with a minimal API, and is natively async — matching the rest of the stack.
The tradeoff is that ARQ is in maintenance-only mode since 2024, which is
a long-term risk but not an immediate operational concern.

**Decision:** ARQ for simplicity and async compatibility. See
[decision_records/arq_retry_decision.md](decision_records/arq_retry_decision.md).

---

## Testing Philosophy

Tests are written against contracts, not implementations. Each test documents
a system guarantee — if the implementation changes but the contract holds,
the test should still pass.

The distinction matters in practice. `test_suggest_does_not_create_categories_as_side_effect`
doesn't test *how* `suggest()` avoids writes — it tests *that* it doesn't write.
If the implementation is refactored, the test still passes as long as the
contract is preserved.

**What's tested:**

- Webhook idempotency contracts and fault tolerance behavior
- Service layer side effects (category changes feed `CategorySuggestionFeedback`)
- Categorizer purity (`suggest()` never writes to DB)
- Business rules enforced at the selector level (pending expenses invisible to API)
- Auth layer (valid/expired/invalid JWT, non-existent users)

**What's not tested:**

- Real Telegram API calls — all bot tests mock PTB. Live API tests would be
  slow, flaky, and network-dependent.
- Worker lifecycle — ARQ startup/shutdown hooks are tested manually.
  Automating this requires a live Redis instance and adds complexity without
  proportional value at this stage.

**Test infrastructure note:** the webhook tests use `RequestFactory` instead
of Django's `AsyncClient` to avoid triggering Django's URL loading, which causes
NinjaAPI to attempt duplicate registration. See
[decision_records/testclient_conflict_resolution.md](decision_records/testclient_conflict_resolution.md).

# TestAsyncClient Conflict Resolution — Decision Record

## Problem

Running the full test suite caused the 6 tests in `test_webhook.py` to fail:
ninja.errors.ConfigError: Looks like you created multiple NinjaAPIs or TestClients
Already registered: ['api-1.0.0']

Tests passed in isolation but failed when running the full suite together.

**Root cause:** Django Ninja registers the API in Django's URL system when
a `TestAsyncClient` instance is created. When Django's `AsyncClient` loads
URLs for the webhook tests, it triggers a second registration of the same
API — Ninja detects the duplicate and raises the error.

## What We Tried

### Attempt 1 — `scope="session"` in conftest

```python
@pytest.fixture(scope="session")
def ninja_client():
    return TestAsyncClient(api)
```

**Result:** The suite hung indefinitely. `scope="session"` keeps a connection
open that blocks database teardown:
OperationalError: database "test_smartexpense_db" is being accessed by other users

### Attempt 2 — `scope="module"` in conftest

**Result:** Still hung. The event loop problem persists with `scope="module"`.

### Attempt 3 — `urls_namespace` on the API

```python
api = NinjaAPI(
    urls_namespace="smartexpense-api"
)
```

**Result:** Error changed to `Already registered: ['smartexpense-api']`.
The namespace doesn't solve the duplicate registration — `AsyncClient`
still loads the URLs.

### Attempt 4 — Importing `ninja_client` between test files

**Result:** `ModuleNotFoundError` — pytest doesn't resolve cross-module
fixture imports that way.

## Solution

Replace Django's `AsyncClient` with `RequestFactory` in `test_webhook.py`.

**Why it works:** `RequestFactory` builds `request` objects directly without
going through Django's router. The view receives the request and processes it
normally, but Django's URLs are never loaded — Ninja never attempts to register
the API a second time.

```python
# Before — loads Django URLs
from django.test import AsyncClient

async def test_valid_request(self, client):
    response = await client.post("/bot/webhook/", ...)

# After — bypasses the router entirely
from django.test import RequestFactory
from apps.bot.views import webhook

async def test_valid_request(self, request_factory):
    request = request_factory.post(...)
    response = await webhook(request)  # direct view call
```

**Mock path with RequestFactory:** When calling the view directly, the mock
must point to where `get_redis` is *used* in the view, not where it *lives*:

```python
# Wrong — where the function lives
@patch("services.infrastructure.redis_client.get_redis")

# Correct — where it's used in the view
@patch("apps.bot.views.get_redis")
```

## Remaining Warning

A cosmetic `OperationalError` warning appears in teardown — consequence of
the `scope="module"` on `ninja_client` in conftest keeping a connection open.
It does not affect test validity or results.

## Rule Extracted

**If the test verifies the behavior of a specific view, use `RequestFactory`.
If the test verifies routing or middleware, use `AsyncClient`.**

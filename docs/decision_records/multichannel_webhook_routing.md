# Multichannel Webhook Routing — Decision Record

## Problem

The inbound normalisation layer is already channel-agnostic:
`services/channels/registry.py` holds a `NORMALIZERS` dict keyed by channel
and dispatches through `normalize(channel, payload)`. Adding WhatsApp there
is one dict entry plus an `inbound` module.

The HTTP entry point is not. `apps/bot/views.py` hardcodes Telegram in three
places:

- the `X-Telegram-Bot-Api-Secret-Token` header check
- the mandatory `update_id` field, which is a Telegram concept
- `normalize(TELEGRAM, payload)`, with the channel fixed at the call site

And the URL was `bot/webhook/` — a generic name occupied by a single channel.

## Why this is not just a rename

Each channel authenticates its webhook differently. This is the part that
makes a naive generalisation wrong:

| | Telegram | WhatsApp Cloud API |
|---|---|---|
| Verification | shared secret in `X-Telegram-Bot-Api-Secret-Token` | HMAC-SHA256 of the raw body in `X-Hub-Signature-256` |
| Endpoint setup | `setWebhook` call, no challenge | `GET` challenge with `hub.challenge` / `hub.verify_token` |
| Dedup key | `update_id` | `messages[].id` |
| Delivery semantics | retries for 24h | retries with its own window |

A generic view therefore needs a per-channel *verifier* strategy plus a
`GET` branch that only one of the two channels uses. That is a second
registry, symmetric to `NORMALIZERS` and `SENDERS`, but with a shape that
cannot be validated against a single implementation.

## Options Considered

### Option A — Generalise the view now

`bot/<channel>/webhook/` resolving to one view that looks up a verifier by
channel, then delegates to `normalize(channel, payload)`.

Cost: roughly a day of design plus tests. Risk: the interface would be
designed from the documentation of one channel and a reading of another.
The real shape of the abstraction — where the `GET` challenge lives, whether
verifiers need the raw body or the parsed payload, what a verifier returns
on failure — surfaces while implementing the second channel, not before.
Designing it now means refactoring it later anyway, having paid twice.

### Option B — Namespace the path only

`bot/telegram/webhook/`, with the old path kept as a transition alias. The
view stays Telegram-specific.

Cost: minutes. Benefit is purely defensive: Telegram stops squatting the
generic namespace, so the second channel gets a symmetric route without
forcing a webhook re-registration in BotFather at the worst possible moment
(mid-migration, in production).

## Decision

**Option B, now.** **Option A, when WhatsApp is actually implemented.**

The deciding factor is that Option A's cost is not the code — it is
committing to an interface whose requirements are still hypothetical.
Option B is cheap, reversible, and removes the one irreversible-ish cost in
the picture: a production URL that has to change under time pressure.

## What Option A should look like when the time comes

Recorded here so the analysis is not redone from scratch:

1. A `VERIFIERS` registry in `services/channels/`, symmetric to `NORMALIZERS`
   and `SENDERS`. A verifier receives the raw request and returns either the
   parsed payload or a rejection — the raw body matters, since WhatsApp
   signs bytes, not the parsed JSON.
2. A `GET` branch in the view for the challenge handshake. Telegram never
   uses it; keep it out of the verifier interface if only one channel needs
   it, or make it an optional hook — decide once there are two real cases.
3. The dedup key moves into the normaliser. `job_id_for(event)` already
   builds `f"{channel}:{message_id}"` from the canonical event, so the view
   should stop reading `update_id` directly and read `event.message_id`
   instead. This is the one part of Option A that could be done today
   without speculation.
4. `bot/<channel>/webhook/` replaces the per-channel paths, and the legacy
   alias below can be dropped in the same change.

The trigger for revisiting this is the second channel — not a third
refactor of the first one.

## Consequences

- `manage.py set_webhook` now registers `/bot/telegram/webhook/`. It must be
  run against the production domain before the legacy alias is removed.
- `bot/webhook/` remains routed to the same view under the name
  `telegram-webhook-legacy`. It is temporary and should be deleted once
  Telegram is confirmed to be delivering to the new path.
- Point 3 above (reading `message_id` from the canonical event instead of
  `update_id` from the raw payload) is deliberately left undone. It is
  correct but it is not free, and it belongs with the work that makes it
  necessary.

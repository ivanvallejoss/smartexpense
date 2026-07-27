# Static Files Serving — Decision Record

## Problem

`whitenoise==6.11.0` was listed in `requirements.txt` and `Procfile` ran
`collectstatic` on release, but the middleware was never added to
`MIDDLEWARE` in `config/settings.py`. Meanwhile, `config/urls.py` only serves
static files when `DEBUG` is on.

Net effect: static files were not served at all in production — the Django
admin rendered without CSS — while the project still paid for the dependency.
The worst of both worlds: the cost of the package without its benefit.

## Context

The project is moving off Railway onto a self-managed VPS, where nginx sits
in front of the ASGI server (gunicorn + uvicorn workers) and the ARQ worker
runs as a systemd unit. In that topology nginx serves `/static/` directly
from `STATIC_ROOT`, and the request never reaches Python.

## Options Considered

### Option A — Wire whitenoise into MIDDLEWARE

Django serves its own static files. Works with or without a reverse proxy,
so the project stays runnable with a single process (`docker run`, a
`DEBUG=False` smoke test, an emergency deploy without nginx).

Cost: one dependency, one middleware, and a second source of truth for
something nginx already does — with nginx in front, whitenoise is dead code
on every production request.

### Option B — nginx only, drop whitenoise

The reverse proxy owns static file serving. One mechanism, one place to look
when something 404s. Django stays a pure application server.

Cost: running the project without a reverse proxy in front no longer serves
static files. Anyone cloning the repo gets working static files in `DEBUG`
mode only.

## Decision

**Option B.** nginx serves static files from `STATIC_ROOT`; `whitenoise` is
removed from `requirements.txt`.

The deciding factor is that the production topology is known and fixed: nginx
is already in the stack for TLS termination and reverse proxying, so static
serving comes for free with infrastructure that has to exist anyway. Adding
whitenoise would mean maintaining a second mechanism that never runs.

## Consequences

- `collectstatic` stays in the release step: nginx reads from `STATIC_ROOT`,
  so the directory still has to be populated on every deploy.
- Deployment requires nginx configured with a location block pointing at
  `STATIC_ROOT`. This is now a hard deployment requirement, not an
  optimisation — a deploy without it serves an admin with no CSS.
- Running the project outside `DEBUG` and without a reverse proxy will not
  serve static files. This is accepted and intentional.
- If the project is ever deployed to a PaaS without a configurable reverse
  proxy, this decision has to be revisited — Option A becomes the answer.

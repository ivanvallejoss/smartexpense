# Cierre de Fase A — Limpieza estructural del backend

**Repo:** `smartexpense` · **Base:** `2b43feb` (main) · **Resultado:** 8 commits
**Prerrequisito de:** Fase B (frontend Django templates + HTMX)

---

## 1. Árbol de estructura final

```bash
backend/
├── apps/
│   ├── core/          modelos + admin. Capa de datos pura, sin views ni urls.
│   │   ├── models.py  User, Category, Expense, CategorySuggestionFeedback,
│   │   │              DeletedObject, ChannelIdentity
│   │   ├── admin.py
│   │   └── migrations/  0001 → 0005
│   ├── bot/           webhook + dispatcher + handlers + state + worker ARQ
│   │   ├── views.py       webhook (productor del pipeline)
│   │   ├── urls.py        bot/telegram/webhook/ (+ alias legacy)
│   │   ├── dispatcher.py  ruteo de comandos → handlers
│   │   ├── handlers/      handlers agnósticos al canal
│   │   ├── worker.py      WorkerSettings de ARQ (consumidor)
│   │   ├── state.py       estado conversacional en Redis
│   │   ├── routing.py  errors.py  utils.py
│   │   └── management/commands/set_webhook.py
│   └── web/           ← FASE B. Vistas HTML. NO creada en esta fase.
├── services/          sin cambios estructurales
│   ├── channels/          frontera multicanal
│   │   ├── events.py      ChannelEvent (evento canónico)
│   │   ├── registry.py    NORMALIZERS por canal
│   │   ├── senders.py     SENDERS por canal
│   │   └── telegram/      inbound.py + outbound.py
│   ├── ml/                categorizer, helper, default_keywords
│   ├── parser/            expense_parser
│   ├── infrastructure/    redis_client
│   ├── auth.py            magic link JWT (dormido hasta Fase B)
│   ├── expenses.py  selectors.py  identities.py  constants.py
├── config/            settings.py, urls.py, asgi.py, wsgi.py
├── templates/         ← FASE B
└── tests/
    ├── bot/ (101)  channels/ (51)  services/ (57)
    └── test_expense_parser.py (33)
```

**Dirección de dependencias verificada, sin ciclos:**
`apps/* → services/* → apps.core.models`

**Fuera de `backend/`:** `frontend/` (React, congelado — se borra al cierre de
Fase B, sirve como referencia visual para los templates), `docs/`,
`docker-compose.yml`, `pytest.ini`, `pyproject.toml`.

---

## 2. Deprecaciones

### Borrado

| Qué | Por qué |
| --- | --- |
| `backend/apps/api/` completa | Existía solo para el frontend React. Hoja del grafo: su única entrada era `config/urls.py` |
| `backend/tests/api/` (17 tests) | Muere con la capa. Cobertura de negocio verificada como redundante con `tests/services/` |
| `backend/tests/conftest.py` | Solo contenía el fixture `ninja_client` |
| `django-ninja==1.5.3` | Sin consumidores |
| `django-cors-headers` + toda la config CORS | El frontend pasa a ser same-origin |
| `FRONTEND_URL`, `FRONTEND_TEST` | Perdieron sus consumidores |
| `IS_PRODUCTION` / `RAILWAY_ENVIRONMENT_NAME` | Estaba roto y muere con la migración a VPS |
| `flower`, `python-decouple`, `requests`, `dj-database-url`, `whitenoise` | Cero usos o nunca cableado |
| `[tool.pytest.ini_options]` en `pyproject.toml` | Duplicaba `pytest.ini` y perdía por precedencia |

### Marcado / dormido

| Qué | Estado | Cuándo se resuelve |
| --- | --- | --- |
| `services/auth.py` | Vivo y testeado, sin consumidor en producción | Fase B: el login web consume el token |
| `link_command` (comando `/link`) | Responde "en construcción", no emite token | Fase B |
| `bot/webhook/` (alias legacy) | Ruteado al mismo view como `telegram-webhook-legacy` | Al confirmar que Telegram entrega en `/bot/telegram/webhook/` tras correr `set_webhook` contra el dominio de producción |
| Vista del webhook | Específica de Telegram | Al implementar WhatsApp (ver ADR) |

### Pendiente con "cuándo"

- **`frontend/`** → borrar al cierre de Fase B.
- **Generalización de la vista del webhook** → al implementar WhatsApp. Análisis
  y diseño propuesto en `docs/decision_records/multichannel_webhook_routing.md`.
- **`update_id` → `event.message_id` en la vista** → único pedazo de esa
  generalización que se podría hacer hoy sin especular. Se dejó sin hacer
  a propósito: es correcto pero no es gratis, y pertenece al trabajo que lo
  vuelve necesario.

---

## 3. Estado de la suite

| Momento | Total | Pasando | Fallando |
| --- | --- | --- | --- |
| Antes (`2b43feb`) | 259 | 247 | **12** |
| Después | 242 | **242** | 0 |

Los 12 rojos no eran fallas de producción: eran tests desactualizados por el
commit `d08ca1e` (*JWT sobre user.id y no telegram_id*). El helper
`get_auth_headers` firmaba con `sub=telegram_id` y sin el claim `typ`, y
`GlobalAuth` los rechazaba con 401. El código de producción estaba sano.

La diferencia de 17 tests es la carpeta `tests/api/` completa (12 rojos + 5
verdes). Cobertura de negocio perdida: **cero** — verificado test por test
contra `tests/services/test_expenses.py` y `test_selectors.py`.

**Verificación final (A4)**, con `requirements.txt` instalado en un venv limpio:

```python
manage.py check                → System check identified no issues (0 silenced)
manage.py migrate (sin DATABASE_URL, SQLite desde cero)  → OK
pytest                         → 242 passed
config.asgi:application        → ASGIHandler
reverse('telegram-webhook')    → /bot/telegram/webhook/
resolve('/api/expenses/')      → no resuelve (correcto)
```

La serie de 8 patches se aplicó con `git am -3` sobre un clon limpio de
`2b43feb` y produjo 242 tests verdes.

---

## 4. Decisiones tomadas

| # | Decisión | Justificación |
| --- | --- | --- |
| D1 | Borrar `apps/api` completa ahora, no marcarla | El sistema está en pausa: la opción conservadora no protegía a ningún usuario, y la CI en verde vale más justo antes de escribir código nuevo |
| D1b | `frontend/` se conserva hasta el cierre de Fase B | Es la referencia visual de los templates y no cuesta nada |
| D2 | `/link` informa "en construcción"; `services/auth.py` intacto | El emisor del token sobrevive porque Fase B lo reusa; emitir tokens sin validador sería mandar usuarios a una URL muerta |
| D3a | `sslmode` viaja en `DATABASE_URL`, no en `settings.py` | La política de TLS depende de dónde vive el Postgres, no del flag `DEBUG` — decisivo con la migración a VPS, donde `require` contra un Postgres local falla |
| D3b | `ENVIRONMENT` explícito reemplaza a `IS_PRODUCTION` | `DEBUG` es un flag de comportamiento de Django, no una descripción de infraestructura; y no se ata al proveedor de hosting |
| D3c | `ALLOWED_HOSTS` abre solo en `dev` + `DEBUG` | Fallar ruidosamente es preferible a aceptar cualquier Host header en silencio |
| D4 | nginx sirve estáticos; `whitenoise` se elimina | La topología de producción es conocida y fija: nginx ya está en el stack. Documentado en `docs/decision_records/static_files.md` |
| D4b | `pytest.ini` queda como fuente única de config de pytest | Una sola fuente de verdad; `pyproject.toml` conserva `black` e `isort`, que sí se usan |
| D5 | Namespacear la ruta (`bot/telegram/webhook/`), no generalizar la vista | El costo de generalizar no es el código sino comprometerse a una interfaz cuyos requisitos son hipotéticos hasta tener el segundo canal. Documentado en `docs/decision_records/multichannel_webhook_routing.md` |

---

## 5. Temas estacionados (no se resolvieron acá)

### Fase B — frontend web
- Dónde vive el login web y cómo consume el token de `services/auth.py`.
- Variable de sitio que reemplace a `FRONTEND_URL` (`SITE_URL` / `BASE_URL`).
- Creación de `apps/web` y de `backend/templates/`.
- Reactivación del comando `/link` una vez que exista destino.
- Borrado de `frontend/`.

### Cuando entre WhatsApp
- Generalización de la vista del webhook (registry de verificadores por canal,
  branch `GET` para el challenge, dedup por `event.message_id`).
- Eliminación del alias `bot/webhook/`.

### Operaciones / deploy (fuera del alcance de esta fase)
- **`ENVIRONMENT=prod` y `ALLOWED_HOSTS` son obligatorias en el deploy.** Sin
  ellas Django rechaza todos los requests. Es el comportamiento buscado, pero
  tiene que estar en el runbook.
- Correr `manage.py set_webhook` contra el dominio de producción antes de
  eliminar el alias legacy.
- nginx necesita un `location /static/` apuntando a `STATIC_ROOT`. Pasó de ser
  una optimización a un requisito duro de deploy.
- `Procfile` declara `release` y `web` pero no el worker ARQ, que corre como
  servicio aparte (Railway) y va a ser una unit de systemd en el VPS. La
  divergencia entre `Procfile`, `docker-compose.yml` y systemd no se unificó.
- No hay `apps.py` / `AppConfig` en ninguna app: no hay hook `ready()`.
  Costo bajo hoy; se documenta por si aparecen señales.

### Arquitectura, sin fecha
- El Bridge del gateway Go mencionado en `services/channels/registry.py:26`
  sigue vigente como plan, sin implementación cercana. La frontera de canales
  quedó donde estaba y no condiciona la Fase B.


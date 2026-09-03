# Plan de unidades — vinculación de canales y acceso web

Documento vivo. Se actualiza al cerrar cada unidad.

**Objetivo del arco:** que la vinculación de canales exista **antes** del primer
mensaje real de WhatsApp, para que el problema de las cuentas partidas no llegue
a nacer. Ver `docs/decision_records/vinculacion_canales.md`, sección 2.

Cada unidad es una sesión, un branch y un PR. No se empiezan dos a la vez.

---

## Estado

| # | Unidad | Estado | Depende de |
|---|---|---|---|
| 2 | Higiene del protocolo de canal | **hecha** — `2133da3`, `c5d8732` | — |
| 2.5 | Fixtures de dashboard independientes del calendario | **hecha** — `5d30bd7` | — |
| 1a | Formateo repo-wide + job de lint en CI | **en curso** | — |
| 0 | ADR de vinculación de canales | pendiente | — |
| 1b | Dependencias: `python-telegram-bot` 20.7 → 22.8, `requirements.txt` real | pendiente | — |
| 3 | Grant store: `issue_grant` / `consume_grant`, db `auth`, sale PyJWT | pendiente | 0 |
| 4 | Acceso web: vista de entrada GET/POST, `LOGIN_URL`, config de sesión | pendiente | 3 |
| 5 | Vinculación de identidad: `attach_identity_to_user`, `link_command` | pendiente | 2, 3 |
| 6a | Fork en el worker: política por canal, estado pendiente, buffer del 1er mensaje | pendiente | 5 |
| 6b | Handler de onboarding: botones, canje, rate limit | pendiente | 6a |
| 7 | Serializador JSON de ARQ + drenaje de cola | pendiente | — |

0 y 1b son independientes entre sí y del resto.

---

## Notas de secuencia

**El ADR (0) va antes de implementar, no después.** Escrito antes, le da a cada
sesión un documento contra el cual chequearse. Escrito después, es arqueología.

**6a está partida de 6b a propósito.** 6a mueve la estructura del worker con un
handler stub; 6b implementa el flujo. El worker es el camino caliente: si algo
sale mal, hay que poder saber en cuál de las dos.

**Punto de partida de 4.** Hoy `SESSION_COOKIE_AGE` y `SESSION_SAVE_EVERY_REQUEST`
no existen en `config/settings.py` — la sesión deslizante está decidida
(`vinculacion_canales.md`, sección 7.3) y sin construir. Y `LOGIN_URL` apunta a
`/admin/login/` (`settings.py:89-91`), asumido en el propio archivo como
break-glass de B1: es un formulario que ningún usuario del bot puede usar.

**7 va al final.** Cambia el formato de la cola. En medio de las otras, cualquier
bug de feature se confunde con un bug de serialización.

**5 y 6 no se pueden probar de punta a punta contra WhatsApp**, porque WhatsApp
todavía no existe. La salida es registrar un canal de prueba —normalizador y
sender fake— solo en el contexto de tests, usando el patrón de registry que ya
existe.

---

## Deuda registrada, sin unidad asignada

- **`flake8` sin configurar.** Necesita archivo de config más una limpieza de
  ~21 hallazgos reales (`F401`, `E402`). Ver `docs/trampas.md`.
- **`User.telegram_id` y `telegram_username`** vivos sin consumidor. El docstring
  de la migración `0005` afirma que `auth.py` usa `telegram_id` como `sub` del
  JWT; ya no es cierto (`services/auth.py:18` usa `user_id`). Además
  `telegram_id` conserva `unique=True` (`models.py:18-24`), que es superficie de
  colisión en un merge de cuentas — ver `vinculacion_canales.md`, sección 2.2.
- **`help_text` de `ChannelIdentity.external_id`** todavía dice `wa_id`
  (`models.py:320`), cuando la clave canónica de WhatsApp es el LID — el
  docstring del mismo modelo (`:288-296`) y `vinculacion_canales.md` sección 3.1
  ya lo dicen bien. Cambiarlo genera un `AlterField`.
- **`process_telegram_message`** sigue normalizando payloads crudos
  (`apps/bot/worker.py:113+`). Es el alias deprecado para jobs encolados antes
  del deploy de la Fase 5 y la única excepción viva a "el worker nunca ve un
  payload crudo" (`vinculacion_canales.md`, sección 4). Se remueve cuando no
  queden jobs viejos en vuelo.
- **`black.target-version = py311`** mientras el repo corre 3.12. Inocuo: con
  py311 black no emite sintaxis exclusiva de 3.12.
- **`multichannel_refactor.md:215`** cita la firma vieja `Sender.reply(external_user_id,
  text)`. Es un ADR de cierre: se deja como está.
- **Los tests mockean `_bot` con `AsyncMock`**, que acepta cualquier kwarg. La
  suite no detecta que PTB deje de aceptar un parámetro. Cerrarlo pediría un test
  de contrato contra la firma real.

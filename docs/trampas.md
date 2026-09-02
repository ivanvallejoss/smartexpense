# Trampas conocidas

Documento vivo. Cada entrada acá costó al menos una sesión de debugging. Están
para que no se paguen de nuevo.

Si encontrás una trampa nueva, agregala. Si arreglás una definitivamente,
**sacala** — una trampa que ya no existe desinforma igual que una que falta.

---

## El borde async/sync está en todos lados

Las views del dashboard son `async`. Eso tiene consecuencias que no son obvias:

- `request.user` es perezoso y pega a la base. Usar `await request.auser()`.
- `LoginRequiredMixin` **no funciona** en views async: su `dispatch` es
  síncrono. Está documentado en `apps/web/views.py`.
- `transaction.atomic` no funciona en contexto async. El patrón del repo es
  función síncrona envuelta en `sync_to_async` — ver `_create_user_with_identity`
  en `services/identities.py`.
- `django.contrib.auth.login()` es síncrono. Va envuelto igual.
- Los templates no pueden evaluar nada perezoso: todo llega resuelto desde los
  selectors, listas y no querysets.

---

## Los tests del dashboard dependían del día del mes

**El bug:** `_dashboard_queryset` filtra la ventana `[inicio de mes en USER_TZ,
now]`. Los fixtures anclaban los datos "del mes en curso" al borde **inferior**
de esa ventana y caminaban hacia adelante (`desde_mes + timedelta(days=1)`). Los
días 1, 2 y 3 de cada mes esos gastos caían en el futuro, `date__lte=now` los
excluía, y los 14 tests de `tests/web/` fallaban. Invisible los otros 27 días.

**La solución:** la fixture `autouse` `reloj_fijo` en `tests/web/conftest.py`
congela `django.utils.timezone.now` a mitad de mes con `unittest.mock.patch`.
Con la ventana de ancho fijo, la aritmética de los fixtures vuelve a ser
correcta sin tocarla.

**No la saques.** El freeze *neutraliza* la fragilidad, no la elimina: los
offsets absolutos siguen ahí y vuelven a romper sin él.

Dos cosas relacionadas:

- `factory.LazyFunction(timezone.now)` en `tests/factories.py` **liga el objeto
  función al importar**, así que el patch no la alcanza. Comprobado. Es inocuo
  en `tests/web/` porque esos archivos no usan factories, pero invalida reusar
  `reloj_fijo` en tests que sí las usen.
- `Expense.clean()` prohíbe explícitamente las fechas futuras. Los fixtures
  venían generando datos que el propio modelo considera inválidos — pasaban solo
  porque `objects.create()` no ejecuta `clean()`. El invariante correcto para un
  gasto de test no es "dentro de la ventana", es **"en el pasado"**.

`tests/services/test_selectors.py` no comparte la fragilidad: ancla los gastos
**en** `timezone.now()`, que siempre cae dentro de la ventana por construcción.
Pero usa fechas absolutas de 2026 con filtros de mes explícitos; si alguien les
agrega un rango relativo, el problema vuelve.

---

## ARQ serializa con pickle

`arq.jobs.serialize_job` usa `pickle.dumps` por defecto. Un productor que no sea
Python no puede escribir en la cola sin cambiar `job_serializer` **y**
`job_deserializer` en los dos extremos.

Y el día que se cambie: van a quedar jobs encolados con pickle que un worker con
deserializador JSON no puede leer — `deserialize_job` lanza `DeserializationError`,
no los ignora. Hay que drenar la cola antes, o soportar los dos formatos durante
una ventana.

---

## Las databases lógicas de Redis tienen techo

`services/infrastructure/redis_client.py` mapea propósitos a databases lógicas
(`jobs`, `state`, `cache`). Funciona en un Redis single-node y **no sobrevive a
Redis Cluster**, donde solo existe la db 0. El patrón que escala es prefijo por
propósito dentro de una sola db, que es lo que ya se hace *dentro* de cada
database (`cat_state:`, `idempotency:`).

Es una limitación conocida y aceptada. No la refactorices.

---

## Telegram y WhatsApp prefetchean las URLs

Los dos canales hacen un GET a cualquier link que se mande, para armar la
preview. Un endpoint de magic link que consuma el token en el GET queda
consumido por el crawler antes de que el humano toque nada.

Por eso el canje es **POST**: el GET renderiza una página con un botón, el POST
consume. Y por eso `Sender.reply()` expone `disable_preview`.

---

## Las migraciones espejan texto de los modelos

El `help_text` de `ChannelIdentity.external_id` está copiado **verbatim** en
`apps/core/migrations/0004_channelidentity.py`. Editar el `help_text` del modelo
hace que `makemigrations` quiera emitir un `AlterField`.

Si una unidad prohíbe tocar migraciones, entonces también prohíbe tocar
`help_text`. Guarda:

```bash
cd backend && python manage.py makemigrations --check --dry-run
```

---

## `flake8` está instalado y sin configurar

`flake8==7.0.0` está en `requirements.txt` y no lo corre nadie. Sin archivo de
configuración tira ~547 errores, de los cuales ~377 son `E501` porque el default
de flake8 son 79 columnas y `black` está configurado en 100.

Después de black quedan unos 21 reales (`F401` imports sin usar, `E402` imports
fuera del tope, algunos legítimos en Django). Meterlo al CI sin config y sin esa
limpieza es meter 547 errores el día uno.

---

## El venv local puede tener paquetes que el repo ya no usa

El CI instala desde `requirements.txt` y es el entorno honesto. Un venv de
desarrollo puede arrastrar restos de features removidas — pasó con `django-ninja`
y `django-cors-headers`, cuyo código se borró del repo y los paquetes quedaron
instalados.

Si algo anda local pero el CI se queja, creele al CI.

---

## `.pre-commit-config.yaml` no existe

`pre-commit` está en `requirements.txt` pero no hay archivo de configuración. No
asumas que hay hooks corriendo antes de tus commits.

# Sistema Integral de Gestión de Consorcios

Aplicación web para administrar un consorcio: expensas, cuenta corriente por departamento, gastos, sueldos del personal, comunicación interna y reserva de amenities. Modelado sobre el formato de liquidación real de la **Ley 941 CABA**.

---

## Stack

| Capa | Tecnologías |
|---|---|
| Backend | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · SQLite |
| Frontend | React 18 · Vite · React Router |
| Auth | JWT HS256 con 4 roles (Administración, Departamento, Representante, Super-Admin) |
| Multitenant | SaaS 3-tier: Super-Admin → Administración → Consorcio → Departamento (discriminator column `consorcio_id` en toda tabla operacional) |
| Tests | pytest (**765 tests**) |
| Contrato | OpenAPI 3.1 (`openapi.yaml`) — documentación-primero |

---

## Cómo correrlo desde cero

> **Pre-requisitos:** Python 3.11+ y Node.js 18+.

### 1. Configurar variables de entorno

Copiá el template y completalo:

**Windows PowerShell**
```powershell
Copy-Item .env.example .env
```

**Linux / Mac**
```bash
cp .env.example .env
```

Editá el archivo `.env` y completá al menos estas dos variables:

```env
SECRET_KEY=<una cadena aleatoria de al menos 32 caracteres>
SEED_DEFAULT_PASSWORD=<la password con la que querés loguearte como demo>
```

Para generar una `SECRET_KEY` aleatoria:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Si `SEED_DEFAULT_PASSWORD` queda vacío, el seed genera una password aleatoria al vuelo y la imprime en consola — útil pero menos cómodo para probar.

### 2. Levantar el backend

```bash
python -m venv .venv

# Activar el venv:
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / Mac:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn backend.main:app --reload
```

API en `http://localhost:8000` · Swagger UI en `http://localhost:8000/docs`.

#### Email saliente (SMTP) — Fase 6a

Para enviar PDFs de boleta por email a los departamentos, configurar en `.env`:

```env
SMTP_HOST=smtp.gmail.com   # o tu servidor SMTP
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=tu_app_password
SMTP_FROM_EMAIL=consorcio@tu-dominio.com
SMTP_FROM_NAME=Administración Consorcio
```

Si `SMTP_HOST` queda vacío, los emails NO se envían — se loggean al stdout de
uvicorn (útil para dev y CI). En modo console, el endpoint
`POST /periodos/{X}/enviar-pdfs` igual devuelve éxito con resumen.

La primera vez, si la base está vacía, se siembra automáticamente con:

| Email | Rol | Password |
|---|---|---|
| `admin@consorcio.local` | Administración | `SEED_DEFAULT_PASSWORD` del `.env` |
| `depto-a@consorcio.local` | Departamento (UF-1A) | idem |
| `depto-b@consorcio.local` | Departamento (UF-2B) | idem |

También se cargan expensas de muestra, movimientos de cuenta corriente y un par de notas crédito/débito para que se vea algo desde el primer login.

### 3. Levantar el frontend (en otra terminal)

```bash
cd frontend
npm install
npm run dev
```

Frontend en `http://localhost:5173`. Ahí podés loguearte con cualquiera de los tres usuarios del seed.

### 4. (Opcional) Correr los tests

```bash
pytest -v
```

Debería pasar **765 tests**. Los tests usan SQLite en memoria, no tocan tu DB local.

### Reset rápido de datos

Si querés volver a sembrar desde cero:

```powershell
# Bajá el backend (Ctrl+C en la terminal de uvicorn)
Remove-Item -Force consorcio.db    # Windows
# rm -f consorcio.db               # Linux/Mac
# Volvé a levantar uvicorn — vuelve a sembrar
```

---

## Multitenant SaaS

El sistema opera como SaaS con jerarquía **Super-Admin → Administración → Consorcio → Departamento**. Cada Administración puede tener N Consorcios y cada Consorcio tiene sus propios usuarios, catálogos y datos operativos (aislamiento por `consorcio_id`).

### Header X-Consorcio-Id

Todo endpoint operacional (fuera de `/auth/*` y `/me/*`) exige el header:

```
X-Consorcio-Id: <id del consorcio activo>
```

El frontend persiste el consorcio seleccionado en `localStorage` y lo envía en cada request. El backend valida con `get_consorcio_activo` que el usuario del JWT tenga acceso al consorcio pedido; caso contrario devuelve **403**.

Códigos de error específicos:
- `400 X-Consorcio-Id requerido` — header ausente.
- `400 X-Consorcio-Id invalido` — no numérico.
- `403 sin acceso a este consorcio` — el user no pertenece a ese tenant.
- `403 cambio_password_requerido` — user con `must_change_password=True` no puede operar hasta cambiar la password.
- `403 administracion_suspendida` — devuelto en `/auth/login` si la Administración está `activa=False`.

### Migración desde single-tenant

Si venís de una DB pre-multitenant (single-tenant `consorcio.db`), corré el script idempotente:

```bash
python -m backend.migrate_multitenant
```

Este script:
1. Crea la tabla `administraciones` con una fila "Administración Demo" (id=1).
2. Crea la tabla `consorcios` con un "Consorcio Demo" (id=1) apuntando a la administración.
3. Alter table + backfill de `consorcio_id=1` en todas las tablas operacionales.
4. Registra el marcador `ya_migrado` para no correr dos veces.

Es seguro correrlo varias veces; sale sin hacer nada si el marcador ya existe.

### Super-Admin

El rol `super_admin` no tiene consorcio propio: opera desde fuera y usa impersonate + audit log (Plan B). Se crea manual con:

```bash
# En .env:
# SUPER_ADMIN_EMAIL=sa@tu-dominio.com
# SUPER_ADMIN_PASSWORD=<password fuerte>

python -m backend.seed_super_admin
```

Idempotente: si el super-admin ya existe, no hace nada (usar `--force` para regenerar password).

### Plan B — Super-Admin backend (completado)

Endpoints bajo `/super-admin/*` (rol `super_admin`, sin `X-Consorcio-Id`):

| Método | Path | Propósito |
|---|---|---|
| GET | `/super-admin/administraciones` | Listar tenants |
| POST | `/super-admin/administraciones` | Crear tenant + primer usuario admin (con `must_change_password=True`) |
| GET/PATCH | `/super-admin/administraciones/{id}` | Detalle / editar |
| POST | `/super-admin/administraciones/{id}/suspender` | Toggle `activa` — bloquea login con 403 `administracion_suspendida` |
| POST | `/super-admin/administraciones/{id}/reset-password/{user_id}` | Password temporal + `must_change_password=True` |
| POST | `/super-admin/impersonate/start` | JWT temporal 15 min con claim `impersonated_by`. Requiere `motivo` ≥ 10 chars |
| POST | `/super-admin/impersonate/end` | Revoca el JTI impersonado |
| GET | `/super-admin/metricas` | Agregados globales (tenants, consorcios, deptos, expensas del mes, impersonates 30d) |
| GET | `/super-admin/audit-log` | Log paginado con filtros por `accion` y `administracion_id` |

**Audit log automático:** durante impersonate, un middleware ASGI loguea todo POST/PUT/PATCH/DELETE con `path`, `body` (campos que matchen `password|token|secret` se redactan) y `status`. Los GET no se loguean — el `impersonate_start` ya deja constancia de la sesión.

**Bloqueo del JWT impersonado en rutas super-admin:** el token temporal tiene el rol del usuario impersonado, así que `require_roles(Rol.super_admin)` lo rechaza con 403 automáticamente. `/impersonate/end` es la única excepción (usa `get_current_user`).

### Plan C — Frontend multitenant (completado)

- **`apiFetch` inyecta `X-Consorcio-Id`** automático desde `localStorage.consorcio_activo_id` en toda ruta operacional (excepto `/auth/*`, `/me/*`, `/super-admin/*`).
- **AuthContext** expone `consorcioActivoId`, `consorciosAccesibles`, `impersonatedBy`, `mustChangePassword`. Al login llama a `GET /me/consorcios` y elige el consorcio activo (último de `localStorage` si válido; sino, el primero).
- **Selector de consorcio en topbar** (`SelectorConsorcio.jsx`): dropdown visible sólo si el usuario tiene 2+ consorcios; al cambiar hace `reload()` para refetchear con el nuevo header.
- **Guard `mustChangePassword`**: `RequireAuth` redirige a `/mi-usuario/cambiar-password` hasta que el usuario cambie su contraseña. `apiFetch` también detecta `403 cambio_password_requerido` como red de seguridad.
- **`Login.jsx`** maneja el 403 `administracion_suspendida` con mensaje claro.
- **Super-admin UI**: sidebar propio (`SidebarSuperAdmin.jsx`) con 3 items; pantallas `SuperAdminAdministraciones`, `SuperAdminMetricas`, `SuperAdminAuditLog` (paginado + filtros).
- **Banner de impersonate** (`BannerImpersonate.jsx`): banda roja fija arriba con countdown 15 min, botón "Salir" que llama a `/super-admin/impersonate/end` y restaura el token original desde `sessionStorage`.

### Plan D — Wizard onboarding + CRUD /consorcios (completado)

**Backend — 4 endpoints nuevos bajo `/consorcios` (rol `administracion` para mutaciones):**

| Método | Path | Rol | Comentario |
|---|---|---|---|
| GET | `/consorcios` | admin | Lista los consorcios de la administración. No requiere `X-Consorcio-Id`. |
| POST | `/consorcios` | admin | Wizard 4-pasos. Crea el consorcio **y una Caja "Banco principal"** en la misma transacción, apuntada por `caja_default_pagos_id`. |
| GET | `/consorcios/{id}` | admin (del tenant), depto/rep (del propio consorcio) | Reemplaza `GET /configuracion`. |
| PATCH | `/consorcios/{id}` | admin | Reemplaza `PUT /configuracion`. Incluye `usa_personal_propio`. |

Los endpoints legacy `/configuracion` (GET y PUT) quedan marcados `deprecated: true` en OpenAPI; siguen funcionando por compatibilidad y resuelven al consorcio del `X-Consorcio-Id`.

**Frontend:**

- Pantalla `/administracion/consorcios` (listado con "Editar", "Usar como activo" y "+ Nuevo consorcio").
- Wizard `/administracion/consorcios/nuevo` con **4 pasos** y barra de progreso: (1) datos del consorcio + toggle `usa_personal_propio`, (2) administración, (3) datos bancarios, (4) vencimientos e intereses. **Pre-fill inteligente** en pasos 2 y 3 con botón "Usar los datos del último consorcio" (se muestra solo si la administración ya tiene otros consorcios).
- Sidebar nuevo item **"Consorcios de la administración"** dentro de "Configuración".
- **Feature flag Personal:** el grupo "Personal" del sidebar (Liquidaciones, Haberes, Conceptos) se oculta cuando el consorcio activo tiene `usa_personal_propio = false`. Se re-evalúa al cambiar de consorcio activo.

---

## Roles y permisos

| Rol | Resumen |
|---|---|
| **Administración** | Crea/edita todo: expensas, gastos, proveedores, empleados, liquidaciones, comunicados. Aprueba comprobantes y crea notas crédito/débito. |
| **Departamento** | Ve sus expensas y su cuenta corriente; presenta comprobantes de pago; lectura de comunicados y configuración del consorcio. |
| **Representante** | Lectura técnica + gestiona tareas y aprueba presupuestos. |

La identidad y el rol siempre se extraen del JWT — el backend nunca confía en `usuario_id`/`departamento_id` del body.

---

## Estructura del proyecto

```
backend/
  main.py                 # FastAPI app, lifespan, middlewares
  models.py               # SQLAlchemy 2.0 (Mapped[...])
  schemas.py              # Pydantic v2
  cuenta_corriente.py     # Módulo FIFO (puro, sin side effects)
  routers/                # Un router por recurso
  seed.py                 # Datos demo inicial
frontend/
  src/
    api/                  # Clientes fetch tipados
    auth/                 # Context + token + roles
    components/           # Modal, Tarjeta, BadgeEstado, Sidebar
    screens/              # Una pantalla por recurso
openapi.yaml              # Contrato API (fuente de verdad)
tests/                    # pytest, un archivo por router
docs/superpowers/
  specs/                  # Diseños de cada fase (brainstorming → spec)
  plans/                  # Planes TDD por tarea
```

---

## Roadmap

El proyecto se entrega en fases independientes:

| # | Fase | Estado |
|---|---|---|
| 1 | Modelo de datos central (rubros, clases de prorrateo, coeficientes, proveedores, configuración) | ✅ |
| 2 | Gastos del consorcio (carga, plan de cuotas, habituales, particulares) | ✅ |
| 3 | Encargado y cargas sociales (empleados, haberes, conceptos, liquidaciones mensuales) | ✅ |
| 3.5 | **Cuenta corriente por departamento** (movimientos contables + FIFO) | ✅ |
| 4 | Cierre de período y liquidación (saldo anterior, intereses, vencimientos) | pendiente |
| 5 | Caja, fondo de reparación, estado financiero | pendiente |
| 6 | Reportes Ley 941 + PDF de liquidación | pendiente |
| 7A | **Multitenant SaaS (backend core)** — Administración/Consorcio/Super-Admin, `consorcio_id` en toda tabla operacional, resolver X-Consorcio-Id | ✅ |
| 7B | **Super-Admin backend** — CRUD administraciones, reset-password, impersonate (JWT 15 min), métricas, audit log automático | ✅ |
| 7C | **Frontend multitenant** — selector de consorcio, `X-Consorcio-Id` automático, `must_change_password` guard, sidebar + pantallas super-admin, banner impersonate con countdown | ✅ |
| 7D | **Wizard onboarding + CRUD /consorcios** — endpoints `/consorcios` (list/get/POST wizard/patch) + caja default, pantalla listado admin + wizard 4 pasos, sidebar con feature flag `usa_personal_propio` | ✅ |
| 7C | Frontend con selector de consorcio + guards por rol | pendiente |
| 7D | Wizard onboarding 4-pasos para nuevos consorcios | pendiente |

Cada fase tiene su propio ciclo `brainstorming → spec → plan → implementación TDD` documentado en `docs/superpowers/`.

---

## Deploy del demo

El demo público corre en su propia infraestructura, separada de producción, para
poder resetearse sin afectar datos reales.

**Infraestructura actual:** frontend en **Vercel**
(https://consorciosdemo.vercel.app/), backend y base en **Render**.

El generador (`backend/seed_demo.py`) tarda 67-69 s, así que no hay seed-on-boot:
haría fallar el healthcheck durante el arranque. En su lugar, un cron aparte lo
dispara cada 6 h.

Los cron jobs de Render corren en contenedores separados de los servicios web, y
los discos persistentes se montan en un único servicio — un cron externo no puede
compartir el archivo SQLite del servicio web, y aunque pudiera, dos procesos
haciendo drop/recreate sobre SQLite mientras el web atiende tráfico es receta de
bloqueos. Por eso el demo usa **Postgres administrado** en vez de SQLite: el cron
se conecta por red, sin filesystem compartido y sin downtime del servicio web
durante el reset. De paso iguala la infraestructura del demo a la de producción.

```
Vercel:
  frontend (Vite build)  -> VITE_DEMO_MODE=true
                            VITE_API_URL apuntando al backend de Render

Render:
  1. Postgres administrado
  2. Web service   -> uvicorn backend.main:app  (usa el Procfile)
  3. Cron job      -> python -m backend.seed_demo --reset
                      schedule "0 */6 * * *"

Los servicios 2 y 3 comparten las mismas variables de entorno.
```

`frontend/vercel.json` ya trae el rewrite de SPA (`/(.*) -> /index.html`), sin el
cual cualquier ruta que no sea `/` da 404 al recargar.

| Variable | Valor |
|---|---|
| `DEMO_MODE` | `true` |
| `DATABASE_URL` | la interna del Postgres de Render — **debe contener la subcadena `demo`** (ej. base `consorcio_demo`), lo exige el candado de `Settings`, que si no impide arrancar |
| `SECRET_KEY` | generar una distinta de la de producción |
| `SEED_ENABLED` | `false` — el dataset lo genera `seed_demo`, no `seed_if_empty`; si queda en `true` aparece un "Consorcio Demo" de smoke-test al lado del real |
| `DEMO_SEED_PASSWORD` | mínimo 8 caracteres |
| `SUPER_ADMIN_EMAIL` / `SUPER_ADMIN_PASSWORD` | credenciales del super admin del demo |
| `SMTP_HOST` | vacío (además `DEMO_MODE` fuerza modo consola en `mail_service`) |
| `CORS_ORIGINS` | el dominio de Vercel del frontend (ej. `https://consorciosdemo.vercel.app`). Si usás preview deployments de Vercel, cada uno tiene su propio subdominio y no va a estar en la lista |
| `CORS_ORIGIN_REGEX` | **vacío** — el default matchea `localhost` en cualquier puerto y no debe viajar a un deploy público |

El primer arranque necesita una corrida manual del cron (o esperar hasta 6 h):
como no hay seed-on-boot, la base arranca vacía y `/auth/demo-login` devuelve
503 hasta que el generador corra por primera vez.

### Mantener el demo despierto (cold start)

En el plan gratuito de Render el servicio web **se duerme tras ~15 min sin
tráfico** y el primer request paga el arranque en frío. Para un demo linkeado
desde una web de ventas eso es caro: el visitante ve una pantalla en blanco y
asume que el producto está roto.

La solución es un **monitor de uptime externo** pingeando `GET /health` cada
**10 minutos** (Render duerme a los 15; 10 deja margen sin desperdiciar
llamadas). Sirve UptimeRobot, Better Stack o similar.

Se eligió un monitor externo y no un cron dentro del repo por tres razones:

- **GitHub Actions desactiva los workflows programados** en repos sin actividad
  por 60 días. El demo dejaría de despertarse en silencio, y el síntoma sería
  "a veces está lento".
- Un monitor **avisa cuando el servicio se cae**, cosa que un cron genérico no
  hace. Es vigilancia gratis que hoy no existe.
- Un cron dentro de Render gasta cuota de Render para algo que un servicio
  externo hace mejor y sin costo.

`GET /health` es público y no toca la base a propósito: así el ping es barato, y
un problema de base de datos no hace fallar un chequeo que mide si el proceso
está vivo (son dos cosas distintas).

> **El costo real de esta decisión:** Render da **750 horas-instancia por mes**
> en el plan gratuito y un mes tiene ~730 horas. Mantener este servicio despierto
> 24/7 consume prácticamente toda la cuota gratuita de la cuenta. Si hay otro
> servicio gratuito en la misma cuenta, se va a quedar sin horas. La alternativa
> es el plan pago del web service (~7 USD/mes), que no duerme.

> **Otro vencimiento a tener en el calendario:** el Postgres gratuito de Render
> **expira a los 90 días**. Si la base del demo está en ese plan, hay que migrarla
> antes o el demo queda vacío.

### ⚠️ Verificar antes de confiar en el cron: ownership del esquema `public`

El reset ejecuta `DROP SCHEMA public CASCADE`, que **exige que el rol de conexión
sea dueño del esquema `public`**. En Render el usuario que te dan es dueño de la
*base*, pero **no es superusuario**, y ahí la cosa depende de la versión:

- **PostgreSQL 15+** — `public` pertenece a `pg_database_owner`, así que el dueño
  de la base puede dropearlo. **Funciona.**
- **PostgreSQL 14 o anterior** — `public` pertenece al superusuario `postgres`, y
  el dueño de la base **no** puede dropearlo: el cron falla cada 6 h con
  `must be owner of schema public`, en silencio salvo que alguien mire los logs.

Comprobalo una vez contra la base del demo, antes de dar el cron por bueno:

```sql
SELECT version();
SELECT nspname, pg_get_userbyid(nspowner) AS owner
  FROM pg_namespace WHERE nspname = 'public';
```

Si la versión es 14 o menor, no uses `DROP SCHEMA`: cambiá `_resetear_esquema`
(`backend/seed_demo.py`) a la variante portable que ya está documentada en su
comentario — dropear tabla por tabla vía el metadata de SQLAlchemy con `CASCADE`,
que sólo requiere ownership de las tablas propias (las crea el mismo rol vía
`create_all`, así que siempre las posee).

**Estado de verificación:** la rama Postgres del reset está cubierta por un test
que intercepta el SQL emitido y comprueba el orden `DROP` → `CREATE`, pero
**nunca se ejecutó contra un Postgres real** (no había Docker en el entorno de
desarrollo). La primera corrida real del cron es, en los hechos, su primera
prueba: miralo.

---

## Pieza destacada — Cuenta corriente con FIFO

Cada departamento tiene un libro de movimientos contables (`expensa_emitida`, `pago_recibido`, `nota_credito`, `nota_debito`, `interes_punitorio`). El monto es siempre positivo; el `tipo` decide el signo.

El estado de cada expensa (`pendiente | parcial | pagada | vencida`) **no se persiste** — se calcula al vuelo aplicando **First-In-First-Out**: los créditos disponibles cubren primero las expensas más viejas.

Ventajas:
- Cero riesgo de desincronización entre el estado y los movimientos reales.
- Soporta pagos parciales, sobre-pagos, notas de crédito/débito y devoluciones sin schema dedicado.
- Base sólida para que Fase 4 modele intereses punitorios sobre mora.

Implementación en `backend/cuenta_corriente.py` (~80 líneas, función pura, testeada en `tests/test_cuenta_corriente.py`).

---

## Decisiones de diseño que vale destacar

- **OpenAPI-first**: cada endpoint se documenta en `openapi.yaml` antes de implementarse.
- **Snapshot pattern** en liquidaciones: cuando se calcula una liquidación mensual, se congelan los valores de haberes y conceptos vigentes. Cambios futuros a esas tablas no rompen historial.
- **Estados terminales inmutables**: un comprobante aprobado no se puede "des-aprobar"; el admin compensa con nota crédito.
- **Soft-delete** en comprobantes y comunicados: oculta de la vista sin perder el registro contable subyacente.
- **Aislamiento por unidad** en backend: los departamentos solo ven sus propios datos, validado server-side incluso si el frontend manda otro `departamento_id` en el query.

---

## Autor

Matías Bauer — capacitación IISAIA 2026 · matiasbauer@gmail.com

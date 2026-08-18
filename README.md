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

### Esquema de la base

El esquema lo maneja **Alembic**. La app no crea tablas al arrancar.

Poner la base al día (hay que correrlo la primera vez y después de cada `git pull`):

```bash
alembic upgrade head
```

**Agregar o cambiar una columna:**

1. Editar `backend/models.py`.
2. Generar la revisión: `alembic revision --autogenerate -m "descripción del cambio"`
3. **Leer el archivo generado.** La autogeneración acierta casi siempre pero no
   siempre: revisar renombres (los detecta como borrar + crear, y eso pierde datos)
   y los `server_default` de columnas nuevas `NOT NULL` sobre tablas con filas.
4. Aplicarla: `alembic upgrade head`
5. Correr `pytest tests/test_migraciones.py` — la guarda de deriva confirma que
   la migración y los modelos quedaron alineados.
6. Commitear el archivo de revisión junto con el cambio de `models.py`.

**Una base que ya tiene el esquema al día pero nunca vio Alembic** (por ejemplo un
`consorcio.db` local de antes de esta migración) se marca como al día sin
re-aplicar nada:

```bash
alembic stamp head
```

En el deploy no hay que acordarse de nada: el `Procfile` corre `alembic upgrade head`
antes de levantar el servidor, y si una migración falla el servidor **no** arranca.
Es a propósito — un despliegue caído y visible es preferible a uno que sirve tráfico
contra un esquema a medio migrar.

### Archivos adjuntos

Los comprobantes de pago y los adjuntos de presupuestos **no se sirven
públicamente**. Para abrir uno hacen falta dos pasos:

1. El frontend pide la URL a un endpoint autenticado —
   `GET /comprobantes/{id}/archivo` o
   `GET /trabajos/{t}/presupuestos/{p}/archivo`— que valida pertenencia mirando
   la fila en la base. Un departamento que pide el comprobante de otro recibe
   404, no 403: un 403 distinguido confirmaría que ese comprobante existe.
2. Ese endpoint devuelve una **URL firmada de vida corta**
   (`URL_FIRMADA_SEGUNDOS`, 300 por defecto) que el frontend usa como `src`.

El paso extra no es capricho: `<img src>` y `<a href>` no mandan el header
`Authorization`, así que un endpoint protegido por token no se puede usar
directamente como origen de una imagen.

`archivo_path` en las respuestas de la API es la **clave de almacenamiento**, no
una URL. Sirve sólo para saber si hay adjunto.

#### Dónde se guardan

Lo decide `STORAGE_BACKEND`:

- **`local`** (default) — disco, bajo `UPLOAD_DIR`. Es lo que corre en
  desarrollo, en los tests y en CI. No necesita ninguna configuración extra.
- **`s3`** — cualquier almacén S3-compatible. Está probado contra la interfaz,
  no contra un proveedor: sirve igual Supabase Storage, Cloudflare R2 o AWS S3,
  y lo único que cambia es `S3_ENDPOINT_URL`.

#### Pasar a almacén externo

En producción el disco del servicio web es efímero: cada despliegue lo reinicia
y se lleva puestos todos los archivos subidos. Antes de tener un cliente real
hay que mover esto a un almacén externo.

1. Crear el bucket. **Tiene que ser privado.** Si queda público, la firma no
   protege nada: el objeto se abre por su URL directa sin pasar por la API.
2. Cargar las cinco variables `S3_*` del `.env.example`, todavía con
   `STORAGE_BACKEND=local`.
3. Subir lo que ya existe:
   ```bash
   STORAGE_BACKEND=s3 python -m backend.migrar_archivos
   ```
   La clave de cada archivo es su ruta relativa al directorio de subidas, que es
   exactamente lo que ya está guardado en la base. No hace falta tocar ninguna fila.
4. Recién ahí poner `STORAGE_BACKEND=s3` y reiniciar.

Si `STORAGE_BACKEND=s3` y falta alguna credencial, **el sistema no arranca**: es
preferible a que cada subida falle en tiempo de request con un error de la
librería de S3.

### Recuperación de contraseña

Un vecino que olvidó su contraseña la recupera solo, sin que intervenga el
administrador ni el dueño de la plataforma. Son dos pasos:

1. **`POST /auth/recuperar-password`** — recibe un email y manda un link de un
   solo uso. **Responde 202 siempre**, exista o no la cuenta.
2. **`POST /auth/restablecer-password`** — canjea el token del link por una
   contraseña nueva.

En el frontend son `/recuperar-password` y `/restablecer-password`, ambas
públicas y enlazadas desde el login.

#### Las decisiones que no son obvias

**Por qué siempre 202.** Si la respuesta cambiara según el email exista o no,
el formulario se convertiría en un verificador de qué cuentas están registradas
en el sistema. Por eso el código, el cuerpo y el comportamiento son idénticos
para un email registrado, uno inexistente, uno dado de baja y uno que superó el
límite de pedidos. La pantalla del frontend hace lo mismo: muestra el mismo
mensaje incluso si el servidor falla.

**En la base va el hash, no el token.** El token en claro sólo existe en el
email. En `tokens_recuperacion` se guarda su sha256, así que una filtración de
la base no permite resetear la contraseña de nadie. (Alcanza sha256 y no hace
falta bcrypt: el token tiene 256 bits de aleatoriedad, no hay diccionario que lo
adivine.)

**Pedir un link nuevo invalida los anteriores.** Si no, un link viejo reenviado
o filtrado seguiría sirviendo.

**Restablecer baja `must_change_password`.** Sin eso, un usuario con cambio
obligatorio pendiente resetea su clave y sigue recibiendo 403 en todo endpoint
operacional.

**El límite de pedidos se cuenta contra la base**, no en memoria: sobrevive a un
reinicio del servidor y funciona igual con más de una instancia.

#### Probarlo en desarrollo

Sin `SMTP_HOST` configurado, `mail_service` imprime el mensaje en la consola del
backend en vez de mandarlo. El link con el token se lee ahí — es como se prueba
el circuito completo sin cuenta de correo.

En producción hay que configurar `SMTP_*` (ver arriba) y, sobre todo,
**`FRONTEND_URL` con el dominio real**: si queda apuntando a localhost, el link
que recibe el vecino no le sirve.

#### Comprobar que el correo saliente funciona

```bash
python -m backend.probar_email vos@tudominio.com
```

Manda un mensaje de prueba con la configuración cargada y reporta qué usó (sin
imprimir la clave) y qué pasó. Sirve para separar "el correo está mal
configurado" de "el circuito de recuperación tiene un problema", que desde la
pantalla se ven igual.

Devuelve 0 si salió, 1 si falló o si está en modo consola, 2 si no le pasaste
destinatario. Avisa explícitamente cuando `DEMO_MODE` o un `SMTP_HOST` vacío
están haciendo que nada salga de verdad.

**Configuración con Resend** (verificado en su documentación):

```env
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USER=resend
SMTP_PASSWORD=<la API key, empieza con re_>
SMTP_FROM_EMAIL=no-responder@notificaciones.tudominio.com
SMTP_FROM_NAME=Administración del Consorcio
```

El usuario es literalmente `resend` y la contraseña es la API key. El remitente
tiene que pertenecer a un dominio verificado en Resend; ellos recomiendan usar
un **subdominio** (`notificaciones.tudominio.com`) para aislar la reputación de
envío del dominio principal.

**Si el envío dice que el dominio no está verificado pero en el panel figura
verificado:**

```bash
python -m backend.probar_email --dominios
```

Le pregunta a la API de Resend qué dominios ve **esa clave concreta** y los
compara con el remitente configurado. Las dos causas de ese desajuste:

- La clave pertenece a **otra cuenta o equipo** de Resend, distinto de aquel
  donde verificaste el dominio. Se ve porque la lista sale vacía o con otros
  dominios.
- Verificaste un **subdominio** y mandás desde el dominio pelado (o al revés).
  Resend los trata como dominios distintos: verificar
  `notificaciones.midominio.com` no habilita `midominio.com`.

#### Lo que no hace

Restablecer la contraseña **no cierra las sesiones que ya estaban abiertas** con
la contraseña vieja. La lista de revocación del proyecto trabaja por `jti` y no
hay índice de los `jti` vigentes de un usuario. Para el caso que motiva esta
función —"me olvidé la clave"— no hace falta; para "me robaron la cuenta", sí.

### Encontrar errores

Cuando algo falla de forma inesperada, el usuario ve **un código corto**
(`E-7K3MQ9`). Ese código es lo único que viaja del vecino al soporte: con él se
llega a qué pasó, a quién y en qué consorcio.

Se busca en **Super-Admin → Errores**, pegando el código. La pantalla también
lista los últimos, para mirar de vez en cuando si algo está fallando en
silencio.

#### Dónde queda cada error

En **dos lugares**, y en este orden:

1. **La salida del servidor**, siempre. Es la fuente de verdad: sobrevive a que
   la base esté caída, que es justo cuando más se necesita el rastro.
2. **La tabla `errores_registrados`**, si se puede. Es la copia cómoda de
   consultar desde el panel.

Por eso el registro nunca puede levantar una excepción propia: taparía el error
original y le cambiaría la respuesta al usuario. Está fijado por test.

#### Qué se registra y qué no

Sólo lo **inesperado**. Los 404, 403 y errores de validación son parte del
funcionamiento normal: registrarlos ahogaría la tabla y la pantalla.

La traza completa **nunca se le devuelve al usuario** — va al log y a la tabla.
Y sólo la ve el super admin: no se le muestran detalles técnicos del sistema al
administrador de un consorcio.

En el mensaje se tacha lo que parezca contraseña o token. Es **mejor esfuerzo**,
no una garantía: la protección de verdad es no meter payloads en los mensajes de
excepción.

Se conservan `ERRORES_RETENCION_DIAS` (90 por defecto) y después se borran
solos. La purga corre al arrancar el servicio, no en una tarea programada: los
despliegues son suficientemente frecuentes y no amerita una pieza más. Un
servidor que quede meses en pie sin redesplegar no purga.

#### Enterarse sin que nadie avise

Todo lo anterior deja **encontrar** un error, no **enterarse**. Para que llegue
un aviso solo, cargar `SENTRY_DSN` e instalar `sentry-sdk`. Sin eso, el sistema
funciona igual.

Va por variable de entorno y **no por la interfaz** a propósito: tiene que
arrancar antes de que algo pueda fallar, y una configuración guardada en la base
no está disponible si el problema es justamente la base. Si iniciar Sentry falla,
se avisa en el log y el servicio arranca igual — sería absurdo que la
herramienta de avisar errores tire el sistema.

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

**La demo pública no tiene backend.** Corre entera en el navegador: el frontend
de Vercel se sirve con `VITE_DEMO_MODE=true` y `frontend/src/api/client.js:39`
desvía cada llamada a `frontend/src/demo/servidor.js`, que responde desde un
estado en memoria sembrado con `frontend/src/demo/dataset.json` y con la misma
forma que devolvería la API real.

Consecuencias, todas buscadas:

- **No hay servidor ni base de datos que sostener, ni costo de infraestructura.**
  Es la restricción dura que motivó el rediseño: no hay presupuesto de
  infraestructura hasta que haya clientes.
- **Cada visitante tiene su propia copia.** Las escrituras viven en su pestaña.
  Nadie le deja basura al siguiente, y no hace falta ningún reset programado.
- **No se duerme ni se vence.** No hay arranque en frío ni base con fecha de
  caducidad.

Diseño completo y decisiones de alcance: `docs/superpowers/specs/2026-08-16-demo-sin-backend-design.md`.

### Regenerar el dataset

El dataset se genera corriendo el sistema de verdad contra una base local y
exportando el resultado — así lo que muestra la demo es lo que produce el backend,
no números escritos a mano.

```bash
python -m backend.seed_demo --reset --exportar
```

Requiere `DEMO_SEED_PASSWORD` en el `.env` local (no versionado). El generador
tarda 67-69 s. La salida se escribe en `frontend/src/demo/dataset.json`; hay que
commitearla junto al cambio que la motivó.

### Publicar

`.github/workflows/mirror-demo.yml` espeja el estado actual de `master` al
repositorio público del demo como un único commit huérfano (nunca el historial:
hay commits viejos con una base SQLite que contenía hashes de password). Vercel
despliega desde ese repositorio.

### Historia: la demo con backend (retirada)

Hasta el 2026-08-16 la demo corría con backend y Postgres en Render, con un cron
que reseteaba la base cada 6 horas. Se retiró porque el servicio de Render quedó
suspendido, porque todos los visitantes compartían un mismo dataset y se
escribían encima, y por los vencimientos del plan gratuito. Si alguna vez se
vuelve a necesitar una demo con backend, el análisis de por qué se abandonó está
en §1 del spec citado arriba.

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

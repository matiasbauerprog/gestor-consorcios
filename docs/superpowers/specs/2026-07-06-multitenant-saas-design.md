# Multitenant SaaS — diseño

**Fecha:** 2026-07-06
**Estado:** propuesto
**Rama sugerida:** `feature/multitenant`

## 1. Contexto y objetivo

Hoy el sistema es 100% single-tenant: `configuracion_consorcio` es una tabla singleton, ninguna tabla operacional lleva `consorcio_id`, y todos los datos comparten un único scope global. Solo puede administrarse un consorcio por instancia.

Este spec define el rediseño para soportar **SaaS multitenant** con jerarquía:

```
Super-admin (persona única, gestiona el sistema)
  └── Administración (tenant = estudio administrador)
        └── Consorcio (edificio)
              └── Departamento (unidad funcional)
                    └── Usuario (rol: departamento)
        └── Usuario (rol: administracion) — pertenece a la administración
```

**Metas:**

- Aislamiento total entre consorcios (una administración A no puede ver nada de la B).
- Un admin puede gestionar N consorcios de su administración con un único login y un selector en el topbar.
- Alta de administraciones nueva controlada por un super-admin (sin registro público).
- Impersonate y audit log para soporte, con mitigaciones razonables contra abuso.
- Cero cambios de motor de DB (seguimos con SQLite).

**No-metas (fuera de scope):**

- Postgres/MySQL. Se documenta como roadmap futuro, no se implementa.
- Registro público / self-service signup de nuevas administraciones.
- Facturación real / planes con features distintas. La columna `plan` queda como placeholder.
- MFA para super-admin.
- Notificación al admin cuando el super-admin impersona su cuenta.
- Subdominios por tenant (`estudio1.consorcios.app`). Un único dominio.
- Emails transaccionales (invitaciones, reset password por email). Todo el intercambio de credenciales es out-of-band (WhatsApp, email personal).

## 2. Arquitectura y jerarquía

### 2.1. Roles

- **`super_admin`** (nuevo): cuenta única del operador del sistema. Cero acceso a datos operacionales. Solo administra tenants + impersonate + audit log + métricas.
- **`administracion`** (existente): pertenece a una `administración`. Acceso completo a todos los consorcios de esa administración.
- **`representante`** (existente): pertenece a **un** consorcio específico. Roles operativos limitados según reglas actuales.
- **`departamento`** (existente): pertenece a un departamento, que pertenece a un consorcio.

### 2.2. Unidades de aislamiento

- **Administración** = unidad de tenancy comercial. Si se suspende, se bloquea el login de todos sus usuarios (admin, depto y rep de todos sus consorcios).
- **Consorcio** = unidad de aislamiento de datos operacionales. Cada consorcio tiene sus propios departamentos, expensas, gastos, cajas, empleados, proveedores, comunicados, amenities, clases de prorrateo, coeficientes, haberes y conceptos de liquidación.
- **Catálogos**: todo por consorcio. Nada se comparte a nivel administración. Si "Ferretería Juan" atiende a 3 consorcios de la misma administración, hay que cargarlo 3 veces. Trade-off aceptado (data-entry vs. simplicidad de modelo).

## 3. Modelo de datos

### 3.1. Tablas nuevas

#### `administraciones`

| Columna | Tipo | Constraints | Notas |
|---|---|---|---|
| id | int | PK | |
| razon_social | str(255) | NOT NULL | |
| cuit | str(13) | NOT NULL, unique | |
| email_contacto | str(255) | NOT NULL | |
| activa | bool | NOT NULL, default true | Si false, bloquea login de todos los usuarios del tenant |
| plan | str(50) | NOT NULL, default `"free"` | Placeholder, sin lógica funcional por ahora |
| fecha_creacion | datetime | NOT NULL, server_default now | |

#### `consorcios`

Reemplaza el singleton `configuracion_consorcio`. Absorbe **todos** sus campos y suma:

| Columna | Tipo | Constraints | Notas |
|---|---|---|---|
| id | int | PK | |
| administracion_id | int | FK → administraciones, NOT NULL, index | |
| nombre | str(255) | NOT NULL | Antes `consorcio_nombre` |
| usa_personal_propio | bool | NOT NULL, default true | Feature flag: si false, oculta módulo Personal en sidebar |
| consorcio_domicilio | str(500) | NOT NULL | |
| consorcio_cuit | str(13) | NOT NULL | (No unique — dos admins pueden llegar a cargar el mismo por error, se valida en UI) |
| consorcio_convenio_suterh | str(50) | nullable | |
| admin_nombre | str(255) | NOT NULL | |
| admin_domicilio | str(500) | NOT NULL | |
| admin_email | str(255) | NOT NULL | |
| admin_telefono | str(50) | NOT NULL | |
| admin_cuit | str(13) | NOT NULL | |
| admin_rpa | str(50) | NOT NULL | |
| admin_situacion_fiscal | str(100) | NOT NULL | |
| banco_titular | str(255) | NOT NULL | |
| banco_nombre | str(100) | NOT NULL | |
| banco_sucursal | str(50) | nullable | |
| banco_numero_cuenta | str(50) | NOT NULL | |
| banco_cbu | str(22) | NOT NULL | |
| banco_alias | str(50) | nullable | |
| dia_primer_vencimiento | int | NOT NULL, default 10 | |
| dias_entre_vencimientos | int | NOT NULL, default 10 | |
| recargo_segundo_vencimiento_pct | float | NOT NULL, default 7.0 | |
| tasa_interes_mensual_pct | float | NOT NULL, default 3.0 | |
| caja_default_pagos_id | int | FK → cajas nullable | |
| reportes_visibles_a_depto | bool | NOT NULL, default false | |
| fecha_creacion | datetime | NOT NULL, server_default now | |

#### `audit_log_super_admin`

| Columna | Tipo | Constraints | Notas |
|---|---|---|---|
| id | int | PK | |
| super_admin_usuario_id | int | FK → usuarios, NOT NULL | Quién realizó la acción |
| accion | str(80) | NOT NULL | Ver §5.3 |
| administracion_id_afectada | int | FK → administraciones, nullable | |
| motivo | str(500) | nullable | Obligatorio para `impersonate_start` |
| detalles | str(2000) | nullable | JSON con contexto extra (path, método, body abreviado) |
| fecha | datetime | NOT NULL, server_default now, index | |

### 3.2. Modificaciones a `usuarios`

- Agregar `super_admin` al enum `Rol`.
- Agregar `administracion_id: int` FK → `administraciones`, nullable, index.
- Agregar `must_change_password: bool` NOT NULL default false.
- Constraints por rol (validados en Pydantic + CHECK en SQL):
  - `super_admin`: `administracion_id` NULL, `departamento_id` NULL.
  - `administracion`: `administracion_id` NOT NULL, `departamento_id` NULL.
  - `representante`: `administracion_id` NULL, `departamento_id` NULL. (Su vínculo con el consorcio se resuelve por otra tabla o convención — ver §3.5.)
  - `departamento`: `administracion_id` NULL, `departamento_id` NOT NULL.
- `email` sigue siendo unique global (no scoped por tenant). Simplifica login.

### 3.3. Modificaciones a `departamentos`

- Agregar `consorcio_id: int` FK → `consorcios`, NOT NULL, index.
- `codigo` deja de ser unique global, pasa a unique por consorcio: `UniqueConstraint("consorcio_id", "codigo")`.

### 3.4. Agregar `consorcio_id` a tablas operacionales

Todas las tablas siguientes reciben `consorcio_id: int` FK → `consorcios`, NOT NULL, index:

- `expensas`, `expensa_detalle`, `comprobantes`, `movimientos_cuenta`, `periodos_cerrados`
- `gastos`, `gastos_habituales`
- `peticiones`, `trabajos`, `trabajos_recurrentes`, `presupuestos`
- `comunicados`, `amenities`, `reservas`
- `cajas`, `movimientos_caja`, `transferencias_caja`
- `clases_prorrateo`, `coeficientes_departamento`, `proveedores`
- `empleados`, `haberes`, `conceptos_liquidacion`
- `liquidaciones_empleado`, `liquidaciones_haber`, `liquidaciones_detalle`
- `notificaciones`

### 3.5. Vínculo de representante con consorcio

Los representantes hoy no tienen columna que los ate a un consorcio. Opciones:

1. Agregar `consorcio_id: int` FK nullable a `usuarios` (para representantes).
2. Tabla nueva `representantes_consorcio(usuario_id, consorcio_id)` con unique.

**Decisión:** opción 1. Un representante = un consorcio. Se agrega `usuarios.consorcio_id: int` FK nullable. Constraints:

- `representante`: `consorcio_id NOT NULL`.
- `super_admin`, `administracion`, `departamento`: `consorcio_id NULL`.

El vínculo del depto con su consorcio se resuelve siempre por `departamento_id → departamentos.consorcio_id`. **No** se replica en `usuarios.consorcio_id` para depto — evita drift silencioso si un depto cambia de consorcio.

### 3.6. Uniques globales que pasan a ser scoped

| Tabla | Antes | Después |
|---|---|---|
| `departamentos.codigo` | unique global | unique `(consorcio_id, codigo)` |
| `proveedores.cuit` | unique global | unique `(consorcio_id, cuit)` |
| `amenities.nombre` | unique global | unique `(consorcio_id, nombre)` |
| `clases_prorrateo.codigo` | unique global | unique `(consorcio_id, codigo)` |
| `cajas.nombre` | unique global | unique `(consorcio_id, nombre)` |
| `haberes.nombre` | unique global | unique `(consorcio_id, nombre)` |
| `conceptos_liquidacion.nombre` | unique global | unique `(consorcio_id, nombre)` |
| `empleados.cuil` | unique global | unique `(consorcio_id, cuil)` |
| `expensas` `uq(depto, periodo)` | | agrega `consorcio_id` |
| `liquidaciones_empleado` `uq(empleado, periodo)` | sigue igual (empleado ya es por consorcio) | sin cambios |
| `coeficientes_departamento` `uq(depto, clase)` | sigue igual (ambos ya son por consorcio) | sin cambios |

### 3.7. Índices

Cada `consorcio_id` FK va con `index=True`. La mayoría de queries filtran primero por `consorcio_id` + otra columna. Idealmente los índices compuestos existentes se extienden con `consorcio_id` al frente. El detalle de qué índices reformar se decide en el plan de implementación (algunos tal vez no valgan la pena rehacer si SQLite ya usa el índice existente).

## 4. Auth y contexto de request

### 4.1. Login

`POST /auth/login` (público, path idéntico):

- Body: `{email, password}` (sin cambios).
- Valida credenciales.
- **Chequeo nuevo:** si el usuario tiene rol `administracion`, `representante` o `departamento` y su administración está `activa=false`, responde 403 con `{"detail": "administracion_suspendida"}`. La administración se deriva por rol:
  - `administracion`: `usuarios.administracion_id`.
  - `representante`: `usuarios.consorcio_id → consorcios.administracion_id`.
  - `departamento`: `usuarios.departamento_id → departamentos.consorcio_id → consorcios.administracion_id`.
- Respuesta: `{token, user, must_change_password}` donde `user` incluye:
  - Común: `id, email, rol`.
  - Para `administracion`: `administracion_id`, `administracion_nombre`, `consorcios: [{id, nombre}]` (todos los del tenant).
  - Para `departamento`: `departamento_id, consorcio_id, consorcio_nombre`.
  - Para `representante`: `consorcio_id, consorcio_nombre`.
  - Para `super_admin`: solo campos comunes.

### 4.2. JWT

Solo lleva `sub = user_id`. Ni `administracion_id` ni `consorcio_id`. El backend resuelve todo por lookup en cada request.

**Excepción:** JWT de impersonate lleva claims extra:
```
{ sub: usuario_id_impersonado, impersonated_by: super_admin_id, exp: now+15min }
```

### 4.3. Headers de request autenticado

| Header | Cuándo | Roles |
|---|---|---|
| `Authorization: Bearer <jwt>` | Siempre | Todos |
| `X-Consorcio-Id: <int>` | Endpoints operacionales | admin, depto, representante |

**Endpoints exentos de `X-Consorcio-Id`:**

- `POST /auth/login`, `POST /auth/logout`
- `GET /me`, `GET /me/consorcios`, `POST /me/cambiar-password`
- Todo `/super-admin/*`
- `GET /consorcios` (listado del tenant — el admin ve los suyos, otros roles 403)
- `POST /consorcios` (alta — todavía no hay consorcio activo)

Todos los demás endpoints operacionales exigen `X-Consorcio-Id`. Si falta → 400. Si el usuario no tiene acceso a ese consorcio → 403.

### 4.4. Dependency chain

Nuevo archivo `backend/tenant.py`:

```python
CurrentUser = Annotated[Usuario, Depends(get_current_user)]

def get_consorcio_activo(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> int:
    """Resuelve X-Consorcio-Id, valida acceso, devuelve el ID."""
    cid = request.headers.get("X-Consorcio-Id")
    if not cid:
        raise HTTPException(400, "X-Consorcio-Id requerido")
    cid = int(cid)
    if user.rol == Rol.administracion:
        ok = db.query(Consorcio.id).filter(
            Consorcio.id == cid,
            Consorcio.administracion_id == user.administracion_id,
        ).first() is not None
    elif user.rol == Rol.representante:
        ok = user.consorcio_id == cid
    elif user.rol == Rol.departamento:
        depto = db.query(Departamento).filter(Departamento.id == user.departamento_id).first()
        ok = depto is not None and depto.consorcio_id == cid
    else:
        raise HTTPException(403)
    if not ok:
        raise HTTPException(403, "sin acceso a este consorcio")
    return cid
```

Cada router operacional agrega `cid: int = Depends(get_consorcio_activo)` y filtra por `consorcio_id == cid` en todas las queries. **Nunca** confiar en `consorcio_id` en el body — mismo principio que hoy con `usuario_id` / `departamento_id`.

### 4.5. Endpoints nuevos

| Método | Path | Rol | Propósito |
|---|---|---|---|
| GET | `/me/consorcios` | admin, depto, rep | Consorcios accesibles al usuario (para el selector) |
| POST | `/me/cambiar-password` | cualquiera autenticado | Cambia password propia. Setea `must_change_password=false` |
| GET | `/consorcios` | admin | Lista todos los consorcios del tenant (para el CRUD del sidebar). Semánticamente distinto de `/me/consorcios`: este exige rol admin y devuelve la representación completa (para la pantalla de gestión), no solo `{id, nombre}` |
| POST | `/consorcios` | admin | Alta de consorcio nuevo dentro de la administración. Body incluye `usa_personal_propio` |
| GET | `/consorcios/{id}` | admin (del tenant), depto/rep (del consorcio) | Reemplaza `GET /configuracion` |
| PATCH | `/consorcios/{id}` | admin | Edición del consorcio, incluyendo `usa_personal_propio` (reemplaza `PUT /configuracion`) |
| GET | `/super-admin/administraciones` | super_admin | Listado |
| POST | `/super-admin/administraciones` | super_admin | Alta (crea admin + primer usuario admin) |
| GET | `/super-admin/administraciones/{id}` | super_admin | Detalle |
| PATCH | `/super-admin/administraciones/{id}` | super_admin | Editar |
| POST | `/super-admin/administraciones/{id}/suspender` | super_admin | Toggle activa |
| POST | `/super-admin/administraciones/{id}/reset-password/{user_id}` | super_admin | Genera password temporal, devuelve una vez, setea `must_change_password=true` |
| POST | `/super-admin/impersonate/start` | super_admin | Body: `{usuario_id, motivo}`. Devuelve JWT temporal 15min |
| POST | `/super-admin/impersonate/end` | super_admin (con JWT impersonado) | Revoca la sesión de impersonate |
| GET | `/super-admin/metricas` | super_admin | Agregados globales |
| GET | `/super-admin/audit-log` | super_admin | Log paginado con filtros |

### 4.6. Deprecaciones controladas

`GET /configuracion` y `PUT /configuracion` se marcan `deprecated: true` en OpenAPI. Se mantienen 1 versión redirigiendo internamente a `/consorcios/{cid}` donde `cid = X-Consorcio-Id`. Después se eliminan.

## 5. Super-admin

### 5.1. Cuenta y seed inicial

- Un solo super-admin por instancia.
- Cuenta física separada: constraint DB fuerza que `rol=super_admin` implique `administracion_id NULL` y `departamento_id NULL`.
- Seed: `backend/seed_super_admin.py`. Idempotente. Toma `SUPER_ADMIN_EMAIL` y `SUPER_ADMIN_PASSWORD` de env vars. Si ya existe, sale silencioso (a menos que se pase `--force`).
- Sin recuperación automática. Reset manual corriendo el seed con `--force`.

### 5.2. Flujo de impersonate

```
1. Super-admin → /super-admin/administraciones/{id}
2. Lista usuarios del tenant
3. Click "Impersonar"
4. Modal exige MOTIVO (obligatorio, texto libre, mín 10 chars)
   Ej: "Ticket #123 – no aparecen expensas julio"
5. POST /super-admin/impersonate/start {usuario_id, motivo}
   - Backend valida: super_admin no está ya impersonando (sesión activa detectada por audit_log)
   - Genera JWT con exp=now+15min y claims:
     { sub: usuario_id, impersonated_by: super_admin_id }
   - Loguea "impersonate_start" en audit_log con motivo
   - Devuelve el JWT temporal
6. Frontend:
   - Guarda JWT original en sessionStorage.impersonate_original
   - Reemplaza el JWT activo con el temporal
   - Muestra banner rojo fijo arriba:
     "⚠ Impersonando a maria@estudiolopez.com. Motivo: [motivo]. Salir en 12:34"
7. Super-admin opera como el usuario impersonado
   - Cada POST/PATCH/DELETE queda logueado por middleware
     (detecta claim impersonated_by y crea fila en audit_log)
8. Al terminar (click "Salir") o expirar:
   - POST /super-admin/impersonate/end
   - Loguea "impersonate_end"
   - Frontend restaura JWT original desde sessionStorage
   - Redirect a /super-admin
```

**Reglas duras:**

- Sin renovación del token. Si expira mid-acción → 401, hay que empezar de nuevo. Frontend muestra modal de aviso a los 13 min ("Quedan 2 min de impersonate. ¿Salir ahora?").
- Sin impersonate anidado: super-admin dentro de impersonate no puede iniciar otro impersonate (403).
- Ciertas rutas `/super-admin/*` quedan bloqueadas durante impersonate activo (403), ej: no puede crear otra administración estando disfrazado. En la práctica: el JWT temporal (con `sub` = usuario impersonado) no da acceso a rutas `/super-admin/*` excepto `impersonate/end`.

### 5.3. Audit log — qué se loguea

**Acciones directas del super-admin:**

- `crear_admin`, `editar_admin`, `suspender_admin`, `reactivar_admin`
- `reset_password` (guarda `usuario_id` afectado, NUNCA la password nueva)
- `impersonate_start` (con motivo), `impersonate_end`

**Acciones durante impersonate (via middleware):**

- Todo método mutante (`POST/PUT/PATCH/DELETE`) de cualquier endpoint. Se guarda: método, path, `administracion_id_afectada` (derivada del consorcio activo), body abreviado (primeros 500 chars). Cualquier campo cuyo nombre matchee `/password|token|secret/i` se reemplaza por `"[REDACTED]"` antes de serializar.

**Lo que NO se loguea:**

- `GET` durante impersonate (para no explotar el log — el motivo del `impersonate_start` ya deja constancia de la sesión).

**Retención:** sin política de purga. Tabla crece indefinida.

### 5.4. Métricas

`GET /super-admin/metricas`:

```json
{
  "administraciones": { "activas": 12, "suspendidas": 3, "total": 15 },
  "consorcios": { "total": 47 },
  "departamentos": { "total": 892 },
  "expensas_ultimo_mes": { "emitidas": 723, "monto_total": 12500000.00 },
  "impersonates_ultimos_30_dias": 5
}
```

Agregados globales, sin drill-down por tenant (el listado de administraciones cubre "cuántos consorcios tiene cada una"). No se expone monto por tenant en la métrica agregada.

### 5.5. Sidebar del super-admin

Sidebar completamente distinto, 3 items sin acordeón:

- Administraciones
- Métricas
- Audit log

Sin acceso a los módulos operacionales. Si navega manualmente a `/expensas` → redirect a `/super-admin/administraciones`.

## 6. UX del admin

### 6.1. Login y post-login

- Login sigue igual: form email + password.
- Post-login según rol y contexto:
  - **admin con 1 consorcio:** `/` con `X-Consorcio-Id` automático.
  - **admin con 2+ consorcios:** `/` con selector visible arriba. Consorcio activo = último de localStorage o el primero por orden alfabético.
  - **admin con 0 consorcios:** `/bienvenida` con CTA "+ Crear tu primer consorcio" que dispara el wizard.
  - **depto y representante:** `/` con `X-Consorcio-Id` automático. Selector oculto.
  - **super_admin:** `/super-admin/administraciones`.
- Si `must_change_password=true`, cualquier ruta (excepto `/mi-usuario/cambiar-password`) redirige ahí. Después de cambiar la password, se pone `false` y sigue el flujo normal.

### 6.2. Topbar

```
┌──────────────────────────────────────────────────────────────────┐
│ ☰ Gestión de Consorcios   [Edificio Rivadavia 100 ▾]   🔔 👤    │
└──────────────────────────────────────────────────────────────────┘
```

- **Selector de consorcio:** dropdown al lado del logo. Visible solo si el usuario tiene 2+ consorcios accesibles. Muestra el nombre del consorcio activo.
- Click abre lista de todos los consorcios accesibles (nombre + código/dirección corta).
- Al elegir uno:
  1. Actualiza `localStorage.consorcio_activo_id`.
  2. Actualiza el header `X-Consorcio-Id` del `fetch` wrapper.
  3. Refetch de la pantalla actual. Si la ruta tiene IDs que no pertenecen al nuevo consorcio (ej: `/gastos/17` donde `17` es de otro consorcio), redirect a la ruta base del módulo (ej: `/gastos`).
- **Banner de impersonate:** banda roja fija arriba de todo cuando el JWT activo tiene claim `impersonated_by`. Botón "Salir" que llama a `/super-admin/impersonate/end`.

### 6.3. Sidebar

Reutiliza la arquitectura de `Sidebar.jsx` actual (grupos + `ORDEN_DEPTO` para depto). Cambios:

- **super_admin:** sidebar propio con 3 items (§5.5), sin acordeón.
- **admin:**
  - "Datos del consorcio" (hoy `/configuracion`) → ruta frontend `/consorcios/activo` (que resuelve el `cid` desde el consorcio activo del selector). Backend: `GET /consorcios/{cid}`.
  - Nuevo item bajo "Configuración": **"Consorcios de la administración"** → ruta frontend `/administracion/consorcios`. Backend: `GET /consorcios` (listado del tenant). Muestra todos los consorcios con acciones (editar, agregar). Es el punto de entrada al wizard.
  - Si el consorcio activo tiene `usa_personal_propio == false`, el grupo "Personal" no se renderiza para el admin en ese consorcio (feature flag). Se re-evalúa al cambiar de consorcio.
- **depto y representante:** sin cambios visuales.

### 6.4. Wizard de alta de consorcio

Desde `/administracion/consorcios` → "+ Nuevo consorcio". Página dedicada `/administracion/consorcios/nuevo` con 4 pasos y barra de progreso arriba.

**Paso 1 — Datos del consorcio:**
- Nombre, domicilio, CUIT, convenio SUTERH (opcional).
- Toggle "El consorcio administra personal propio (encargados, ayudantes)". Default: sí.

**Paso 2 — Datos de la administración:**
- Nombre de la administración, domicilio, email, teléfono, CUIT, RPA, situación fiscal.
- **Pre-fill inteligente:** si la administración ya tiene otros consorcios, botón "Usar los datos del último consorcio creado". Copia los valores para no re-tipear.

**Paso 3 — Datos bancarios:**
- Titular, banco, sucursal, número de cuenta, CBU, alias.
- Idem pre-fill del paso 2.

**Paso 4 — Vencimientos e intereses:**
- Día primer vencimiento (default 10), días entre vencimientos (default 10), recargo 2do venc % (default 7), tasa interés mensual % (default 3).
- Toggle "Los deptos pueden ver reportes" (default off).

**Botón "Crear consorcio"** al final: `POST /consorcios` con todo el payload en un body. En caso de éxito el backend crea, en la misma transacción:

- El consorcio.
- **1 caja default** "Banco principal" (tipo `banco`, apuntando al CBU cargado). Se setea como `caja_default_pagos_id` del consorcio.
- **1 clase de prorrateo** "General" con código `GRAL` (asignable a los deptos con coeficientes que sumen 100%).

Frontend redirige a `/administracion/consorcios` con toast "Consorcio creado. Cargá los departamentos para empezar a operar." El selector del topbar se actualiza y queda posicionado en el nuevo consorcio.

### 6.5. Onboarding del super-admin al crear administración

Formulario único desde `/super-admin/administraciones/nueva`:

- **Datos de la administración:** razón social, CUIT, email de contacto.
- **Primer usuario admin:** email, password inicial (autogenerada de 12 chars alfanuméricos, mostrada una vez con botón "copiar"). Se setea `must_change_password=true`.
- Sin email transaccional. El super-admin comunica la password al admin por canal externo.

### 6.6. Cambio de password obligatorio

Nueva columna `usuarios.must_change_password` (§3.2). Se pone `true` cuando:

- Super-admin crea un admin nuevo.
- Super-admin resetea password de un admin.

Al hacer login con `must_change_password=true`:

- Frontend solo permite `/mi-usuario/cambiar-password`. Cualquier otra ruta redirige ahí.
- `POST /me/cambiar-password` con `{password_actual, password_nueva}`. Backend cambia y pone `must_change_password=false`.

### 6.7. Fetch wrapper del frontend

Un único punto (probablemente `frontend/src/api/apiFetch.js`) que:

- Agrega `Authorization: Bearer <jwt>` desde AuthContext.
- Agrega `X-Consorcio-Id: <consorcio_activo_id>` desde localStorage, **excepto** en los endpoints exentos listados en §4.3.
- Si el backend responde 403 `administracion_suspendida` → forzar logout con mensaje.
- Si responde 401 → limpiar tokens y redirigir a login.

## 7. Migración y seed

### 7.1. Estrategia

Sin Alembic. El proyecto usa `Base.metadata.create_all()` en el lifespan hook. Para la migración a multitenant hay que modificar datos existentes, no solo crear tablas. Solución: script único idempotente.

### 7.2. Script `backend/migrate_multitenant.py`

Idempotente. Detecta si ya migró (`SELECT 1 FROM administraciones LIMIT 1`) y sale silencioso.

Pasos en orden:

1. **Tablas nuevas ya existen** al arrancar el server (Base.metadata.create_all las creó).
2. **Crear administración "Demo"** con id=1: razón social "Administración Demo", CUIT `30-00000000-0`, email `demo@example.com`, activa, plan `"free"`.
3. **Migrar `configuracion_consorcio` → `consorcios`**:
   - Si hay una fila en `configuracion_consorcio`: copiar todos los campos a `consorcios` con `administracion_id = admin.id`, `nombre = cfg.consorcio_nombre`, `usa_personal_propio = true`.
   - Si no hay ninguna fila (DB fresca): crear un consorcio "Consorcio Demo" con defaults sensatos.
4. **Popular `consorcio_id`** en todas las tablas operacionales: `UPDATE tabla SET consorcio_id = :cid` para cada una en la lista de §3.4.
5. **Asignar `administracion_id`** a usuarios admin: `UPDATE usuarios SET administracion_id = :aid WHERE rol = 'administracion'`.
6. **Drop `configuracion_consorcio`**: `DROP TABLE configuracion_consorcio`.
7. **Commit.**

### 7.3. Restricción de SQLite y "table rebuild"

SQLite no soporta `ALTER TABLE ADD COLUMN NOT NULL FK` sin default. Para las tablas existentes que reciben `consorcio_id NOT NULL FK`:

1. `ALTER TABLE ... ADD COLUMN consorcio_id INTEGER` (nullable).
2. `UPDATE ... SET consorcio_id = :cid` (paso 4 del script).
3. Recrear la tabla con constraint NOT NULL + FK vía patrón table-rebuild: `CREATE TABLE ..._new (...)`, `INSERT INTO ..._new SELECT ... FROM ...`, `DROP TABLE ...`, `ALTER TABLE ..._new RENAME TO ...`, recrear índices.

Detalle línea por línea, tabla por tabla, se define en el plan de implementación. Documentar cada rebuild como una función en el script.

### 7.4. Cómo se corre

- **Local dev:** `python -m backend.migrate_multitenant` una sola vez.
- **Automatizado (opcional):** endpoint interno `POST /admin/migrar` protegido por header `X-Bootstrap-Token` (env var). Útil si eventualmente hay CI/CD.

### 7.5. Seed del super-admin

`backend/seed_super_admin.py`:

- Idempotente. Si existe un usuario con rol `super_admin`, sale silencioso (a menos que `--force`).
- Toma `SUPER_ADMIN_EMAIL` y `SUPER_ADMIN_PASSWORD` de env vars. Falla ruidoso si faltan.
- `--force` resetea el password del super-admin existente.

Uso:

```
SUPER_ADMIN_EMAIL=root@sistema.com SUPER_ADMIN_PASSWORD=<pass> python -m backend.seed_super_admin
```

### 7.6. Seed demo (opcional)

`backend/seed_demo.py` detrás de flag `--demo`. Crea:

- 2 administraciones demo.
- 2 consorcios por administración.
- 1 admin user por administración.
- 3-4 deptos por consorcio + un user por depto.
- Algunos comunicados y expensas de ejemplo.

Útil para demo en clase. No se corre en el path de arranque normal.

## 8. Estrategia de tests

### 8.1. Tests de migración

`tests/test_migracion_multitenant.py`:

- **Fresh:** DB vacía con schema pre-migración. Correr script. Assertar `administraciones` tiene 1 fila, `consorcios` tiene 1 fila con defaults esperados.
- **Idempotencia:** correr el script 2 veces. La 2da vez no hace cambios ni rompe.
- **Datos existentes:** cargar dataset chico (2 deptos, 3 expensas, 1 gasto) en schema viejo, migrar, verificar que todas las filas tienen `consorcio_id = 1` y que `configuracion_consorcio` ya no existe.

### 8.2. Tests de aislamiento (críticos)

`tests/test_aislamiento_multitenant.py`:

- Crear 2 administraciones, cada una con 1 consorcio, cada uno con 1 admin, 1 depto y 1 expensa.
- Para cada endpoint operacional (subset representativo — expensas, gastos, comprobantes, comunicados, cajas, empleados):
  - Login admin A. Setear `X-Consorcio-Id` al consorcio de A. Listar recursos → recibe solo los suyos (nunca los de B).
  - Login admin A. Setear `X-Consorcio-Id` al consorcio de B → 403.
  - Login admin A. Omitir `X-Consorcio-Id` → 400.

Estos tests son la garantía dura del aislamiento. Si alguno falla, la implementación está mal.

### 8.3. Tests de super-admin

`tests/test_super_admin.py`:

- Alta de administración + primer admin. Devuelve password autogenerada. Login como el nuevo admin funciona pero pide cambio de password.
- Suspender administración: sus usuarios ya no pueden loguear (403 `administracion_suspendida`).
- Reset password: setea `must_change_password=true`, devuelve nueva password.
- Impersonate happy path: `start` devuelve JWT con `impersonated_by`. Requests con ese JWT modifican datos y quedan logueadas. `end` revoca.
- Impersonate sin motivo → 400.
- Impersonate con motivo <10 chars → 400.
- Impersonate anidado → 403.
- Super-admin sin impersonate no puede acceder a endpoints operacionales.

### 8.4. Tests de rol super_admin fuera de scope

- Login super_admin. GET `/expensas` → 403.
- Login super_admin. GET `/consorcios/1` → 403.

### 8.5. Cobertura por router

Todos los routers existentes suman una batería mínima de:

- 401 (sin JWT).
- 400 (sin `X-Consorcio-Id`).
- 403 (con `X-Consorcio-Id` de otro tenant).
- 200 (happy path con `X-Consorcio-Id` propio, solo devuelve datos del propio consorcio).

Se puede compartir un fixture `dos_consorcios` en `conftest.py`.

## 9. OpenAPI y documentación

- `openapi.yaml` se actualiza **antes** de tocar los routers (openapi-first).
- Se define un `parameter` reusable `ConsorcioIdHeader` que todo endpoint operacional incluye en su `parameters`.
- Se documentan los códigos de error nuevos: 400 `x-consorcio-id-faltante`, 403 `sin-acceso-consorcio`, 403 `administracion-suspendida`, 403 `impersonate-anidado`.
- Los endpoints super-admin se agrupan bajo el tag `super-admin`.
- Los endpoints de configuracion viejos (`GET/PUT /configuracion`) se marcan `deprecated: true`.
- README actualizado con sección "Migración a multitenant" (§7.4 comandos).

## 10. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Un router olvida el filtro `consorcio_id` en un query → leak entre tenants | Tests de aislamiento §8.2 en cada router. Helper `scope()` centralizado que fuerza el uso. Code review manual. |
| Bug en el resolver `get_consorcio_activo` → acceso incorrecto | Tests dedicados al resolver con matrix rol × consorcio propio/ajeno. |
| Super-admin comprometido → catástrofe | Cuenta separada, motivo obligatorio para impersonate, sesión limitada, audit log. MFA deferido a roadmap. |
| Impersonate se usa como backdoor sin motivo real | Audit log revisable. En una V2 se puede agregar notificación al tenant afectado. |
| Migración corrupta datos productivos | El proyecto es académico sin datos productivos hoy. El script es idempotente. Tests de migración cubren fresh + con-datos. |
| SQLite table-rebuild deja índices sin recrear | Cada función de rebuild en el script recrea explícitamente los índices de la tabla original. Test smoke tras migración corre EXPLAIN QUERY PLAN en queries típicas. |
| Confusión de scope entre admins con muchos consorcios (ej: creo un gasto pensando que estoy en Rivadavia pero estaba en San Martín) | Selector siempre visible en topbar, altamente contrastado. Toast al cambiar de consorcio: "Ahora estás en Rivadavia 100". |
| `X-Consorcio-Id` en el header es manipulable por el cliente | Es el punto de la validación server-side. El backend valida acceso en cada request. No hay confianza en el header, solo en el resolver. |

## 11. Roadmap futuro (fuera de scope)

- Postgres + Row-Level Security como mitigación adicional al filtro por app.
- MFA para super-admin (TOTP).
- Notificación al admin cuando su cuenta es impersonada.
- Registro público self-service de administraciones (email verification).
- Facturación real: planes con límites (max consorcios, max deptos, features gated).
- Subdominios por administración (`estudio1.consorcios.app`).
- Emails transaccionales (invitación, reset password por link con token).
- Compartir catálogos a nivel administración (proveedores globales del tenant).
- Multi-tenant en la capa de logs y observabilidad (marcar cada log con `administracion_id`).

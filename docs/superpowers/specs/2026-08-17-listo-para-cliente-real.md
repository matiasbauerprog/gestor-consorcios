# Listo para cliente real — spec de puesta en producción

**Fecha:** 2026-08-17
**Estado:** aprobado en sus decisiones de fondo; pendiente de descomponer en planes por frente.

## Contexto

La demo pública está terminada y publicada (frontend en Vercel, backend y Postgres en Render,
todo en plan gratuito). El sistema está funcionalmente completo: 1082 tests verdes, multitenant
de 3 niveles (Administración → Consorcio → Departamento), 4 roles, y los módulos de expensas,
cuenta corriente, gastos, personal/liquidaciones, comunicados, amenities y peticiones.

Lo que falta **no es funcionalidad**: es lo que separa una demo de un sistema al que un
consorcio le confía su contabilidad y los datos bancarios de sus vecinos.

Este documento fija el alcance, el orden y el esfuerzo de ese trabajo.

## Decisiones tomadas

| Tema | Decisión | Razón |
|---|---|---|
| Archivos subidos | Almacén de objetos externo, S3-compatible | Resuelve a la vez la pérdida por redeploy y el agujero de privacidad; costo ~0 al volumen real |
| Recuperación de contraseña | Autoservicio por email | Con 50 departamentos, el reseteo manual es una interrupción semanal |
| Correo saliente | Proveedor transaccional con interfaz SMTP | `mail_service.py` ya habla SMTP: cambio de configuración, no de código. Entregabilidad y rebotes visibles |

## Hallazgos que motivan el alcance

### H1 — Los comprobantes se pierden en cada despliegue

`backend/storage.py:35` y `backend/routers/presupuestos.py:56` escriben en `UPLOAD_DIR`, un
directorio del filesystem local. En Render el disco del servicio web es efímero: cada deploy
lo reinicia. Todo comprobante de pago y todo presupuesto adjunto cargado desde el deploy
anterior desaparece. La fila en la base sobrevive con un `archivo_path` que ya no resuelve.

### H2 — Los comprobantes son públicos

`backend/main.py:357` monta `/uploads` con `StaticFiles`, sin dependencia de autenticación.
`ComprobanteOut` (`backend/schemas.py:179-183`) serializa `archivo_path` a `/uploads/<path>`.
Cualquiera con la URL ve el archivo sin estar logueado. Los nombres son UUID hex, así que no
son adivinables, pero la URL queda en el historial del navegador, se puede reenviar, y no hay
ningún control de quién mira el comprobante de quién. Son fotos de transferencias bancarias.

### H3 — El esquema se migra a mano

No hay Alembic. `backend/main.py` arranca con `Base.metadata.create_all()` (línea 230) más
nueve funciones `_migrar_*` escritas a mano (líneas 59-229) que hacen `ALTER TABLE` idempotentes.
Funciona hoy porque cada cambio se agregó con cuidado, pero: no hay orden garantizado, no hay
rollback, no hay registro de qué versión corre cada base, y cada cambio futuro es un `ALTER`
artesanal contra datos de un cliente que paga. Es el frente con mayor costo diferido.

**Agravante detectado al planificar el frente 1:** las nueve funciones están dentro de un
`if get_settings().DATABASE_URL.startswith("sqlite")` (`backend/main.py:232`). **En PostgreSQL
no corre ninguna.** En producción el esquema saldría exclusivamente de `create_all()`, que crea
tablas nuevas pero nunca agrega columnas a tablas existentes.

Hoy no explota por una razón que no es una defensa: **no hay ninguna base PostgreSQL viva**. La
demo pública corre entera en el navegador desde el 2026-08-16 y no usa backend. El agujero está
al 100% latente y se estrena con el primer cliente: la primera columna que se agregue después
del alta no va a existir en su base, la app va a arrancar como si todo estuviera bien, y va a
fallar recién cuando alguien abra la pantalla que usa ese dato. Esto convierte al frente 1 de
"deuda técnica ordenable" en "defecto latente que se activa con el primer cambio posterior al
alta", y es la razón por la que va primero.

### H4 — No hay copias de seguridad ni simulacro de restauración

No hay nada configurado ni documentado. El plan gratuito de Render **vence la base a los ~90 días**
y el servicio web se duerme a los 15 minutos de inactividad: ninguno de los dos es aceptable
para un cliente que paga.

### H5 — No existe recuperación de contraseña

`backend/routers/auth.py` expone `/login`, `/me`, `/logout`, `/cambiar-password`. El único
reseteo es `reset_password_usuario` en `backend/routers/super_admin.py:319`, disponible solo
para el super admin — ni siquiera el administrador del consorcio puede usarlo. Con 50
departamentos, esto se convierte en soporte manual la primera semana.

### H6 — No hay monitoreo (fuera de alcance, anotado)

Si el servicio se cae de madrugada, nadie se entera hasta que un vecino llama. No bloquea el
piloto, pero debería resolverse antes del segundo cliente.

## Frentes de trabajo

Cada frente produce software funcionando y testeable por sí solo, y merece su propio plan de
implementación detallado. El orden está elegido por **costo diferido**: los frentes 1 y 2 son
mucho más baratos ahora que después de que exista el primer dato real de un cliente.

### Frente 1 — Versionado del esquema (Alembic)

**Por qué primero:** es el único momento de la vida del proyecto en que no hay datos de
producción que proteger. Introducir Alembic contra bases vacías o descartables es trivial;
hacerlo con la contabilidad de un edificio adentro es una operación de riesgo.

**Alcance:**
- Incorporar Alembic con `alembic.ini` y `backend/migrations/`, leyendo `DATABASE_URL` desde `Settings`.
- Generar la revisión base que refleje `backend/models.py` tal como está hoy.
- `alembic stamp` sobre las bases existentes (demo) para marcarlas al día sin re-aplicar.
- Retirar las nueve funciones `_migrar_*` de `backend/main.py` y `create_all()` del lifespan,
  reemplazadas por `alembic upgrade head` en el arranque del deploy.
- Mantener `create_all()` **solo** en el camino de tests (`tests/conftest.py`), que crea y
  destruye esquema por sesión y no necesita historial.
- Documentar el flujo de "agregar una columna" para el futuro.

**Riesgo:** medio. Es el frente donde un error rompe el arranque. Se mitiga porque no hay datos
reales todavía y porque los 1082 tests cubren el esquema resultante.

**Esfuerzo:** 1,5 – 2 días.

### Frente 2 — Archivos fuera del servidor y con control de acceso

**Por qué segundo:** resuelve H1 y H2 juntos, y mover archivos es mucho más barato mientras los
únicos que existen son los de la demo.

**Alcance:**
- Reescribir `backend/storage.py` como una interfaz de almacenamiento con dos implementaciones:
  local (dev y tests, sin dependencias de red) y S3-compatible vía `boto3` (producción).
  Selección por configuración, no por código.
- Unificar `_guardar_archivo` de `backend/routers/presupuestos.py:47` contra esa misma interfaz:
  hoy es una copia del mismo código con otro subdirectorio.
- Quitar el `app.mount("/uploads", StaticFiles(...))` de `backend/main.py:357`.
- Reemplazarlo por un endpoint autenticado que valide rol y pertenencia al consorcio —
  un departamento solo accede a sus propios comprobantes — y devuelva una redirección a una
  URL firmada de corta vida.
- Mantener la forma de `archivo_path` que ya serializa `ComprobanteOut`, para que el frontend
  siga funcionando con un cambio mínimo (las cinco pantallas que lo consumen hoy usan
  `${API_BASE}${archivo_path}`; `ModalDetalleTrabajo.jsx:167` usa un prefijo distinto y hay que
  emparejarlo).
- Script de migración de los archivos existentes al almacén nuevo.
- Tests: aislamiento entre departamentos, expiración de la URL firmada, y que el backend local
  siga cubriendo el camino de tests sin red.

**Esfuerzo:** 2 días.

### Frente 3 — Recuperación de contraseña y correo saliente real

**Alcance:**
- Alta del proveedor transaccional, verificación de dominio (SPF/DKIM) y variables `SMTP_*`.
  `mail_service.py` no cambia: ya habla SMTP y ya fuerza modo consola bajo `DEMO_MODE`.
- Tabla de tokens de reseteo: hash del token (nunca el token en claro), vencimiento, `usado_at`,
  `usuario_id`.
- `POST /auth/recuperar-password`: público, recibe email, **siempre responde 202** exista o no
  la cuenta (no filtrar qué emails están registrados), con límite de frecuencia por email e IP.
- `POST /auth/restablecer-password`: recibe token y contraseña nueva, valida vencimiento y
  un solo uso, invalida el resto de los tokens del usuario y baja `must_change_password`.
- Frontend: pantalla de "olvidé mi contraseña" y pantalla de "elegir contraseña nueva",
  enlazadas desde el login.
- Tests: token vencido, token reusado, email inexistente, límite de frecuencia, y que el token
  no aparezca en claro en la base.

**Esfuerzo:** 2 días de código + ~0,5 día de configuración de dominio (con espera de propagación DNS).

### Frente 4 — Entorno de producción separado de la demo

**Alcance:**
- Servicio web y Postgres en plan pago, **independientes** de los de la demo (la demo se queda
  donde está, gratuita y desechable). Sin esto el servicio se duerme y la base se vence sola.
- `DEMO_MODE=false` y `SECRET_KEY` propia — verificar que el candado anti-producción de
  `backend/config.py` impide arrancar producción con la configuración de demo.
- `CORS_ORIGINS` con el dominio real; proyecto de Vercel de producción con su propio dominio
  y `VITE_API_URL` apuntando al backend nuevo.
- `SEED_ENABLED=false` en producción.
- Alta del cliente vía el circuito de super admin ya existente (`super_admin.py` crea la
  administración y el usuario administrador con `must_change_password=True`).
- Checklist de humo post-deploy: login de cada rol, subir un comprobante, emitir una expensa,
  bajar un PDF, recibir un mail.

**Esfuerzo:** 1 día.

**Costo mensual recurrente estimado (verificar precios vigentes al contratar):** servicio web
en plan de entrada + Postgres en plan de entrada + dominio. Orden de magnitud: decenas de
dólares al mes, no cientos. El almacén de objetos y el envío de correo caen dentro de sus
niveles gratuitos al volumen de un consorcio.

### Frente 5 — Copias de seguridad y simulacro de restauración

**Por qué último:** opera sobre la base de producción, que existe recién después del frente 4.

**Alcance:**
- Activar y verificar las copias automáticas del Postgres pago.
- Volcado lógico propio (`pg_dump`) programado al almacén de objetos del frente 2, con
  retención definida. Motivo: no depender de un solo proveedor para el peor día.
- **Simulacro de restauración documentado y ejecutado al menos una vez** contra una base
  descartable. Una copia que nunca se restauró no es una copia, es una intención.
- Documento de recuperación: cuánto se puede llegar a perder y cuánto tarda volver a estar en
  línea, con los pasos concretos.

**Esfuerzo:** 1 día.

## Esfuerzo total

**7,5 – 8,5 días de trabajo efectivo.** Para una persona sola, entre semana y media y dos
semanas y media de calendario según interrupciones.

Los frentes 1, 2 y 3 son de código y se pueden delegar. Los frentes 4 y 5 son de configuración
y de decisiones de cuenta (contratar, verificar dominios, guardar credenciales): requieren al
dueño del proyecto, aunque los pasos se dejen escritos.

## Explícitamente fuera de alcance

- **Cobro de la suscripción.** No hay integración de pagos. Con uno o dos clientes se factura a
  mano sin problema; se vuelve necesario alrededor del quinto.
- **Alta autoservicio de clientes.** Hoy el super admin da de alta cada administración a mano,
  y para un piloto está bien.
- **Monitoreo y alertas (H6).** Recomendado antes del segundo cliente.
- **Retención de logs y política de datos personales.** Va a hacer falta si el cliente pregunta
  formalmente por tratamiento de datos.

## Criterio de "listo"

El sistema está listo para un cliente que paga cuando, todo junto:

1. Un despliegue nuevo no pierde ningún archivo subido.
2. Un comprobante solo lo puede abrir quien tiene derecho a verlo.
3. Un vecino recupera su contraseña sin que intervenga nadie.
4. Existe una copia de seguridad de ayer **y ya se probó restaurarla**.
5. Agregar una columna al esquema es un comando, no una operación artesanal.
6. El servicio no se duerme ni la base se vence sola.

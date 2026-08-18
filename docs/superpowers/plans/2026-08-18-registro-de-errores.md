# Registro de errores buscable por código — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que un error inesperado deje de ser un texto técnico anónimo y pase a ser algo rastreable: el vecino ve un código corto, y con ese código se llega en segundos a qué pasó, a quién y en qué consorcio.

**Architecture:** Un manejador de excepciones no atrapadas registra cada error en **dos lugares**: la salida del servidor —siempre, sobrevive a cualquier falla— y una tabla de la base —cómoda de consultar, pero sólo si la base está viva—. Al usuario se le devuelve un código de 6 caracteres legible por teléfono. Una pantalla nueva en el panel de super admin busca por ese código. Un servicio externo de alertas (Sentry) queda preparado por variable de entorno, sin acoplarse a nada.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · `logging` · React + Vite · pytest.

**Spec:** `docs/superpowers/specs/2026-08-17-listo-para-cliente-real.md` (hallazgo H6, que la spec dejaba fuera de alcance y se adelanta por pedido del usuario)

## Global Constraints

- **El registro nunca puede tapar el error original.** Si guardar en la base falla, se traga esa falla y se sigue: el usuario tiene que recibir su 500 y la salida del servidor tiene que tener la traza igual.
- **La salida del servidor es la fuente de verdad.** La tabla es la copia cómoda. Todo error va a las dos, en ese orden.
- Alcance de la pantalla: **sólo super admin**. Los errores técnicos no se le muestran al administrador del consorcio.
- Retención: **90 días**, con borrado automático.
- El código tiene que poder dictarse por teléfono: nada de caracteres ambiguos (`0/O`, `1/I/L`).
- Nunca registrar contraseñas ni tokens. Se reutiliza el criterio de `backend/audit.py`, que ya tacha por nombre de campo.
- Los 1158 tests existentes siguen en verde al terminar cada tarea.
- El cambio de esquema va como revisión de Alembic; `pytest tests/test_migraciones.py` tiene que quedar verde.

## Contexto que el implementador necesita saber

**Lo que hay hoy.** `backend/main.py:116` y `:126` manejan `StarletteHTTPException` y `RequestValidationError` — o sea los errores *esperados* (404, 403, validaciones). **No hay manejador para lo inesperado**: una excepción no atrapada sale por el camino por defecto de Starlette, que devuelve 500 y escribe la traza en la salida, sin contexto de quién la provocó.

**El precedente que conviene seguir.** `backend/audit.py` ya resuelve el problema de persistir información sensible: `redactar_payload` reemplaza por `[REDACTED]` todo campo cuyo nombre contenga `password`, `token` o `secret`, y trunca a 500 caracteres. Se reutiliza tal cual.

**Dónde va la pantalla.** El panel de super admin ya tiene tres: `SuperAdminAdministraciones`, `SuperAdminMetricas` y `SuperAdminAuditLog` (`frontend/src/App.jsx:175-177`). La nueva sigue el patrón de `SuperAdminAuditLog`, que es la más parecida — lista paginada de eventos.

**Cuidado con los tests.** `TestClient` de Starlette por defecto **re-lanza** las excepciones del servidor en vez de dejar que el manejador responda. Para probar el manejador hay que construirlo con `raise_server_exceptions=False`.

**Sesión de base propia.** El manejador no puede usar la sesión del request: si el error fue una falla de base, esa sesión está en estado inválido. Abre una `SessionLocal()` nueva y la cierra.

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `backend/models.py` (modificar) | `ErrorRegistrado`: código, cuándo, ruta, tipo, mensaje, traza, quién. |
| `backend/migrations/versions/*.py` (crear) | Revisión de Alembic. |
| `backend/errores.py` (crear) | Generar el código, registrar en los dos lados, purgar los viejos. Aparte del router para testear sin HTTP. |
| `backend/main.py` (modificar) | El manejador de excepciones no atrapadas; purga al arrancar. |
| `backend/config.py` (modificar) | `ERRORES_RETENCION_DIAS`, `SENTRY_DSN`. |
| `backend/routers/super_admin.py` (modificar) | Listar y buscar por código. |
| `backend/schemas.py` (modificar) | `ErrorRegistradoOut`. |
| `frontend/src/screens/SuperAdminErrores.jsx` (crear) | Lista + búsqueda por código. |
| `frontend/src/api/superAdmin.js` (modificar) | Las dos llamadas. |
| `frontend/src/App.jsx` (modificar) | La ruta. |
| `tests/test_errores.py` (crear) | Registro, código, redacción, resistencia a base caída, purga, permisos. |

---

### Task 1: Modelo, código legible y registro

**Files:**
- Modify: `backend/models.py`, `backend/config.py`
- Create: `backend/errores.py`
- Create: `backend/migrations/versions/<hash>_registro_de_errores.py`
- Create: `tests/test_errores.py`

**Interfaces:**
- Produces:
  - `ErrorRegistrado` con `id`, `codigo`, `ocurrido_at`, `ruta`, `metodo`, `tipo`, `mensaje`, `traza`, `usuario_id`, `rol`, `consorcio_id`.
  - `generar_codigo() -> str` — 6 caracteres sin ambigüedades, con prefijo `E-`.
  - `registrar(exc, *, ruta, metodo, usuario_id, rol, consorcio_id) -> str` — devuelve el código; escribe a log siempre y a la base si puede.
  - `purgar_viejos(db, dias) -> int`

- [ ] **Step 1: Escribir los tests (fallan)**

Crear `tests/test_errores.py` cubriendo, como mínimo:

```python
def test_el_codigo_no_usa_caracteres_ambiguos():
    """Se dicta por teléfono: 0/O y 1/I/L se confunden al escucharlos."""
    from backend.errores import generar_codigo

    for _ in range(200):
        codigo = generar_codigo()
        assert codigo.startswith("E-")
        cuerpo = codigo[2:]
        assert len(cuerpo) == 6
        assert not set(cuerpo) & set("O0I1L")


def test_registrar_guarda_el_error_con_su_contexto(db_session):
    from backend.errores import registrar
    from backend.models import ErrorRegistrado

    try:
        raise ValueError("algo se rompió")
    except ValueError as e:
        codigo = registrar(
            e, ruta="/gastos", metodo="POST", usuario_id=1,
            rol="administracion", consorcio_id=1, db=db_session,
        )

    fila = db_session.query(ErrorRegistrado).one()
    assert fila.codigo == codigo
    assert fila.ruta == "/gastos"
    assert fila.tipo == "ValueError"
    assert "algo se rompió" in fila.mensaje
    assert "ValueError" in fila.traza


def test_registrar_escribe_en_el_log_aunque_la_base_falle(caplog, monkeypatch):
    """Si el error ES la base, guardarlo en la base no va a funcionar. La
    salida del servidor tiene que tener la traza igual, o se pierde el único
    rastro justo cuando más se necesita."""
    ...


def test_registrar_no_deja_pasar_una_falla_propia(monkeypatch):
    """Un fallo al registrar no puede convertirse en una segunda excepción que
    tape la original."""
    ...


def test_el_mensaje_no_guarda_contraseñas():
    """Reutiliza el criterio de audit.py: campos con password/token/secret."""
    ...


def test_purgar_borra_solo_lo_mas_viejo_que_la_retencion(db_session):
    ...
```

Completar cada uno con su cuerpo antes de implementar.

- [ ] **Step 2: Correr y verificar que fallan**
- [ ] **Step 3: Agregar `ERRORES_RETENCION_DIAS: int = 90` y `SENTRY_DSN: str = ""` a `Settings`**
- [ ] **Step 4: Agregar el modelo `ErrorRegistrado`** con `codigo` único e indexado y `ocurrido_at` indexado (se ordena y se purga por ahí).
- [ ] **Step 5: Crear `backend/errores.py`**

El alfabeto del código: `"ABCDEFGHJKMNPQRSTUVWXYZ23456789"` — sin `I`, `L`, `O`, `0`, `1`.

`registrar` primero loguea con `logger.exception(...)` incluyendo el código y el contexto, y recién después intenta persistir dentro de un `try/except` que traga cualquier falla y la loguea aparte.

- [ ] **Step 6: Generar la revisión de Alembic y correr la guarda de deriva**
- [ ] **Step 7: Suite completo y commit**

---

### Task 2: El manejador de errores no atrapados

**Files:**
- Modify: `backend/main.py`
- Modify: `tests/test_errores.py`

**Interfaces:**
- Consumes: `registrar` (Tarea 1).
- Produces: respuesta 500 con cuerpo `{"detail": "...", "codigo": "E-XXXXXX"}`.

- [ ] **Step 1: Escribir los tests (fallan)**

Montar una ruta que explote sólo para el test, y un `TestClient(app, raise_server_exceptions=False)`:

```python
def test_un_error_inesperado_devuelve_500_con_codigo(...):
    ...
    assert r.status_code == 500
    assert r.json()["codigo"].startswith("E-")


def test_el_codigo_de_la_respuesta_es_el_que_quedo_guardado(...):
    """Es todo el punto: el vecino dicta el código y tiene que encontrarse."""


def test_la_respuesta_no_filtra_la_traza_al_usuario(...):
    """El detalle técnico va al log y a la tabla, nunca al navegador."""


def test_los_404_y_403_siguen_saliendo_como_antes(client, ...):
    """El manejador nuevo no debe capturar los errores esperados."""
```

- [ ] **Step 2: Correr y verificar que fallan**
- [ ] **Step 3: Agregar el manejador en `backend/main.py`**

Toma usuario/rol/consorcio del request si están disponibles, sin volver a autenticar y sin romper si no hay token.

- [ ] **Step 4: Purga al arrancar**, dentro del lifespan, envuelta en `try/except` — que un fallo de purga no impida arrancar.
- [ ] **Step 5: Suite completo y commit**

---

### Task 3: Consultarlos desde el panel de super admin

**Files:**
- Modify: `backend/schemas.py`, `backend/routers/super_admin.py`, `openapi.yaml`
- Modify: `tests/test_errores.py`

**Interfaces:**
- Produces: `GET /super-admin/errores` (lista paginada, más nuevos primero) y `GET /super-admin/errores/{codigo}`.

- [ ] **Step 1: Escribir los tests (fallan)** — incluir que un admin común recibe 403 y que un código inexistente da 404.
- [ ] **Step 2 a 5:** schema, endpoints, OpenAPI, suite, commit.

---

### Task 4: La pantalla

**Files:**
- Create: `frontend/src/screens/SuperAdminErrores.jsx` y su test
- Modify: `frontend/src/api/superAdmin.js`, `frontend/src/App.jsx`

Seguir el patrón de `SuperAdminAuditLog.jsx`, que es la pantalla más parecida.

Lo que tiene que resolver: pegar un código y ver el error completo; y ver los últimos errores sin buscar nada.

- [ ] Tests, pantalla, ruta, enlace en la navegación de super admin, suite, commit.

---

### Task 5: Ordenar los `print()` y dejar Sentry preparado

**Files:**
- Modify: los módulos de `backend/` que usan `print()` en camino de producción
- Modify: `backend/main.py`, `.env.example`, `README.md`

- [ ] **Step 1:** Inventariar con `grep -rn "print(" backend/ --include=*.py`, separando los **scripts** (`seed_demo`, `export_demo`, `probar_email`, `migrar_archivos`, `seed`) —donde `print` es correcto, son salida de consola para una persona— de los **módulos de servicio**, donde tiene que ser `logger`.
- [ ] **Step 2:** Convertir los de servicio al nivel que corresponda. `mail_service.py` es el caso claro: `[EMAIL ERROR]` es `logger.error`.
- [ ] **Step 3:** Inicializar Sentry en `main.py` **sólo si `SENTRY_DSN` está cargado**, con import perezoso para no agregar dependencia obligatoria.
- [ ] **Step 4:** Documentar en `.env.example` y `README.md`: qué hace la pantalla de errores, cómo se usa el código, la retención de 90 días, y que Sentry es opcional y va por variable de entorno **y no por la interfaz**, porque tiene que arrancar antes de que algo pueda fallar.
- [ ] **Step 5:** Suite completo y commit.

---

## Self-Review

**Lo que este plan NO hace, a propósito:**

- **No avisa.** Deja encontrar rápido, no enterarse solo. Eso lo cubre Sentry, que queda preparado en la Tarea 5 pero cuya alta es del usuario.
- **No registra los errores esperados** (404, 403, validaciones). Son parte del funcionamiento normal; guardarlos ahogaría la tabla y la pantalla.
- **No sirve si la base está caída.** Por eso el log a la salida del servidor es obligatorio y primero. Está fijado por test.

**Riesgo residual:** la purga corre al arrancar. Un servidor que quede meses en pie sin redesplegar no purga, y la tabla crece. Aceptable a esta escala y anotado en el README; si molesta, el paso siguiente es una tarea programada.

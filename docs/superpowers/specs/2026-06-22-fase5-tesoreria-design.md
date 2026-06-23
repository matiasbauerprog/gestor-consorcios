# Fase 5 — Tesorería: cajas, transferencias y estado financiero

Fecha: 2026-06-22
Estado: spec aprobado (brainstorming cerrado con el usuario)

## Contexto y motivación

El sistema hoy modela:
- `MovimientoCuenta`: tracking de cuenta corriente **por departamento** (qué le debe el depto al consorcio).
- `Gasto.forma_pago`: cómo se pagó (efectivo / transferencia / cheque) — informativo, sin link a una caja.

Lo que falta es la perspectiva del consorcio mismo: **dónde tiene la plata**. Hoy un admin no puede contestar "¿cuánto tengo en el banco?" desde el sistema.

Fase 5 introduce el concepto de **caja** (cuenta financiera del consorcio) y lo conecta con el flujo de gastos y pagos existente: cada gasto sale de una caja, cada pago aprobado entra a una caja.

## Decisiones (cerradas en brainstorming)

1. **Alcance**: multi-caja sin conciliación con extractos bancarios.
2. **Definición de cajas**: configurables vía CRUD admin (no hardcoded).
3. **Asignación gasto/pago → caja**: explícita (el usuario elige `caja_id` en el form).
4. **Fondo de reparación**: se nutre por transferencia manual entre cajas (sin % automático).
5. **Red de seguridad para descuadres**: tipo de movimiento extra `ajuste` que el admin carga manualmente con descripción obligatoria al cuadrar con el extracto bancario.
6. **Rediseño visual general**: pospuesto, se mantiene patrón actual.

## Modelos

### `Caja` (nuevo)
```python
class Caja(Base):
    id: int (PK)
    nombre: str (unique, max 100)
    tipo: enum("efectivo" | "banco" | "fondo_reparacion" | "otro")
    descripcion: str | None (max 500)
    saldo_inicial: float (default 0.0)  # snapshot al crear
    activa: bool (default True)          # soft toggle
    created_at: datetime

    movimientos: relationship("MovimientoCaja")
```

### `MovimientoCaja` (nuevo)
```python
class TipoMovimientoCaja(str, enum.Enum):
    ingreso = "ingreso"
    egreso = "egreso"
    ajuste = "ajuste"   # +/- según monto; carga manual con descripcion required

class MovimientoCaja(Base):
    id: int (PK)
    caja_id: int (FK Caja, required)
    fecha: date (required)
    tipo: TipoMovimientoCaja (required)
    monto: float (required, signo según tipo: positivo siempre; "ajuste" usa monto firmado)
    descripcion: str (required)

    # Sólo uno seteado a la vez:
    gasto_id: int | None (FK Gasto)
    comprobante_id: int | None (FK Comprobante)
    transferencia_id: int | None (FK TransferenciaCaja)

    created_at: datetime
```

Nota: para `ajuste` el monto puede ser positivo o negativo (sumando o restando al saldo). Para `ingreso`/`egreso` el monto siempre es positivo y el `tipo` indica la dirección.

### `TransferenciaCaja` (nuevo)
```python
class TransferenciaCaja(Base):
    id: int (PK)
    caja_origen_id: int (FK Caja, required)
    caja_destino_id: int (FK Caja, required)
    monto: float (required, > 0)
    fecha: date (required)
    descripcion: str (required)
    created_at: datetime

    # Al crear se generan 2 MovimientoCaja atómicamente:
    #   - MovimientoCaja(caja=origen, tipo=egreso, monto, transferencia_id=X)
    #   - MovimientoCaja(caja=destino, tipo=ingreso, monto, transferencia_id=X)
```

### Cambios a modelos existentes

- **`Gasto`**: agregar `caja_id: int (FK Caja, required)`.
- **`GastoHabitual`**: agregar `caja_id: int (FK Caja, required)` — heredado por los Gastos materializados al "cargar habituales del mes".
- **`Comprobante`**: agregar `caja_destino_id: int (FK Caja, nullable)` — se completa al pasar a estado `aprobado`.
- **`ConfiguracionConsorcio`**: agregar `caja_default_pagos_id: int (FK Caja, nullable)` — pre-selecciona al aprobar comprobante.

## Lógica integrada

### Saldo de una caja
Función pura, calculado on-demand (no persiste columna):
```
saldo(caja) = caja.saldo_inicial
            + sum(m.monto for m in caja.movimientos if m.tipo == ingreso)
            - sum(m.monto for m in caja.movimientos if m.tipo == egreso)
            + sum(m.monto for m in caja.movimientos if m.tipo == ajuste)   # monto firmado
```

### Crear Gasto (POST /gastos)
1. Validar `caja_id` referencia caja activa.
2. Bloquear si período cerrado (regla Fase 4, ya existe).
3. Crear `Gasto`.
4. Crear `MovimientoCaja(caja_id, tipo=egreso, monto=gasto.monto, fecha=gasto.fecha_pago, descripcion=gasto.concepto, gasto_id=gasto.id)`.
5. Commit atómico.

### Editar Gasto (PATCH /gastos/{id})
- Regla simple: en cada PATCH borrar el `MovimientoCaja` asociado y crear uno nuevo con los valores actualizados (monto, caja, fecha, descripción).
- Si el gasto no tenía MovimientoCaja (edge case migrational), solo crearlo.

### Eliminar Gasto (DELETE /gastos/{id})
- Cascade manual: borrar `MovimientoCaja` con `gasto_id=X` antes del Gasto.

### Crear Plan de Cuotas (POST /gastos/plan-cuotas)
- El payload `PlanCuotasCrear` requiere `caja_id`.
- Las N cuotas generadas comparten la misma `caja_id`.
- Por cada Gasto generado se crea su MovimientoCaja (egreso) en esa caja, con la `fecha_pago` propia de cada cuota.

### Cargar Gastos Habituales (POST /gastos/cargar-habituales)
- Cada Gasto materializado hereda el `caja_id` de su `GastoHabitual` plantilla.
- Por cada Gasto generado se crea su MovimientoCaja correspondiente.

### Crear/Editar Liquidación de Empleado (POST/PATCH /liquidaciones)
- El payload requiere `caja_id` (de qué caja se pagó el sueldo).
- Los N Gastos del rubro `sueldos_y_cargas_sociales` que se generan al liquidar heredan ese `caja_id`.
- Cada uno genera su MovimientoCaja (egreso).
- Al editar/eliminar liquidación, los MovimientoCaja de los gastos asociados se borran/recrean en cascada.

### Aprobar Comprobante (PATCH /comprobantes/{id} con estado=aprobado)
1. Validar `caja_destino_id` referencia caja activa (si nulo, usar `ConfiguracionConsorcio.caja_default_pagos_id`; si tampoco, 400).
2. Bloquear si período cerrado.
3. Cambiar estado del Comprobante.
4. Generar `MovimientoCuenta(depto, tipo=pago_recibido, ...)` como ya hacía.
5. Generar `MovimientoCaja(caja_destino_id, tipo=ingreso, monto, fecha=fecha_pago, descripcion=..., comprobante_id=X)`.
6. Commit atómico.

### Crear Transferencia (POST /transferencias-caja)
1. Validar `caja_origen_id != caja_destino_id`, `monto > 0`, ambas cajas activas.
2. Bloquear si `fecha` cae en período cerrado.
3. Crear `TransferenciaCaja`, flush para id.
4. Crear 2 `MovimientoCaja` (egreso en origen, ingreso en destino) con `transferencia_id=X`.
5. Commit atómico.

### Cargar Ajuste (POST /cajas/{caja_id}/movimientos con tipo=ajuste)
1. Validar caja activa.
2. Validar período no cerrado.
3. `descripcion` obligatoria (mínimo 5 chars).
4. Crear `MovimientoCaja(caja_id, tipo=ajuste, monto=firmado, fecha, descripcion)`.

## Endpoints

### Cajas
```
GET    /cajas                          → [Caja con saldo] (admin)
POST   /cajas                          → crear (admin)
PATCH  /cajas/{caja_id}                → editar nombre/descripcion/activa (admin)
DELETE /cajas/{caja_id}                → baja física solo sin movimientos (admin); sino 409
```

### Movimientos
```
GET    /cajas/{caja_id}/movimientos    → paginado (admin)
POST   /cajas/{caja_id}/movimientos    → cargar ajuste manual (admin)
```
Movimientos de `ingreso`/`egreso` solo se crean indirectamente (vía Gasto/Comprobante/Transferencia). Endpoint solo acepta `tipo=ajuste`.

### Transferencias
```
GET    /transferencias-caja            → listado paginado (admin)
POST   /transferencias-caja            → crear (admin)
```

### Dashboard
```
GET    /estado-financiero              → { cajas: [...], total: float, ultimos_movimientos: [...] }
```

### Modificaciones a endpoints existentes
- `POST /gastos`: schema `GastoCrear` requiere `caja_id`.
- `PATCH /gastos/{id}`: schema `GastoActualizar` acepta `caja_id`.
- `POST /gastos/plan-cuotas`: schema `PlanCuotasCrear` requiere `caja_id`.
- `POST /gastos/cargar-habituales`: sin cambio en el body, pero cada gasto generado hereda `caja_id` del `GastoHabitual` plantilla.
- `POST /gastos-habituales` y `PATCH /gastos-habituales/{id}`: schemas requieren `caja_id`.
- `POST /liquidaciones` y `PATCH /liquidaciones/{id}`: schemas requieren `caja_id` (aplicado a los N gastos generados).
- `PATCH /comprobantes/{id}`: si `estado=aprobado`, body acepta opcionalmente `caja_destino_id` (sino usa default).
- `GET /configuracion`: incluye `caja_default_pagos_id`.
- `PUT /configuracion`: acepta `caja_default_pagos_id`.

Todos los endpoints nuevos son **admin-only**. Depto y representante: 403.

## UI

### Sidebar — sección nueva "Tesorería"
Va entre "Expensas y pagos" y "Sueldos":
```
📊 Estado financiero
💰 Cajas
🔄 Transferencias
```
Admin-only. Si el rol no es admin, la sección entera no se renderiza.

### Pantalla `/estado-financiero` (nueva)
- Grid de tarjetas: una por caja activa con nombre, badge de tipo, saldo, último movimiento (fecha + monto).
- Tarjeta "Total general" con la suma.
- Botón "Transferir entre cajas" → abre `ModalNuevaTransferencia`.
- Lista paginada de últimos 20 movimientos (cualquier caja): fecha, caja, tipo (badge), monto firmado, descripción.

### Pantalla `/cajas` (nueva)
- Tabla: nombre, tipo (badge), descripción, saldo actual, activa, acciones.
- Botón "Nueva caja" → modal.
- Click en una fila → modal "Detalle de caja":
  - Datos editables (nombre, descripción, activa) con Guardar.
  - Tab "Movimientos" con historial paginado.
  - Botón "Cargar ajuste manual" → modal con monto (signo) + descripción.

### Pantalla `/transferencias` (nueva)
- Tabla simple: fecha, origen, destino, monto, descripción.
- Botón "Nueva transferencia" → `ModalNuevaTransferencia` (mismo componente que en estado-financiero).

### Ajuste a `/gastos`
- Form (`FormularioGasto`): dropdown nuevo "Caja origen" (required) entre "Forma de pago" y "Fecha de pago".
- Lista: columna nueva "Caja" mostrando `caja.nombre`.

### Ajuste a `/comprobantes`
- Al aprobar un comprobante (botón "Aprobar"): se abre un mini-modal con dropdown "Caja destino" (pre-seleccionada con la default de configuración) y un confirm. El depto que presenta el comprobante NO ve este paso.

### Ajuste a `/configuracion`
- Fieldset "Vencimientos e intereses" gana un campo extra: dropdown "Caja default para pagos recibidos".

### API clients (nuevos)
- `frontend/src/api/cajas.js` → `listarCajas, crearCaja, actualizarCaja, eliminarCaja`
- `frontend/src/api/movimientosCaja.js` → `listarMovimientos, crearAjuste`
- `frontend/src/api/transferencias.js` → `listarTransferencias, crearTransferencia`
- `frontend/src/api/estadoFinanciero.js` → `obtenerEstadoFinanciero`

## Tests

### Backend (siguiendo patrón Fases 3.5/4)
- `tests/test_cajas.py` (~15 tests):
  - GET listado con saldo correcto (suma sembrada + ingresos - egresos + ajustes firmados).
  - POST crear (admin 201, depto 403, sin token 401, duplicado nombre 400).
  - PATCH editar (200, no toca movimientos).
  - DELETE: 204 si sin movimientos, 409 si tiene.
- `tests/test_transferencias.py` (~8 tests):
  - POST genera 2 movimientos atómicamente.
  - Validaciones: origen=destino 400, monto<=0 400, caja inactiva 400, período cerrado 409.
  - GET paginado.
- `tests/test_movimientos_caja.py` (~8 tests):
  - POST ajuste con monto positivo (saldo sube), negativo (saldo baja).
  - Descripcion obligatoria (mín 5 chars), 400.
  - No se puede POST con tipo=ingreso/egreso desde este endpoint (400).
  - Período cerrado 409.
- `tests/test_estado_financiero.py` (~4 tests):
  - GET devuelve cajas + saldos + total + últimos N movimientos.
  - Admin-only (depto 403).
- Ampliación de `tests/test_gastos.py`:
  - POST sin `caja_id` → 400.
  - POST con `caja_id` válido → 201 + verificar MovimientoCaja generado.
  - PATCH cambia caja → MovimientoCaja viejo borrado, nuevo creado.
  - DELETE → MovimientoCaja en cascada.
- Ampliación de `tests/test_comprobantes.py`:
  - Aprobar comprobante sin `caja_destino_id` y sin default → 400.
  - Aprobar con default configurado → usa la default.
  - Aprobar con `caja_destino_id` explícito → genera MovimientoCaja.

### Módulo puro
- `backend/caja_saldo.py` con función `calcular_saldo(caja, movimientos)` pura, testeable sin DB.
- `tests/test_caja_saldo.py` unitario para esa función.

### Sin tests E2E del frontend
- Mismo criterio que fases anteriores: smoke manual al cierre.

## Migración

Clean start (patrón de Fases 1-4): borrar `consorcio.db`, re-seed.

### Seed
1. Crear 3 cajas default:
   - "Banco Provincia" (tipo banco, saldo_inicial=0)
   - "Caja chica" (tipo efectivo, saldo_inicial=0)
   - "Fondo de reparación" (tipo fondo_reparacion, saldo_inicial=0)
2. `ConfiguracionConsorcio.caja_default_pagos_id` = id de "Banco Provincia".
3. Los `GastoHabitual` demo se crean con `caja_id` = "Banco Provincia" (sueldo encargado, ascensor, etc.).
4. Los gastos demo (existentes en seed Fase 3) se crean con `caja_id` = "Banco Provincia" y generan su MovimientoCaja.
5. Los comprobantes ya aprobados del seed se actualizan para tener `caja_destino_id` = "Banco Provincia" y generar el MovimientoCaja correspondiente.

## Bloqueos cross-recurso (suma a los de Fase 4)
- `POST /cajas/{id}/movimientos` (ajuste): 409 si período cerrado.
- `POST /transferencias-caja`: 409 si la fecha cae en período cerrado.
- Crear/editar/borrar Gasto y aprobar Comprobante: ya respetan el bloqueo de Fase 4, no cambia.

## Out-of-scope explícito (queda para fases futuras)
- ❌ Conciliación con extractos bancarios (importar CSV/Excel para auto-match).
- ❌ Saldos por moneda (todo en pesos argentinos).
- ❌ Cuentas con descubierto bloqueante: se permite saldo negativo sin warning.
- ❌ Histórico de saldo (gráficos evolución mes a mes) — Fase 6.
- ❌ P&L mensual / estado de resultados — Fase 6.
- ❌ Permisos finos por caja (admin tiene acceso total a todas).
- ❌ Multi-moneda, conversión, ajuste por inflación.
- ❌ Rediseño visual general del frontend (queda pospuesto).

## Estimación

- ~10-12 tasks (modelos → schemas → módulo puro `caja_saldo.py` → routers cajas/transferencias/estado-financiero → integración en gastos.py y comprobantes.py → tests integration → seed → openapi → 3 frontend clients + 3 pantallas nuevas + 4 pantallas modificadas → smoke + merge).
- Tiempo total: 1-2 semanas estimadas (el patrón TDD + subagent-driven ya está conocido).

## Historial

- 2026-06-22: brainstorming + spec inicial post-merge Fase 4.5. Acordado scope multi-caja sin conciliación, cajas configurables, asignación explícita, fondo manual con ajuste como red de seguridad.

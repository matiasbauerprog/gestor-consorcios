# Expensas — Fase 2: gastos del consorcio — diseño

Fecha: 2026-06-16
Estado: aprobado por el usuario, pendiente de plan de implementación.
Roadmap: [2026-06-16-expensas-completas-roadmap.md](2026-06-16-expensas-completas-roadmap.md)
Fase previa: [2026-06-16-expensas-fase1-modelo-central-design.md](2026-06-16-expensas-fase1-modelo-central-design.md)

## Objetivo

Permitir a Administración cargar los gastos del consorcio (lo que el consorcio paga durante el mes a proveedores: sueldos, servicios públicos, mantenimiento, etc.). Estos gastos serán insumo de la Fase 4 (cierre de período) para generar las expensas de cada departamento con su desglose.

Incluye dos modelos: **gastos puntuales** (carga manual por mes) y **gastos habituales** (plantillas que se replican automáticamente cuando admin pide cargar las recurrentes del mes).

No introduce el concepto de "período cerrado": en esta fase los gastos se pueden crear/editar/borrar siempre. Fase 4 introduce el bloqueo post-cierre.

## Reglas del proyecto aplicables

- `business-rules.md`: Administración es quien crea/edita/borra gastos y plantillas habituales; ningún otro rol tiene acceso.
- `backend.md`: routers en `backend/routers/`, modelos en `backend/models.py`, schemas en `backend/schemas.py`, tests por router con 401/403/404/400.
- `openapi-first.md`: todos los endpoints nuevos se documentan primero en `openapi.yaml`.
- `frontend.md`: HTML semántico, mobile-first, targets táctiles ≥44px, paleta vía variables CSS.
- `security.md`: identidad y rol vienen del JWT; los endpoints validan con `require_roles`.

## Decisiones de diseño

| Decisión | Elegida | Alternativas descartadas | Razón |
|---|---|---|---|
| Campos del gasto | Intermedio: rubro, clase/depto, proveedor, concepto, monto, periodo, fecha_pago, numero_factura, fecha_factura, forma_pago, cuota_actual, cuota_total | Minimal (solo lo indispensable); Completo (incluye n° de pago y banco) | Cubre auditoría básica (Ley 941) y planes en cuotas sin meterse en módulo de caja/banco (Fase 5). |
| Gasto particular a un depto | Campo opcional `departamento_id` en `Gasto`, excluyente con `clase_prorrateo_id` | Tabla separada `GastoParticular`; sin gastos particulares en esta fase | El 99% de casos en los PDFs es 1 gasto → 1 depto. Una tabla aparte sería overkill. |
| Cuotas (X/Y) | B-simple: el sistema replica N gastos a períodos consecutivos al crear (vía endpoint `/gastos/plan-cuotas`) | Solo dos campos opcionales sin replicación automática (A); entidad `PlanDeCuotas` con sincronización (B-completo); texto libre (C) | Evita que admin tenga que recordar cargar cada cuota manualmente. Cada cuota generada es un Gasto editable individualmente. Una entidad PlanDeCuotas sería más limpia pero ~2-3 días extra. |
| Forma de pago | Enum cerrado (`transferencia`, `debito_automatico`, `cheque`, `efectivo`, `otro`) | Texto libre | Datos limpios, queryables, sin typos. El valor `otro` cubre casos raros. |
| Período | String `"YYYY-MM"` (mismo patrón que `Expensa.periodo`) | Entidad `Periodo` separada con estado abierto/cerrado; fecha completa | Consistencia con lo existente. El estado "abierto/cerrado" lo introduce Fase 4 sin necesidad de tabla nueva. |
| Gasto recurrente | Entidad `GastoHabitual` separada (plantilla) + endpoint `/gastos/cargar-habituales` que genera los gastos del mes a partir de plantillas activas, idempotente | Checkbox "habitual" en `Gasto` que se autoreplica al próximo mes (A); botón "duplicar mes anterior" sin entidad (C) | La plantilla es fuente de verdad; los gastos generados son normales y editables sin afectar la plantilla. Admin puede ajustar el sueldo de un mes específico sin tocar la recurrencia. |
| Alcance frontend | Pantalla `/gastos` con tabs internos `Únicos` y `Habituales` (rutas `/gastos` y `/gastos/habituales`), mobile-first | Items separados en sidebar; sub-headers anidados; solo backend + seed | Mantiene el sidebar limpio. Tabs son convención y permiten alternar rápido entre lo puntual y las plantillas. |
| Permisos | Admin-only en todo | Representante con read | Ningún otro rol tiene caso de uso real para gastos en esta fase. |

## Modelo de datos

### `FormaPago` (enum en `backend/models.py`)

```python
class FormaPago(str, enum.Enum):
    transferencia = "transferencia"
    debito_automatico = "debito_automatico"
    cheque = "cheque"
    efectivo = "efectivo"
    otro = "otro"
```

### `Gasto`

```python
class Gasto(Base):
    __tablename__ = "gastos"

    id: Mapped[int] = mapped_column(primary_key=True)
    periodo: Mapped[str] = mapped_column(String(7), index=True, nullable=False)  # "YYYY-MM"
    rubro: Mapped[Rubro] = mapped_column(SqlEnum(Rubro, name="rubro"), nullable=False)

    # Excluyentes: o clase (se prorratea) o depto (particular). Nunca ambos. Nunca ninguno.
    clase_prorrateo_id: Mapped[int | None] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="RESTRICT"), nullable=True
    )
    departamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=True
    )

    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    concepto: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)  # > 0 (validado en schema)

    forma_pago: Mapped[FormaPago] = mapped_column(SqlEnum(FormaPago, name="forma_pago"), nullable=False)
    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)

    numero_factura: Mapped[str | None] = mapped_column(String(50))
    fecha_factura: Mapped[date | None] = mapped_column(Date)

    cuota_actual: Mapped[int | None] = mapped_column(Integer)  # null = no es en cuotas
    cuota_total: Mapped[int | None] = mapped_column(Integer)

    # Apunta a la plantilla origen si fue generado por "Cargar habituales del mes"
    gasto_habitual_id: Mapped[int | None] = mapped_column(
        ForeignKey("gastos_habituales.id", ondelete="SET NULL")
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

**Validaciones (en Pydantic, no en DB):**
- Exactamente uno de `clase_prorrateo_id` / `departamento_id` debe estar seteado.
- Si `cuota_actual` está, también `cuota_total`. Si `cuota_total` está, también `cuota_actual`. Y `1 ≤ cuota_actual ≤ cuota_total`.
- `monto > 0`.
- `periodo` con regex `^\d{4}-(0[1-9]|1[0-2])$`.

### `GastoHabitual` (plantilla recurrente)

```python
class GastoHabitual(Base):
    __tablename__ = "gastos_habituales"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    rubro: Mapped[Rubro] = mapped_column(SqlEnum(Rubro, name="rubro"), nullable=False)
    clase_prorrateo_id: Mapped[int] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="RESTRICT"), nullable=False
    )
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False
    )
    concepto: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    forma_pago: Mapped[FormaPago] = mapped_column(SqlEnum(FormaPago, name="forma_pago"), nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

**Decisiones sobre `GastoHabitual`:**
- **Sin período**: la plantilla es perpetua mientras `activa=true`. El período se asigna al generar el gasto.
- **Sin cuotas**: una plantilla recurrente no tiene cuotas. Los planes a cuotas se cargan como `Gasto` con `/gastos/plan-cuotas`.
- **Sin gasto particular**: la plantilla siempre va a prorrateo (`clase_prorrateo_id` obligatorio). Reparaciones en unidades son siempre puntuales.
- **Editar plantilla NO toca gastos ya generados**: cada gasto es independiente una vez creado. Esto permite ajustar la plantilla (ej. paritarias) y que los meses pasados conserven el monto original.

### Idempotencia al cargar habituales

El endpoint `/gastos/cargar-habituales` recibe `{ periodo: "YYYY-MM" }`. Por cada `GastoHabitual` con `activa=true`, chequea si ya existe un `Gasto` con `(periodo=X, gasto_habitual_id=plantilla.id)`. Si no existe, lo crea. Si existe, lo omite. Devuelve la lista de gastos generados en esa llamada (puede ser vacía si todos ya estaban).

## Endpoints

Todos requieren JWT y son **admin-only**. Errores de validación Pydantic → HTTP 400.

### Gastos — `backend/routers/gastos.py`

| Método | Path | Notas |
|---|---|---|
| GET | `/gastos` | Filtros opcionales `?periodo=YYYY-MM&rubro=X&clase_prorrateo_id=N&departamento_id=N&proveedor_id=N&gasto_habitual_id=N&limit=50&offset=0`. |
| POST | `/gastos` | Crea **un** gasto. Si trae `cuota_actual`/`cuota_total`, se aceptan tal cual (sin replicación). |
| POST | `/gastos/plan-cuotas` | Crea **N** gastos a partir de un plan. Body: campos del gasto + `cuota_total: N` (donde `N ≥ 2`, validado). Server genera N filas en períodos consecutivos (`periodo`, `periodo+1mes`, ..., `periodo+N-1mes`), cada una con `cuota_actual=i+1`, `cuota_total=N`, `fecha_pago` desplazada 1 mes por cuota (ej. si primera es `2026-06-15`, segunda es `2026-07-15`). Devuelve lista. |
| GET | `/gastos/{gasto_id}` | Detalle. |
| PATCH | `/gastos/{gasto_id}` | Editar cualquier campo excepto `gasto_habitual_id`. Mismas validaciones de excluyencia clase/depto. |
| DELETE | `/gastos/{gasto_id}` | Hard delete. |
| POST | `/gastos/cargar-habituales` | Body `{ periodo: "YYYY-MM" }`. Genera gastos a partir de plantillas activas, idempotente. Devuelve lista de gastos creados (puede ser vacía). |

### Gastos habituales — `backend/routers/gastos_habituales.py`

| Método | Path | Notas |
|---|---|---|
| GET | `/gastos-habituales` | Listar. Filtro opcional `?activa={bool}`. |
| POST | `/gastos-habituales` | Crear. |
| GET | `/gastos-habituales/{gasto_habitual_id}` | Detalle. |
| PATCH | `/gastos-habituales/{gasto_habitual_id}` | Editar (incluye toggle `activa`). |
| DELETE | `/gastos-habituales/{gasto_habitual_id}` | Soft-delete si tiene gastos asociados (set `activa=false`); hard-delete si no. Mismo patrón que `clases_prorrateo`. |

### Códigos de error

| Código | Cuándo |
|---|---|
| 400 | Pydantic falla. Casos clave: clase y depto al mismo tiempo, ni clase ni depto, monto≤0, cuotas inconsistentes, período mal formado. |
| 401 | Sin token o inválido. |
| 403 | Rol no admin. |
| 404 | Gasto/plantilla/clase/proveedor/depto no existe. |

## Frontend

### Sidebar (Admin)

Sumar `Gastos` a la sección `Expensas y pagos`:

```
Expensas y pagos
  · Expensas
  · Comprobantes
  · Gastos
```

`Gastos` lleva a `/gastos`. Tabs internos manejan la sub-navegación.

### Rutas

- `/gastos` → tab "Únicos" (default)
- `/gastos/habituales` → tab "Habituales"

### Componente de tabs (mobile-first)

Dos `<NavLink>` lado a lado, cada uno 50% del ancho. Alto mínimo 44px. Indicador del activo con borde inferior coloreado. Mismo aspecto en desktop, alineados a la izquierda dentro del content.

### `/gastos` — Tab "Únicos"

**Layout:**
- Cabecera con título y tabs.
- **Filtros** apilados en mobile, en línea en desktop: período (input `text` regex), rubro (select), clase (select), proveedor (select), departamento (SelectorDepartamento existente).
- **Acciones del período**:
  - Botón "Cargar gastos habituales del mes" (deshabilitado si no hay período seleccionado en el filtro).
  - Botón "+ Nuevo gasto".
- **Lista de tarjetas** (`<ul className="lista-gastos">`):
  - Cada `<Tarjeta>`: título `<rubro> · <concepto>` + monto, meta con proveedor, fecha de pago, período. Si `cuota_actual` mostrar `Cuota X/Y`. Si `gasto_habitual_id` mostrar pill `Habitual`. Si `departamento_id` mostrar pill con código del depto. Si `clase_prorrateo_id` mostrar pill con código de la clase.
  - Botones Editar / Eliminar.

**Modal "Nuevo gasto":**
- Rubro (select del enum).
- **Tipo de prorrateo** (radio excluyente):
  - "Se prorratea (clase)" → muestra select de ClaseProrrateo activa.
  - "Particular a un departamento" → muestra `SelectorDepartamento`.
- Proveedor (select de proveedores activos).
- Concepto (textarea).
- Monto (number, min=0.01, step=0.01).
- Período (input regex `YYYY-MM`).
- Forma de pago (select del enum).
- Fecha de pago (date).
- N° de factura, fecha de factura (opcionales).
- **Checkbox "Es en cuotas"** → si marcado, muestra input "Total de cuotas" (min=2). Texto: "Se generarán N gastos en períodos consecutivos a partir de este".
- Submit: si "en cuotas" → `POST /gastos/plan-cuotas`; si no → `POST /gastos`.

**Modal "Editar gasto":** mismos campos sin el checkbox de cuotas (cada cuota se edita individualmente).

### `/gastos/habituales` — Tab "Habituales"

**Layout:**
- Cabecera con tabs.
- Toggle "Mostrar inactivas" (off por default).
- Botón "+ Nueva plantilla".
- Lista de tarjetas (`<ul className="lista-gastos-habituales">`):
  - Cada `<Tarjeta>`: nombre + monto, meta con rubro · clase · proveedor, badge Activa/Inactiva.
  - Botones Editar / Activar-Desactivar.

**Modal "Nueva plantilla":** nombre, rubro, clase (solo activas), proveedor, concepto, monto, forma de pago. Sin período, sin cuotas, sin depto particular.

### API clients

- `frontend/src/api/gastos.js`: `listarGastos`, `crearGasto`, `crearPlanCuotas`, `obtenerGasto`, `actualizarGasto`, `eliminarGasto`, `cargarGastosHabituales`.
- `frontend/src/api/gastosHabituales.js`: CRUD estándar (mismo patrón que `proveedores.js`).

## Tests

Un archivo por router. Cubren happy path + 401/403/404 + 400 de validación.

| Archivo | Cobertura específica |
|---|---|
| `tests/test_gastos.py` | CRUD básico; filtros (periodo, rubro, clase, depto, proveedor, gasto_habitual_id); 400 si clase y depto juntos; 400 si ni clase ni depto; 400 si monto≤0; 400 si cuotas inconsistentes; `/gastos/plan-cuotas` genera N en períodos consecutivos con fecha_pago desplazada; `/gastos/cargar-habituales` genera correctamente, omite duplicados (idempotente), funciona con período sin plantillas (devuelve vacío). |
| `tests/test_gastos_habituales.py` | CRUD; soft-delete cuando tiene gastos generados; hard-delete cuando no; filtro `?activa`; 403 para roles no-admin. |

## Seed inicial

Extender `backend/seed.py`:
1. Crear 3 plantillas `GastoHabitual` activas: "Sueldo encargado" (Rubro `sueldos_y_cargas_sociales`), "Servicio de limpieza" (`abonos_y_servicios`), "Mantenimiento ascensores" (`abonos_y_servicios`). Todas apuntan a la clase A (sembrada en Fase 1) y a alguno de los proveedores seeded.
2. Crear 4 `Gasto` puntuales para el período actual (`2026-06`):
   - Un gasto generado vía plantilla habitual (con `gasto_habitual_id` apuntando a una de las tres anteriores).
   - Un gasto prorrateable puntual (ej. reparación de cañería común, Rubro `mantenimiento_partes_comunes`).
   - Un gasto particular asignado al depto A (ej. arreglo plomería).
   - Un gasto en cuotas, cuota 1/3 (carga manual, las 2 restantes admin las generaría con `/gastos/plan-cuotas` al testear).
3. No tocar los datos sembrados existentes de Fase 1.

**Conftest de tests** (`tests/conftest.py`): sumar 1 `GastoHabitual` (id=700) y 1 `Gasto` (id=800) básico al `_seed()` para fixtures mínimas.

## Fuera de scope (Fase 2)

- **Período abierto/cerrado**: los gastos se pueden crear/editar/borrar siempre. Fase 4 introduce el bloqueo post-cierre.
- **Validación de coherencia entre rubro y clase**: cualquier combinación es válida.
- **Adjuntar archivo del comprobante de pago** al gasto.
- **Historial de cambios / audit log** de gastos editados o borrados.
- **Reportes y exports** (CSV, PDF). Fase 6.
- **Cancelar plantilla con efecto retroactivo** (borrar todos los gastos futuros).
- **Numeración automática de pago** (`numero_pago`, `banco`, `caja`). Fase 5 (caja/banco).
- **Concepto de "gasto programado a futuro"** (cargar hoy un gasto que se paga en julio).

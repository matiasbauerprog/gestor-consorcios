# Fase 6b — Reportes (morosos, estado financiero, gastos del período, proveedores)

Fecha: 2026-06-25
Estado: spec aprobado (brainstorming cerrado con el usuario)

## Contexto y motivación

El roadmap original definía la Fase 6 como "Reportes Ley 941 + PDF de liquidación". Ya cerramos el PDF de liquidación en Fase 6a. Esta Fase 6b cubre los reportes — formato "PBA-friendly" (tablas claras + PDF lindo, sin formato oficial Ley 941 CABA).

El producto ya tiene casi todo el dato necesario (cuenta corriente, cajas, gastos, proveedores) — falta exponerlo en consultas agregadas que el admin usa día a día y los copropietarios tienen derecho a ver.

**Mercado objetivo:** Provincia de Buenos Aires (sin obligación legal de formato Ley 941 CABA, pero los admins y copropietarios igual piden los reportes core). Modo oficial Ley 941 queda para una Fase 6c posterior si entra un cliente de CABA que lo requiera.

## Decisiones (cerradas en brainstorming)

1. **Scope**: los 4 reportes juntos en una fase (morosos + estado financiero + gastos del período + lista de proveedores).
2. **Formato output**: pantalla con tabla y filtros + botón "Descargar PDF" (reusa ReportLab de Fase 6a). Sin Excel/CSV en este alcance.
3. **Acceso**: los 4 reportes son visibles a admin + representante + depto (transparencia total). Solo lectura.
4. **Modo Ley 941 oficial CABA**: NO incluido en esta fase. Queda para Fase 6c cuando aparezca cliente real de CABA.
5. **Sin cambios al modelo**: los reportes son consultas agregadas sobre datos existentes.

## Arquitectura

### Backend nuevo

**Módulo puro `backend/reportes.py`** — funciones puras que devuelven dataclasses:

```python
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class ItemMoroso:
    departamento_id: int
    departamento_codigo: str
    saldo: float                    # > 0 = debe; < 0 = a favor
    periodos_vencidos_impagos: int
    primer_vencimiento_impago: date | None

@dataclass(frozen=True)
class ItemActivoCaja:
    caja_id: int
    nombre: str
    saldo: float

@dataclass(frozen=True)
class ItemPasivoGasto:
    gasto_id: int
    proveedor: str
    concepto: str
    monto: float
    fecha_registrada: date

@dataclass(frozen=True)
class EstadoFinancieroReporte:
    fecha_corte: date
    cajas: list[ItemActivoCaja]
    deudores_total: float            # suma de saldos > 0 de deptos
    pasivos: list[ItemPasivoGasto]
    activo_total: float
    pasivo_total: float
    patrimonio_neto: float

@dataclass(frozen=True)
class ItemGastoDetalle:
    fecha: date
    concepto: str
    rubro: str                       # enum value
    proveedor: str
    forma_pago: str
    caja: str
    monto: float
    es_particular: bool              # True si el gasto va a un depto específico (clase=null)

@dataclass(frozen=True)
class GastosDelPeriodoReporte:
    periodo: str                     # "YYYY-MM"
    por_rubro: dict[str, list[ItemGastoDetalle]]
    particulares: list[ItemGastoDetalle]
    subtotales_por_rubro: dict[str, float]
    total_general: float

@dataclass(frozen=True)
class ItemProveedor:
    proveedor_id: int
    razon_social: str
    cuit: str
    cantidad_gastos: int
    total_facturado: float
    ultimo_gasto: date | None

def calcular_morosos(db, solo_deudores: bool = True) -> list[ItemMoroso]: ...
def calcular_estado_financiero(db, fecha_corte: date) -> EstadoFinancieroReporte: ...
def calcular_gastos_del_periodo(db, periodo: str, rubro: str | None = None,
                                 proveedor_id: int | None = None) -> GastosDelPeriodoReporte: ...
def calcular_lista_proveedores(db, anio: int, periodo: str | None = None) -> list[ItemProveedor]: ...
```

**Schemas Pydantic** en `backend/schemas.py` correspondientes a las dataclasses (con `model_config = ConfigDict(from_attributes=True)` para serialización).

**Router nuevo `backend/routers/reportes.py`** con 8 endpoints (4 JSON + 4 PDF):

```
GET  /reportes/morosos                           → JSON list[ItemMorosoOut]
GET  /reportes/morosos/pdf                       → application/pdf
GET  /reportes/estado-financiero                 → JSON EstadoFinancieroReporteOut
GET  /reportes/estado-financiero/pdf             → application/pdf
GET  /reportes/gastos/{periodo}                  → JSON GastosDelPeriodoReporteOut
GET  /reportes/gastos/{periodo}/pdf              → application/pdf
GET  /reportes/proveedores                       → JSON list[ItemProveedorOut]
GET  /reportes/proveedores/pdf                   → application/pdf
```

**Filtros como query params:**
- `/reportes/morosos?solo_deudores=false&orden=meses_atraso`
- `/reportes/estado-financiero?fecha_corte=2026-06-30`
- `/reportes/gastos/2026-06?rubro=servicios_publicos&proveedor_id=3`
- `/reportes/proveedores?anio=2026&periodo=2026-06`

**Auth**: los 3 roles (`admin`, `representante`, `departamento`) pueden GET cualquier reporte. 401 sin token. Sin restricción adicional por ownership — los reportes son del consorcio entero.

### Extensión de `backend/pdf.py`

Sumar 4 funciones nuevas:

```python
def generar_pdf_morosos(items: list[ItemMoroso], fecha: date, config) -> bytes: ...
def generar_pdf_estado_financiero(reporte: EstadoFinancieroReporte, config) -> bytes: ...
def generar_pdf_gastos_periodo(reporte: GastosDelPeriodoReporte, config) -> bytes: ...
def generar_pdf_lista_proveedores(items: list[ItemProveedor], anio: int, config) -> bytes: ...
```

**Refactor menor:** extraer `_dibujar_header_consorcio(story, config, titulo, subtitulo=None)` para reuso entre los 4 reportes nuevos + el de boleta de Fase 6a (DRY).

### Frontend

**Sidebar — nueva sección "Reportes"** entre "Tesorería" y "Sueldos":
```
📊 Lista de morosos       (admin / representante / departamento)
💼 Estado financiero      (admin / representante / departamento)
📋 Detalle de gastos      (admin / representante / departamento)
🏢 Lista de proveedores   (admin / representante / departamento)
```

**4 pantallas nuevas** en `frontend/src/screens/`:
- `ReporteMorosos.jsx`
- `ReporteEstadoFinanciero.jsx`
- `ReporteGastosPeriodo.jsx`
- `ReporteProveedores.jsx`

**Patrón común:**
- Header con título + filtros (input/select) + botón "📄 Descargar PDF"
- Tabla principal (reusa estilos `tarjeta`)
- Fila/sección de totales abajo
- Mensaje "sin datos" si la consulta está vacía

**API client `frontend/src/api/reportes.js`:**
```javascript
import { apiFetch, API_BASE } from "./client";

export function listarMorosos(filtros) { /* query params */ }
export function obtenerEstadoFinanciero(fechaCorte) { ... }
export function obtenerGastosDelPeriodo(periodo, filtros) { ... }
export function listarProveedores(anio, periodo) { ... }

// PDFs: reusa patrón blob URL de api/pdf.js
export async function abrirPdfMorosos(filtros, token) { ... }
export async function abrirPdfEstadoFinanciero(fechaCorte, token) { ... }
export async function abrirPdfGastosPeriodo(periodo, filtros, token) { ... }
export async function abrirPdfProveedores(anio, token) { ... }
```

## Detalles de cálculo por reporte

### 1) Lista de morosos

- **Iterar** todos los `Departamento`.
- Para cada uno, calcular saldo con la función ya existente en `backend/cuenta_corriente.py` (o equivalente).
- Si `saldo > 0` → moroso (le debe al consorcio).
- Contar cuántas `Expensa` del depto tienen `fecha_segundo_vencimiento < hoy` Y saldo aún pendiente → `periodos_vencidos_impagos`.
- Tomar la `fecha_primer_vencimiento` más vieja de las expensas impagas → `primer_vencimiento_impago`.
- Filtro `solo_deudores=true` (default): excluye deptos con `saldo <= 0`.
- Filtro `solo_deudores=false`: incluye todos.
- Orden default: por `saldo` descendente.

### 2) Estado financiero

- **Cajas activas**: cada `Caja` con `activa=True`, calcular saldo con `caja_saldo.calcular_saldo()`. Listar con saldo.
- **Deudores total**: suma de saldos positivos de la lista de morosos calculada igual que el reporte 1.
- **Pasivo (gastos a pagar)**: `Gasto.fecha_pago` es `nullable=False` (verificado en `backend/models.py:536`). El admin siempre carga gastos con fecha de pago concreta. Por lo tanto el "pasivo" se define como gastos cuya `fecha_pago > fecha_corte` (gastos registrados como futuros). En el uso típico esto será cero o muy poco — la mayoría de admins carga gastos ya pagados. Si el patrón cambia (admins registran gastos futuros para planificar), el reporte refleja esa información.
- **Activo total** = suma cajas + deudores_total
- **Pasivo total** = suma de pasivos
- **Patrimonio neto** = activo_total - pasivo_total
- Filtro `fecha_corte` (default = hoy).

### 3) Detalle de gastos del período

- **Iterar** todos los `Gasto` cuyo `periodo == periodo_filtro`.
- Aplicar filtros opcionales `rubro` y `proveedor_id`.
- Separar en dos grupos:
  - **Por rubro**: gastos con `clase_prorrateo_id IS NOT NULL` → agrupar por `rubro`, subtotales.
  - **Particulares**: gastos con `clase_prorrateo_id IS NULL AND departamento_id IS NOT NULL` → lista plana.
- Total general al final.

### 4) Lista de proveedores

- **Agregar** por `Gasto.proveedor_id` filtrando por año (`Gasto.periodo LIKE 'YYYY-%'`) y opcionalmente por período exacto.
- Por proveedor: contar gastos, sumar montos, tomar la última `fecha_pago`.
- Orden default: total_facturado descendente.

## Tests

### Backend

- `tests/test_reportes_morosos.py` (~5 tests):
  - Depto al día (saldo ≤ 0) no aparece con `solo_deudores=true`.
  - Depto con saldo > 0 aparece con monto correcto.
  - Con `solo_deudores=false`, todos los deptos aparecen (incluso a favor).
  - Orden default por monto descendente.
  - Endpoint: 200 admin / 200 representante / 200 depto / 401 sin token.

- `tests/test_reportes_estado_financiero.py` (~4 tests):
  - Activo = suma de saldos de cajas activas + suma de deudores.
  - Pasivo = gastos sin pagar o con fecha futura.
  - Patrimonio = activo - pasivo.
  - Filtro `fecha_corte` respeta la fecha.

- `tests/test_reportes_gastos_periodo.py` (~4 tests):
  - Gastos agrupados por rubro con subtotales correctos.
  - Filtro por rubro funciona.
  - Filtro por proveedor funciona.
  - Período sin gastos → array vacío + total cero.

- `tests/test_reportes_proveedores.py` (~3 tests):
  - Suma de gastos por proveedor correcta.
  - Orden por total descendente.
  - Filtro por año respeta el rango.

- `tests/test_reportes_pdf.py` (~4 tests):
  - Smoke: cada PDF se genera, devuelve bytes con magic `%PDF-`.

**Total estimado: ~20 tests nuevos.**

### Sin tests E2E del frontend
Smoke manual al cierre.

## Migración

Ninguna. Cero cambios al modelo de datos.

## Out-of-scope explícito

- ❌ Formato oficial Ley 941 CABA (Fase 6c).
- ❌ Export a Excel/CSV.
- ❌ Gráficos (charts.js o similar) — todo tablas.
- ❌ Comparativos año contra año.
- ❌ Reporte "evolución de cobranzas" mes a mes (Fase 6c si surge demanda).
- ❌ Drill-down (click en moroso → detalle). El admin ya tiene `/departamentos/{id}/cuenta`.
- ❌ Reportes por rango de fechas custom (siempre por mes o año estándar).
- ❌ Permisos finos por reporte.

## Bloqueos cross-recurso

Ninguno — los reportes son read-only.

## Estimación

- ~10-12 tasks (módulo `reportes.py` + funciones + tests · 4 endpoints JSON + tests · 4 endpoints PDF + tests · 4 funciones PDF en `pdf.py` · refactor `_dibujar_header_consorcio` · API client + 4 pantallas frontend · sidebar + routes + smoke + merge + roadmap).
- Tiempo total estimado: **1.5-2 semanas**.

## Historial

- 2026-06-25: brainstorming + spec inicial post-merge Fase 6a. Decisiones clave: 4 reportes juntos, PDF reusando ReportLab, transparencia total (admin + representante + depto), modo Ley 941 oficial queda para Fase 6c.

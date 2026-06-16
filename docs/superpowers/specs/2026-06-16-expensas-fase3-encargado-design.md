# Expensas — Fase 3: encargado y cargas sociales (ampliada) — diseño

Fecha: 2026-06-16
Estado: aprobado por el usuario, pendiente de plan de implementación.
Roadmap: [2026-06-16-expensas-completas-roadmap.md](2026-06-16-expensas-completas-roadmap.md)
Fases previas: [Fase 1](2026-06-16-expensas-fase1-modelo-central-design.md), [Fase 2](2026-06-16-expensas-fase2-gastos-design.md)

## Objetivo

Permitir a Administración liquidar el sueldo del/los empleado(s) del consorcio (típicamente el encargado bajo CCT SUTERH) con desglose de **haberes** que componen el bruto, cálculo automático de **descuentos** y **contribuciones** patronales, y generación de los **Gastos** correspondientes en el Rubro 1 (Sueldos y cargas sociales).

Esta fase es **ampliada respecto al roadmap original** — incluye desglose de haberes (básico + antigüedad + presentismo + HE + ad-hoc) para que el sistema sea utilizable en producción real desde el día uno.

## Reglas del proyecto aplicables

- `business-rules.md`: Administración es quien gestiona empleados, conceptos, haberes y liquidaciones. Ningún otro rol tiene acceso.
- `backend.md`: routers en `backend/routers/`, modelos en `backend/models.py`, schemas en `backend/schemas.py`, tests por router cubriendo 401/403/404/409/400.
- `openapi-first.md`: todos los endpoints nuevos se documentan primero en `openapi.yaml`.
- `frontend.md`: HTML semántico, mobile-first, ≥44px targets táctiles, paleta vía variables CSS.
- `security.md`: identidad y rol vienen del JWT.

## Decisiones de diseño

| Decisión | Elegida | Alternativas descartadas | Razón |
|---|---|---|---|
| Cálculo de cargas sociales | Configurable (catálogo `ConceptoLiquidacion`) | Hardcoded en código; manual | Paritarias cambian 2-3 veces al año; admin debe poder editar % sin esperar release. |
| Cantidad de empleados | Múltiples (tabla `Empleado` CRUD) | Singleton | Consorcios reales tienen titular + suplente + ayudante. |
| Categorías de empleado | Enum fijo (4 SUTERH) | Tabla configurable; texto libre | CCT no cambia categorías cada año. |
| Persistencia de la liquidación | Snapshot (`LiquidacionEmpleado` + `LiquidacionDetalle` + `LiquidacionHaber`) | Cálculo on-the-fly | Si admin cambia un % después de crear la liquidación, los datos históricos no deben modificarse. Regla básica de auditoría. |
| Relación liquidación ↔ gastos | Liquidación genera N Gastos automáticamente (con `Gasto.liquidacion_id`) | Independientes; un único Gasto agregado | Replica el PDF real: pagos separados a empleado, AFIP, FATERYH, SUTERH visibles en `/gastos`. |
| Modelo del bruto | Desglose en haberes (`Haber` + `LiquidacionHaber`) — ampliación | Un único campo `sueldo_bruto` (Fase 3 original) | Necesario para recibo de sueldo legal en Argentina y para cargar variables del mes (HE, presentismo). Modelo análogo a `ConceptoLiquidacion` para mantener consistencia. |
| Organización frontend | "Liquidaciones" en Expensas y pagos; "Empleados" + "Conceptos" + "Haberes" en Configuración | Todo bajo un único item "Sueldos" con tabs | Respeta el patrón del proyecto: catálogos estables en Configuración, módulo operativo en Expensas y pagos. |
| Proveedores institucionales | Seedeados al inicio (AFIP, ARCA, FATERYH, SUTERH) | Admin los crea | Los conceptos SUTERH requieren conocer estos proveedores; seedearlos evita errores de carga inicial. |
| Vinculación empleado ↔ proveedor | `Empleado.proveedor_id` obligatorio (1:1) | Crear empleado como proveedor implícito; vincular a varios | Necesario para que el sueldo neto se asigne a un proveedor concreto en el Gasto generado. |
| Cálculo de antigüedad | No automatizado (admin elige el % del haber) | Calcular desde `fecha_ingreso` | Admin ya viene con el % aplicado del recibo. Simple y predecible. |
| SAC (aguinaldo) | Haber ad-hoc que admin carga en jun/dic | Cálculo automático | El cálculo real es "mejor sueldo del semestre / 2" — agrega complejidad sin valor en MVP. |

## Modelo de datos

### Enums nuevos

```python
class CategoriaEmpleado(str, enum.Enum):
    encargado_permanente_con_vivienda = "encargado_permanente_con_vivienda"
    encargado_permanente_sin_vivienda = "encargado_permanente_sin_vivienda"
    encargado_suplente = "encargado_suplente"
    ayudante = "ayudante"


class TipoConcepto(str, enum.Enum):
    descuento = "descuento"          # se resta del bruto
    contribucion = "contribucion"    # paga el consorcio aparte del bruto


class TipoHaber(str, enum.Enum):
    monto_fijo = "monto_fijo"                          # ej. adicional vivienda
    porcentaje_sobre_basico = "porcentaje_sobre_basico"  # ej. antigüedad 12%
    cantidad_x_valor = "cantidad_x_valor"              # ej. HE 50% = cantidad × valor_hora
```

### `Empleado`

```python
class Empleado(Base):
    __tablename__ = "empleados"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String(255), nullable=False)
    cuil: Mapped[str] = mapped_column(String(13), unique=True, nullable=False)  # XX-XXXXXXXX-X
    categoria: Mapped[CategoriaEmpleado] = mapped_column(
        SqlEnum(CategoriaEmpleado, name="categoria_empleado"), nullable=False
    )
    fecha_ingreso: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_egreso: Mapped[date | None] = mapped_column(Date)
    sueldo_basico: Mapped[float] = mapped_column(Float, nullable=False)  # > 0, base para haberes %
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

### `Haber` (catálogo de componentes del bruto)

```python
class Haber(Base):
    __tablename__ = "haberes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)  # "Básico", "Antigüedad", "HE 50%"
    tipo: Mapped[TipoHaber] = mapped_column(SqlEnum(TipoHaber, name="tipo_haber"), nullable=False)
    valor_default: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # % o monto
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

### `ConceptoLiquidacion` (catálogo de descuentos/contribuciones)

```python
class ConceptoLiquidacion(Base):
    __tablename__ = "conceptos_liquidacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    tipo: Mapped[TipoConcepto] = mapped_column(SqlEnum(TipoConcepto, name="tipo_concepto"), nullable=False)
    porcentaje: Mapped[float] = mapped_column(Float, nullable=False)  # 0..100
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

> `proveedor_id` nullable: si es null, el concepto se aplica al cálculo pero **no** genera un Gasto separado (queda implícito en otro pago).

### `LiquidacionEmpleado`

```python
class LiquidacionEmpleado(Base):
    __tablename__ = "liquidaciones_empleado"
    __table_args__ = (
        UniqueConstraint("empleado_id", "periodo", name="uq_liquidacion_empleado_periodo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empleado_id: Mapped[int] = mapped_column(
        ForeignKey("empleados.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    periodo: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # "YYYY-MM"
    sueldo_bruto: Mapped[float] = mapped_column(Float, nullable=False)  # calculado: sum(haberes)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    haberes: Mapped[list["LiquidacionHaber"]] = relationship(
        back_populates="liquidacion", cascade="all, delete-orphan", order_by="LiquidacionHaber.orden"
    )
    detalle: Mapped[list["LiquidacionDetalle"]] = relationship(
        back_populates="liquidacion", cascade="all, delete-orphan", order_by="LiquidacionDetalle.orden"
    )
```

### `LiquidacionHaber` (snapshot de cada componente del bruto)

```python
class LiquidacionHaber(Base):
    __tablename__ = "liquidaciones_haber"

    id: Mapped[int] = mapped_column(primary_key=True)
    liquidacion_id: Mapped[int] = mapped_column(
        ForeignKey("liquidaciones_empleado.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)  # snapshot del nombre del Haber (o ad-hoc)
    tipo: Mapped[TipoHaber | None] = mapped_column(
        SqlEnum(TipoHaber, name="tipo_haber"), nullable=True
    )  # null si es ad-hoc (monto manual)
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)  # % o valor_hora; null si ad-hoc
    cantidad: Mapped[float | None] = mapped_column(Float, nullable=True)  # solo para cantidad_x_valor
    monto: Mapped[float] = mapped_column(Float, nullable=False)  # monto calculado o ingresado
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    liquidacion: Mapped["LiquidacionEmpleado"] = relationship(back_populates="haberes")
```

### `LiquidacionDetalle` (snapshot de descuentos y contribuciones)

```python
class LiquidacionDetalle(Base):
    __tablename__ = "liquidaciones_detalle"

    id: Mapped[int] = mapped_column(primary_key=True)
    liquidacion_id: Mapped[int] = mapped_column(
        ForeignKey("liquidaciones_empleado.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concepto_nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    concepto_tipo: Mapped[TipoConcepto] = mapped_column(
        SqlEnum(TipoConcepto, name="tipo_concepto"), nullable=False
    )
    porcentaje_aplicado: Mapped[float] = mapped_column(Float, nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    liquidacion: Mapped["LiquidacionEmpleado"] = relationship(back_populates="detalle")
```

### Cambio mínimo a `Gasto`

```python
liquidacion_id: Mapped[int | None] = mapped_column(
    ForeignKey("liquidaciones_empleado.id", ondelete="SET NULL"), nullable=True
)
```

## Lógica de cálculo (POST /liquidaciones)

**Input:** `{ empleado_id, periodo, haberes: [...], haberes_ad_hoc: [...] }`

**Algoritmo:**

1. **Resolver haberes desde catálogo:**
   ```python
   for item in payload.haberes:
       haber = db.get(Haber, item.haber_id)
       if haber.tipo == "monto_fijo":
           monto = item.valor_override or haber.valor_default
       elif haber.tipo == "porcentaje_sobre_basico":
           pct = item.valor_override or haber.valor_default
           monto = empleado.sueldo_basico * pct / 100
       elif haber.tipo == "cantidad_x_valor":
           valor = item.valor_override or haber.valor_default
           monto = item.cantidad * valor
       crear LiquidacionHaber(nombre=haber.nombre, tipo=haber.tipo, valor=valor, cantidad=cantidad, monto=monto)
   ```

2. **Sumar haberes ad-hoc** (cada uno con nombre + monto manual ingresado por admin):
   ```python
   for item in payload.haberes_ad_hoc:
       crear LiquidacionHaber(nombre=item.nombre, tipo=null, valor=null, cantidad=null, monto=item.monto)
   ```

3. **`sueldo_bruto = sum(haberes.monto)`** y persistir en `LiquidacionEmpleado`.

4. **Aplicar conceptos activos** (descuentos + contribuciones):
   ```python
   for concepto in db.scalars(select(ConceptoLiquidacion).where(activo=True).order_by(orden)).all():
       monto = sueldo_bruto * concepto.porcentaje / 100
       crear LiquidacionDetalle(concepto_nombre, tipo, porcentaje_aplicado, monto, proveedor_id, orden)
   ```

5. **Calcular sueldo neto:** `sueldo_neto = sueldo_bruto - sum(detalle donde tipo=descuento)`.

6. **Generar Gastos** del Rubro `sueldos_y_cargas_sociales`:
   - **1 Gasto** al empleado: monto = `sueldo_neto`, proveedor = `empleado.proveedor_id`, concepto = `"Sueldo neto - {nombre empleado}"`, `liquidacion_id` = liquidación recién creada.
   - **1 Gasto por proveedor único** entre los detalles: monto = suma de detalles con ese proveedor, proveedor = ese, concepto = nombres concatenados.
   - Todos con `clase_prorrateo_id` = primera clase activa por `id` (decisión simple para MVP).
   - Todos con `fecha_pago` = primer día del período.

7. **Devolver la liquidación con haberes + detalle + totales calculados.**

## Endpoints

Todos admin-only. Errores Pydantic → HTTP 400.

### Empleados — `backend/routers/empleados.py`

| Método | Path | Notas |
|---|---|---|
| GET | `/empleados?activo={bool}` | Listar. |
| POST | `/empleados` | 409 si CUIL duplicado; 404 si `proveedor_id` no existe. |
| GET | `/empleados/{id}` | Detalle. |
| PATCH | `/empleados/{id}` | Editar (CUIL inmutable). |
| DELETE | `/empleados/{id}` | Soft-delete si tiene liquidaciones; hard si no. |

### Haberes — `backend/routers/haberes.py`

| Método | Path | Notas |
|---|---|---|
| GET | `/haberes?activo={bool}` | Listar ordenado por `orden`, `nombre`. |
| POST | `/haberes` | 409 si nombre duplicado. |
| GET | `/haberes/{id}` | Detalle. |
| PATCH | `/haberes/{id}` | Editar todo. |
| DELETE | `/haberes/{id}` | Soft-delete (set `activo=false`). |

### Conceptos de liquidación — `backend/routers/conceptos_liquidacion.py`

| Método | Path | Notas |
|---|---|---|
| GET | `/conceptos-liquidacion?activo={bool}` | Listar ordenado. |
| POST | `/conceptos-liquidacion` | 409 si nombre duplicado; 404 si `proveedor_id` no existe. |
| GET | `/conceptos-liquidacion/{id}` | Detalle. |
| PATCH | `/conceptos-liquidacion/{id}` | Editar todo. |
| DELETE | `/conceptos-liquidacion/{id}` | Soft-delete siempre. |

### Liquidaciones — `backend/routers/liquidaciones.py`

| Método | Path | Notas |
|---|---|---|
| GET | `/liquidaciones?periodo=YYYY-MM&empleado_id=N` | Listar con detalle (eager-load de haberes y detalle). |
| POST | `/liquidaciones` | Body: `{ empleado_id, periodo, haberes: [{haber_id, valor_override?, cantidad?}], haberes_ad_hoc: [{nombre, monto}] }`. Calcula bruto, aplica conceptos, genera Gastos. 409 si duplicado `(empleado, periodo)`. |
| GET | `/liquidaciones/{id}` | Detalle completo. |
| PATCH | `/liquidaciones/{id}` | Recalcula con nuevos haberes (mismo body). Borra haberes/detalle/gastos viejos y regenera. |
| DELETE | `/liquidaciones/{id}` | Hard delete. Cascade borra haberes/detalle/gastos asociados. |

### Códigos de error

| Código | Cuándo |
|---|---|
| 400 | Validación Pydantic; `valor_override` inválido; `cantidad` requerida cuando el haber es `cantidad_x_valor`; etc. |
| 401 | Sin token. |
| 403 | Rol no admin. |
| 404 | Empleado/concepto/haber/liquidación/proveedor no existe. |
| 409 | CUIL duplicado, nombre de concepto/haber duplicado, `(empleado, periodo)` duplicado. |

## Frontend

### Sidebar actualizado

```
Expensas y pagos
  · Expensas
  · Comprobantes
  · Gastos
  · Liquidaciones                ← nuevo

Configuración
  · Datos del consorcio
  · Clases de prorrateo
  · Proveedores
  · Departamentos
  · Empleados                    ← nuevo
  · Haberes                      ← nuevo
  · Conceptos de liquidación     ← nuevo
```

> Configuración crece a 7 items. Si se vuelve incómodo, lo agrupamos con tabs internos en una fase posterior. Por ahora plano.

### Pantalla `/empleados` (Configuración)

Patrón estándar tipo Proveedores:
- Cabecera + filtro "Mostrar inactivos" + "+ Nuevo empleado".
- Lista de tarjetas: nombre · categoría, meta con CUIL, sueldo básico, fecha ingreso, proveedor asociado, badge Activo/Inactivo.
- Acciones: Editar, Desactivar/Activar.

**Modal "Nuevo empleado":** nombre completo, CUIL (regex), categoría (select del enum), fecha ingreso, fecha egreso (opcional), sueldo básico, proveedor (select). Helper UX: si no hay proveedor con CUIT igual al CUIL, link "Crear proveedor con este CUIL".

### Pantalla `/haberes` (Configuración)

- Cabecera + "+ Nuevo haber".
- Lista de tarjetas ordenadas: nombre · tipo, meta con valor default, orden, badge Activo/Inactivo.
- Acciones: Editar, Desactivar/Activar.

**Modal "Nuevo haber":** nombre, tipo (radio: `monto_fijo` / `porcentaje_sobre_basico` / `cantidad_x_valor`), valor default (label dinámico: "Monto" / "Porcentaje" / "Valor por unidad"), orden (number).

### Pantalla `/conceptos-liquidacion` (Configuración)

Igual al diseño anterior: cabecera, lista, modal con nombre, tipo (descuento/contribución), porcentaje, proveedor opcional, orden.

### Pantalla `/liquidaciones` (Expensas y pagos)

Tabs internos `Del mes` / `Historial` (mismo componente `Tabs`).

**Tab "Del mes" (`/liquidaciones`):**
- Filtro de período (month picker, default mes actual).
- Botón "+ Cargar liquidación".
- Lista de tarjetas con resumen: nombre empleado, bruto, neto, total liquidación.
- Cada tarjeta expandible muestra los haberes + descuentos + contribuciones.
- Acciones: Editar, Eliminar.

**Tab "Historial" (`/liquidaciones/historial`):**
- Filtros: empleado, período (opcional).
- Lista plana con los mismos cards.

**Modal "Cargar liquidación":**

```
Empleado: [Juan Pérez ▼]
Período: [2026-06 month picker]

Haberes:
  Básico                 (auto: del empleado)        $1.000.000
  Antigüedad             [%: 12]   = $1.000.000 × 12%  =  $120.000
  Presentismo            [%: 8.33] = $1.000.000 × 8.33% =  $83.300
  Horas extra 50%        [cantidad: 10] [valor: 5000]  =  $50.000
  [+ Agregar haber del catálogo]
  
  Haberes ad-hoc:
  [Nombre]  [Monto]  [X]
  [+ Agregar haber ad-hoc]

Total bruto:  $1.253.300

Vista previa de descuentos y contribuciones (se calcula al modificar haberes):
  Jubilación 11%:       $137.863
  ISSPJ 3%:             $37.599
  ...
Sueldo neto:            $964.040
Contribuciones:         $200.528
Total liquidación:      $1.453.828

[Cancelar]  [Guardar]
```

**Modal "Editar liquidación":** mismo formato, precargado con los haberes/valores actuales.

### API clients

- `frontend/src/api/empleados.js`
- `frontend/src/api/haberes.js`
- `frontend/src/api/conceptosLiquidacion.js`
- `frontend/src/api/liquidaciones.js`

## Tests

| Archivo | Cobertura específica |
|---|---|
| `tests/test_empleados.py` | CRUD + CUIL duplicado (409) + CUIL inválido (400) + proveedor inexistente (404) + soft/hard delete según liquidaciones. |
| `tests/test_haberes.py` | CRUD + nombre duplicado (409) + tipo inválido (400). |
| `tests/test_conceptos_liquidacion.py` | CRUD + nombre duplicado (409) + % fuera de rango (400) + proveedor inexistente (404). |
| `tests/test_liquidaciones.py` | CRUD + 409 duplicado + cálculo correcto bruto sumando haberes + haberes porcentuales usan `empleado.sueldo_basico` + haberes ad-hoc OK + snapshot congela montos + recálculo al editar + generación de N gastos con `liquidacion_id` + cascade en delete. |

**Tests integración clave:**
- Empleado con `sueldo_basico=$1M`. Crear liquidación con: `Básico` (monto_fijo, sin override), `Antigüedad` (porcentaje_sobre_basico, valor=12), `HE 50%` (cantidad_x_valor, cantidad=10, valor=5000). Asertar bruto = $1.170.000.
- Cambiar el % de un concepto **después** de crear la liquidación → asertar que `LiquidacionDetalle` mantiene el % original (snapshot).
- Editar liquidación con `sueldo_bruto` mayor → asertar que detalle se recalcula y gastos se regeneran.
- Eliminar liquidación → cascade borra `LiquidacionHaber`, `LiquidacionDetalle`, y los `Gasto` con `liquidacion_id` apuntando.

## Seed inicial (`backend/seed.py`)

1. **4 proveedores institucionales:** AFIP, ARCA, FATERYH, SUTERH (razón social + CUIT formato XX-XXXXXXXX-X ficticio).
2. **1 proveedor para empleado de ejemplo:** "Pérez, Juan" con CUIT propio matching el CUIL del empleado.
3. **1 empleado de ejemplo:** Juan Pérez, encargado_permanente_sin_vivienda, fecha_ingreso 2020-01-01, sueldo_basico $1.000.000, vinculado al proveedor del paso 2.
4. **6 haberes:**
   - "Básico" (porcentaje_sobre_basico, valor_default=100 — toma el `sueldo_basico` completo del empleado, equivalente a `básico × 100% = básico`. Admin puede override el % si en algún mes paga distinto).
   - "Antigüedad" (porcentaje_sobre_basico, valor_default=1.0 — 1% por año en SUTERH).
   - "Presentismo" (porcentaje_sobre_basico, valor_default=8.33).
   - "Adicional vivienda" (monto_fijo, valor_default=0 — admin completa según corresponda).
   - "Horas extra 50%" (cantidad_x_valor, valor_default=0).
   - "Horas extra 100%" (cantidad_x_valor, valor_default=0).
5. **12 conceptos de liquidación SUTERH (paritarias 2026 — referencia):**
   - Descuentos: Jubilación 11%, ISSPJ 3%, OSPERyHA 2.55%, ANSSAL 0.45%, Caja Familia 1%, Cuota SUTERH 2%, FMVDD 1.75%.
   - Contribuciones: AFIP F931 16%, ARCA VEP 10.78%, FATERYH 8.535%, FATERYH-SERACARH 0.5%, SUTERH patronal 4.51%.
   - Cada uno con `proveedor_id` correspondiente.
6. **No** crear liquidaciones — admin las carga al usar.

**Conftest de tests** (`tests/conftest.py`): sumar 1 empleado (id=900) con `sueldo_basico` razonable, 2 haberes (id=940 Básico, 941 Antigüedad), 2 conceptos básicos (id=950 Jubilación 11% descuento, 951 AFIP 16% contribución).

## Fuera de scope (Fase 3 ampliada)

- **SAC automático**: admin carga como haber ad-hoc en jun/dic.
- **Recibo de sueldo en PDF**: Fase 6.
- **Antigüedad calculada desde fecha_ingreso**: admin elige el % al cargar el haber.
- **Vacaciones, licencias, ausencias**: no.
- **Múltiples convenios** (no SUTERH): no.
- **Multi-tenant / multi-consorcio**: no (single-tenant).
- **Conceptos compuestos**: no (cada concepto es lineal).
- **Adelantos / préstamos al empleado**: no (se podría modelar como descuento ad-hoc en una fase futura).
- **Edición de liquidación pasada con regla de bloqueo**: no (Fase 4 introduce el cierre de período que bloqueará retroactivamente).
- **Sueldo neto bancario vs efectivo separados**: no.
- **Histórico/audit log de cambios de paritarias**: no.
- **Feature flag por consorcio para ocultar el módulo** (caso Madero Cleaners): anotado como mejora futura — ver memoria `[[feature-flag-personal-saas]]`.

# Fase 4 — Cierre de período y liquidación

Fecha: 2026-06-21
Estado: spec aprobada — pendiente plan de implementación.
Predecesores: Fase 3.5 (cuenta corriente por departamento — completada 2026-06-17).

## Contexto

Hasta Fase 3.5 el módulo de expensas permite crear boletas una por una (`POST /expensas`) y cobrar pagos contra una cuenta corriente por departamento con asignación FIFO. Sin embargo, las boletas reales de un consorcio se generan **en bloque al cierre del mes**, con un desglose por rubro/clase, dos vencimientos (1° y 2°), saldo anterior heredado del cierre previo, e intereses punitorios sobre los saldos morosos.

Esta fase reemplaza el flujo manual de "crear expensa una por una" por un evento contable formal: **el cierre del período**. Después del cierre, los gastos y las expensas de ese período quedan inmutables; las correcciones se hacen vía notas crédito/débito posteriores.

El diseño se apoya 100% en la cuenta corriente de Fase 3.5: los intereses y las notas son `MovimientoCuenta` ya soportados (`interes_punitorio`, `nota_debito`, `nota_credito`).

## Decisiones de diseño

| # | Tema | Decisión |
|---|---|---|
| 1 | Naturaleza del cierre | **Cierre formal** con nueva tabla `PeriodoCerrado`. Bloquea cargar/editar gastos y expensas del período. Correcciones via notas. |
| 2 | Vencimientos | **1° + 2° vencimiento** con recargo % configurable. `Expensa` pasa a tener dos fechas y dos montos. |
| 3 | Desglose | **Snapshot `ExpensaDetalle`** (rubro + clase|depto + concepto + monto) materializado al cierre. Patrón snapshot, coherente con `LiquidacionHaber` (Fase 3). |
| 4 | Intereses | **Automáticos al cierre del período siguiente** sobre saldos vencidos. Un único movimiento `interes_punitorio` por depto moroso, con descripción agregada. |
| 5 | Saldo anterior | **Snapshot en `Expensa.saldo_anterior`**. La boleta queda autocontenida; reimprimir 3 años después da el mismo número. |
| 6 | UX del cierre | **Preview-resumen + confirm**. Dashboard agregado con checklist de validaciones + totales + lista colapsable de deptos. Pantalla "Estado del cierre" disponible durante el mes para detectar errores temprano. |
| 7 | Fechas de vencimiento | **Regla configurable en `ConfiguracionConsorcio` + editables** en el modal de cierre. |
| 8 | Reapertura | **Sin reapertura**. Correcciones via notas crédito/débito (coherente con "estados terminales inmutables"). |
| 9 | Recargo 2° venc al no pagar | **Escuela 1: recargo OR intereses**. El recargo es solo info de display ("pagás hasta el 20 con +7%"). Si no pagás antes del 20, corren intereses sobre el monto del 1° venc — el recargo no se materializa. |
| 10 | Trazabilidad detalle ↔ gasto | **`ExpensaDetalle` guarda `concepto` como texto**, sin FK al gasto origen. |

## Sección 1 — Modelo de datos

### `Expensa` (modificada)

```python
class Expensa(Base):
    __tablename__ = "expensas"
    __table_args__ = (
        UniqueConstraint("departamento_id", "periodo", name="uq_expensa_depto_periodo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)

    # ─── renombrados (rename del campo viejo `monto` y `fecha_vencimiento`) ──
    monto_primer_vencimiento: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_primer_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)

    # ─── nuevos ─────────────────────────────────────────────────────────────
    monto_segundo_vencimiento: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_segundo_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)
    saldo_anterior: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    departamento: Mapped["Departamento"] = relationship(back_populates="expensas")
    detalle: Mapped[list["ExpensaDetalle"]] = relationship(
        back_populates="expensa", cascade="all, delete-orphan"
    )
```

**Migración del schema viejo:** como `Base.metadata.create_all()` no migra columnas, y el proyecto usa SQLite con seed regenerable, el reset esperado es: bajar uvicorn, borrar `consorcio.db`, levantar uvicorn (re-seedea). En el commit que cambia los nombres, agregar nota al README.

### `ExpensaDetalle` (nueva)

```python
class ExpensaDetalle(Base):
    __tablename__ = "expensa_detalle"

    id: Mapped[int] = mapped_column(primary_key=True)
    expensa_id: Mapped[int] = mapped_column(
        ForeignKey("expensas.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    rubro: Mapped[Rubro] = mapped_column(SqlEnum(Rubro, name="rubro"), nullable=False)

    # Excluyentes (valido a nivel schema, igual que Gasto):
    clase_prorrateo_id: Mapped[int | None] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="RESTRICT"), nullable=True
    )
    departamento_origen_id: Mapped[int | None] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=True
    )

    concepto: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)

    expensa: Mapped["Expensa"] = relationship(back_populates="detalle")
```

`departamento_origen_id` se usa cuando un gasto particular asignado al depto X aparece como línea en la propia expensa del depto X (típico: "reparación caño" del 1A se prorratea solo al 1A).

### `PeriodoCerrado` (nueva)

```python
class PeriodoCerrado(Base):
    __tablename__ = "periodos_cerrados"

    periodo: Mapped[str] = mapped_column(String(7), primary_key=True)
    fecha_cierre: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cerrado_por_usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    total_expensado: Mapped[float] = mapped_column(Float, nullable=False)
    total_intereses: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cantidad_expensas: Mapped[int] = mapped_column(Integer, nullable=False)
```

### `ConfiguracionConsorcio` (modificada — agregar campos)

```python
# Nuevos campos con defaults razonables:
dia_primer_vencimiento: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
dias_entre_vencimientos: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
recargo_segundo_vencimiento_pct: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
tasa_interes_mensual_pct: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
```

## Sección 2 — Lógica del cierre

### Módulo nuevo: `backend/cierre.py`

Función pura (sin side effects), análogo a `backend/cuenta_corriente.py`. Calcula el preview completo; el endpoint de cierre la llama, valida que no haya bloqueantes, y persiste todo en una transacción atómica.

```python
@dataclass
class Validacion:
    tipo: Literal["bloqueante", "warning"]
    codigo: str
    mensaje: str

@dataclass
class LineaDetalleExpensa:
    rubro: Rubro
    clase_prorrateo_id: int | None
    departamento_origen_id: int | None
    concepto: str
    monto: float

@dataclass
class ExpensaACrear:
    departamento_id: int
    saldo_anterior: float
    monto_primer_vencimiento: float
    monto_segundo_vencimiento: float
    detalle: list[LineaDetalleExpensa]

@dataclass
class InteresACrear:
    departamento_id: int
    monto: float
    descripcion: str

@dataclass
class PreviewCierre:
    periodo: str
    fecha_primer_vencimiento: date
    fecha_segundo_vencimiento: date
    validaciones: list[Validacion]
    expensas: list[ExpensaACrear]
    intereses: list[InteresACrear]
    total_expensado: float
    total_intereses: float

    @property
    def puede_cerrar(self) -> bool:
        return not any(v.tipo == "bloqueante" for v in self.validaciones)


def calcular_preview_cierre(
    db: Session,
    periodo: str,
    fecha_primer_venc: date | None = None,
    fecha_segundo_venc: date | None = None,
) -> PreviewCierre: ...


def calcular_intereses_al_cierre(
    db: Session, depto_id: int, fecha_corte: date
) -> tuple[float, str]: ...
```

### Algoritmo (orden estricto)

1. **Validar período no cerrado.** Si existe `PeriodoCerrado(periodo=X)` → raise `HTTPException(409)` antes de calcular nada.
2. **Resolver fechas.** Si vinieron del caller, usarlas. Si no, calcularlas con la regla de `ConfiguracionConsorcio`:
   - `fecha_1 = primer_dia_del_mes_siguiente_al_periodo.replace(day=config.dia_primer_vencimiento)`
   - `fecha_2 = fecha_1 + timedelta(days=config.dias_entre_vencimientos)`
3. **Validaciones estructurales** (devuelve lista de `Validacion`, no aborta):
   - **Bloqueante `coeficientes_faltantes`**: alguna clase activa **con gastos en el período** no tiene coeficiente cargado para algún departamento existente. Las clases sin gastos en el período actual no bloquean (alguien puede haber creado una clase nueva pero todavía no la usa).
   - **Bloqueante `coeficientes_no_suman_100`**: para cada clase activa **con gastos del período**, la suma de coeficientes ≠ 100.0 (tolerancia ±0.01).
   - **Bloqueante `gastos_huerfanos`**: hay `Gasto(periodo=X)` con `clase_prorrateo_id IS NULL AND departamento_id IS NULL`. (Defensivo: el schema Pydantic de `Gasto` ya valida exclusión, pero lo chequeamos por las dudas — y por si en el futuro entra algún gasto por otra vía.)
   - **Bloqueante `fechas_invalidas`**: `fecha_2 <= fecha_1`.
   - **Bloqueante `configuracion_incompleta`**: no existe `ConfiguracionConsorcio` o falta algún campo obligatorio.
   - **Warning `sin_gastos`**: no hay gastos del período.
   - **Warning `deptos_con_saldo_vencido`**: el listado de morosos al cierre.
   - **Warning `clases_sin_gastos`**: clases activas que no aparecen en ningún gasto del período.
4. **Prorrateo de gastos** (si no hay bloqueantes que detengan el cálculo siguiente; los bloqueantes no rompen el preview, lo entregan vacío de expensas si hace falta). Por cada `Gasto` del período:
   - Si `gasto.departamento_id` no es None → ese depto se lleva el 100%. `LineaDetalleExpensa(rubro, departamento_origen_id=depto_id, clase=None, concepto=gasto.concepto, monto=gasto.monto)`.
   - Si `gasto.clase_prorrateo_id` no es None → reparto entre los deptos que tienen `CoeficienteDepartamento` para esa clase. Para cada depto: `monto_depto = gasto.monto × (coef.porcentaje / 100)` con redondeo a 2 decimales; `LineaDetalleExpensa(rubro, clase_prorrateo_id=clase_id, departamento_origen_id=None, concepto=gasto.concepto, monto=monto_depto)`.
5. **Agrupar líneas por depto** → `ExpensaACrear.detalle`.
6. **`monto_primer_vencimiento`** = `sum(d.monto for d in detalle)`.
7. **`monto_segundo_vencimiento`** = `round(monto_primer * (1 + config.recargo_pct/100), 2)`.
8. **Cálculo de intereses por depto.** `calcular_intereses_al_cierre(db, depto_id, fecha_corte=date.today())`. La `fecha_corte` es el día real en que se ejecuta el cierre, no la última fecha del período. Si te demorás unos días en cerrar mayo, los intereses se calculan hasta ese día (más justo para el depto). Si > 0 → `InteresACrear` en la lista.
9. **`saldo_anterior`** por depto = `calcular_estado_cuenta(db, depto_id, hoy=date.today()).saldo_total + interes_de_este_cierre_para_este_depto`. (Se suma el interés porque en el orden de escritura los intereses se materializan **antes** de la nueva expensa, así que conceptualmente forman parte del saldo previo a la nueva boleta.)

### Regla de cálculo de intereses

```python
def calcular_intereses_al_cierre(
    db: Session, depto_id: int, fecha_corte: date
) -> tuple[float, str]:
    """Suma intereses sobre todas las expensas del depto con saldo > 0 cuyo
    2° vencimiento ya pasó. Tasa diaria = mensual_pct / 100 / 30.

    Returns:
        (monto_total, descripcion_agregada)
    """
```

- Para cada `Expensa` del depto donde `estado_calculado ∈ {parcial, vencida}` y `fecha_segundo_vencimiento <= fecha_corte`:
  - `dias_mora = (fecha_corte - fecha_segundo_vencimiento).days`
  - `tasa_diaria = config.tasa_interes_mensual_pct / 100 / 30`
  - `interes_expensa = round(monto_pendiente × tasa_diaria × dias_mora, 2)`
- Suma → `monto_total`. Descripción ejemplo: `"Intereses al 30-jun sobre 2 expensas vencidas ($1.200 + $300)"`.
- Si `monto_total == 0` → no se genera movimiento.

### Endpoint de cierre — escritura atómica

```python
@router.post("/periodos/{periodo}/cerrar")
def cerrar_periodo(periodo, payload, db, user_admin):
    preview = calcular_preview_cierre(db, periodo, payload.fecha_1, payload.fecha_2)

    if db.get(PeriodoCerrado, periodo):
        raise HTTPException(409, "El período ya está cerrado.")
    if not preview.puede_cerrar:
        raise HTTPException(409, "Hay validaciones bloqueantes pendientes.")

    # Transacción: si algo falla, rollback total.
    # 1) Intereses primero (forman parte del saldo previo a la nueva expensa).
    for it in preview.intereses:
        db.add(MovimientoCuenta(
            departamento_id=it.departamento_id,
            fecha=date.today(),
            tipo=TipoMovimiento.interes_punitorio,
            descripcion=it.descripcion,
            monto=it.monto,
        ))
    db.flush()

    # 2) Expensas + detalle + movimiento expensa_emitida.
    for exp in preview.expensas:
        e = Expensa(
            departamento_id=exp.departamento_id,
            periodo=periodo,
            monto_primer_vencimiento=exp.monto_primer_vencimiento,
            fecha_primer_vencimiento=preview.fecha_primer_vencimiento,
            monto_segundo_vencimiento=exp.monto_segundo_vencimiento,
            fecha_segundo_vencimiento=preview.fecha_segundo_vencimiento,
            saldo_anterior=exp.saldo_anterior,
        )
        db.add(e); db.flush()
        for d in exp.detalle:
            db.add(ExpensaDetalle(expensa_id=e.id, **asdict_safe(d)))
        db.add(MovimientoCuenta(
            departamento_id=exp.departamento_id,
            fecha=date.today(),
            tipo=TipoMovimiento.expensa_emitida,
            descripcion=f"Expensa {periodo}",
            monto=exp.monto_primer_vencimiento,
            expensa_id=e.id,
        ))

    # 3) Marcar período cerrado.
    db.add(PeriodoCerrado(
        periodo=periodo,
        cerrado_por_usuario_id=user_admin.id,
        total_expensado=preview.total_expensado,
        total_intereses=preview.total_intereses,
        cantidad_expensas=len(preview.expensas),
    ))
    db.commit()
```

## Sección 3 — Endpoints

### Recurso nuevo `/periodos`

| Verbo | Path | Rol | Resumen |
|---|---|---|---|
| `GET` | `/periodos` | admin | Lista períodos cerrados, orden desc por `fecha_cierre`. |
| `GET` | `/periodos/{periodo}/estado` | admin | Diagnóstico durante el mes: `{periodo, cerrado: bool, validaciones: [...]}`. Solo checklist, sin números monetarios. |
| `GET` | `/periodos/{periodo}/preview` | admin | Preview completo serializado. Query params opcionales `fecha_1`, `fecha_2`. 409 si ya está cerrado. |
| `POST` | `/periodos/{periodo}/cerrar` | admin | Cierra. Body `CerrarPeriodoIn{fecha_primer_vencimiento?, fecha_segundo_vencimiento?}`. 409 si ya cerrado o si hay bloqueantes. |

### Cambios a endpoints existentes

**`/gastos`:**
- `POST /gastos`: si `payload.periodo` corresponde a un período cerrado → 409 "El período {X} está cerrado y no admite cambios.".
- `PATCH /gastos/{id}` y `DELETE /gastos/{id}`: si el gasto pertenece a un período cerrado → 409. (Lectura sigue funcionando sin restricción.)

**`/expensas`:**
- `POST /expensas`: si el período está cerrado → 409. (Permitir crear individual solo si el período sigue abierto, p.ej. extraordinarias antes del cierre.)
- `PATCH /expensas/{id}` y `DELETE /expensas/{id}`: si la expensa es de un período cerrado → 409.

**`/liquidaciones`:**
- `POST /liquidaciones`, `PATCH /liquidaciones/{id}` y `DELETE /liquidaciones/{id}`: si el `periodo` está cerrado → 409 (porque la liquidación crea/edita `Gasto` con ese período).

**`/configuracion` (PATCH):**
- Agregar al schema los 4 campos nuevos. Validaciones:
  - `dia_primer_vencimiento`: `1 <= n <= 28`
  - `dias_entre_vencimientos`: `n >= 1`
  - `recargo_segundo_vencimiento_pct`: `n >= 0`
  - `tasa_interes_mensual_pct`: `n >= 0`

**`/comprobantes` y `/movimientos`:** sin cambios funcionales — la cuenta corriente sigue viva incluso para períodos cerrados (deptos pueden seguir pagando boletas viejas, admin puede emitir notas).

### Schemas Pydantic nuevos (en `backend/schemas.py`)

- `ValidacionOut`
- `LineaDetalleExpensaOut`
- `ExpensaACrearOut`
- `InteresACrearOut`
- `PreviewCierreOut`
- `EstadoCierreOut` (subset de Preview, sin números)
- `CerrarPeriodoIn`
- `PeriodoCerradoOut`

### Schemas modificados

- `ExpensaOut`: agregar `monto_primer_vencimiento`, `fecha_primer_vencimiento`, `monto_segundo_vencimiento`, `fecha_segundo_vencimiento`, `saldo_anterior`, `detalle: list[LineaDetalleExpensaOut]`. Eliminar los nombres viejos `monto`, `fecha_vencimiento`.
- `ConfiguracionUpdate` y `ConfiguracionOut`: agregar los 4 campos nuevos.

### OpenAPI

Documentar primero en `openapi.yaml` siguiendo la regla del proyecto. Path parameters con nombre completo (`{periodo}`, no `{p}`).

## Sección 4 — UI

### Pantalla nueva `/cierre-de-periodo` (admin)

Dos modos en la misma ruta:

**Modo "Estado"** — vista por defecto al entrar:
- Header con `<select>` de período (mes actual + 2 anteriores no cerrados).
- Bloque "Estado de {periodo}" mostrando el checklist de validaciones (verde/amarillo/rojo) devuelto por `GET /periodos/{periodo}/estado`.
- Cuando todas las bloqueantes están verdes, se habilita el botón **"Generar preview"** que dispara el modo siguiente.

**Modo "Preview"** — después de generar:
- Editor de fechas (`fecha_primer_vencimiento`, `fecha_segundo_vencimiento`) prellenado por la regla. Cambiar la fecha llama a `GET /periodos/{periodo}/preview?fecha_1=...&fecha_2=...` y refresca el dashboard.
- Resumen agregado: 4 KPIs (total a expensar, boletas a emitir, intereses, saldo anterior total).
- Comparación opcional con el período anterior (delta absoluto + %).
- Tabla colapsable de deptos. Una fila por depto: código + monto del 1° venc + saldo anterior + total a pagar. Click en la fila → expande mostrando el `detalle` con rubro/clase/concepto/monto.
- Botón **"← Volver"** vuelve al modo Estado.
- Botón **"Confirmar cierre del mes"** (deshabilitado si hay rojos): abre modal de confirmación final con texto explícito sobre irreversibilidad → `POST /periodos/{periodo}/cerrar`.
- Al recibir 201, redirect a `/periodos` con success toast.

### Pantalla nueva `/periodos` (admin)

Tabla de historial:

| Período | Cerrado el | Cerrado por | Boletas | Total expensado | Intereses | Acciones |
|---|---|---|---|---|---|---|
| 2026-05 | 31-may 14:32 | admin | 6 | $510.000 | $4.500 | [Ver expensas] |

"Ver expensas" → `/expensas?periodo=2026-05` (filtro ya existente).

### Cambios en pantallas existentes

**Sidebar (admin):** en la sección "Expensas y pagos" agregar:
- "Cierre de período" → `/cierre-de-periodo`
- "Historial de cierres" → `/periodos`

**`/expensas` (admin y depto) — `TarjetaExpensa`:**
```
Expensa 2026-05 — UF-1A    [BadgeEstado]
1° vencimiento (hasta 10-jun):  $85.200
2° vencimiento (11 al 20-jun):  $91.164  (+7%)
Después del 20-jun: +intereses 3% mensual
Saldo anterior:                 $0
Total a pagar:                  $85.200
[Ver desglose]
```

"Ver desglose" abre modal con la lista de `ExpensaDetalle` agrupada por rubro, formato:
```
Rubro 1 — Sueldos y cargas sociales            $42.000
  Clase A (50%)         Sueldo encargado abril  $35.000
  Clase A (50%)         Cargas sociales abril    $7.000
Rubro 2 — Servicios                             $28.200
  ...
Particulares                                    $15.000
  UF-1A                 Reparación caño         $15.000
─────────────────────────────────────────────────────
Total                                           $85.200
```

**`/mi-cuenta` (depto):** el bloque de saldo destaca el próximo vencimiento:
```
Saldo actual: $85.200

Próximo vencimiento: 10-jun
  Pagás hasta 10-jun:    $85.200
  Del 11 al 20-jun:      $91.164 (+7%)
  Después del 20-jun:    se acumulan intereses 3% mensual
```

**`/configuracion` (admin):** sección nueva "Vencimientos e intereses" con los 4 campos editables.

**`/gastos` (admin):** filas de gastos pertenecientes a períodos cerrados se muestran con candado y tooltip "Período cerrado — no editable". Las acciones Editar/Borrar quedan ocultas en esas filas.

## Sección 5 — Reglas y validaciones consolidadas

### Reglas de cierre

| Acción | Período abierto | Período cerrado |
|---|---|---|
| `POST/PATCH/DELETE /gastos` para período X | ✅ | 🚫 409 |
| `POST/PATCH/DELETE /liquidaciones` con periodo X | ✅ | 🚫 409 |
| `POST /expensas` (creación individual) en período X | ✅ | 🚫 409 |
| `PATCH/DELETE /expensas/{id}` de período X | n/a | 🚫 409 |
| `POST /comprobantes` (presentar pago) | ✅ | ✅ |
| `PATCH /comprobantes/{id}` (admin aprueba/rechaza) | ✅ | ✅ |
| Crear `MovimientoCuenta` tipo `nota_credito`/`nota_debito` | ✅ | ✅ |

Regla mental: **cerrar congela gastos y expensas. La cuenta corriente sigue viva.**

### Códigos de validación (devueltos por `/preview` y `/estado`)

**Bloqueantes:** `configuracion_incompleta`, `coeficientes_faltantes`, `coeficientes_no_suman_100`, `gastos_huerfanos`, `periodo_ya_cerrado`, `fechas_invalidas`.

**Warnings:** `sin_gastos`, `deptos_con_saldo_vencido`, `clases_sin_gastos`.

### Invariantes del modelo (post-cierre)

- `UniqueConstraint(departamento_id, periodo)` en `Expensa` (existente, conservar).
- Si existe `PeriodoCerrado(periodo=X)` → existe **exactamente 1** `Expensa` por departamento existente para ese período.
- Si existe `Expensa(periodo=X)` perteneciente a un período cerrado → `sum(detalle.monto) == monto_primer_vencimiento` (tolerancia ±0.01 por redondeo).
- `Expensa.monto_segundo_vencimiento ≈ monto_primer_vencimiento × (1 + recargo_pct/100)` ± 0.01.
- `Expensa.fecha_segundo_vencimiento > Expensa.fecha_primer_vencimiento`.
- Cada `Expensa` creada por el cierre → existe **1** `MovimientoCuenta(tipo=expensa_emitida)` con `expensa_id` apuntando a ella y `monto = monto_primer_vencimiento`.
- Por cierre y por depto moroso → **0 o 1** `MovimientoCuenta(tipo=interes_punitorio)` (agregado).
- `ExpensaDetalle.clase_prorrateo_id` XOR `ExpensaDetalle.departamento_origen_id`.

### Permisos

| Endpoint | Admin | Depto | Representante |
|---|---|---|---|
| `GET /periodos`, `/periodos/{p}/estado`, `/periodos/{p}/preview` | ✅ | 🚫 403 | 🚫 403 |
| `POST /periodos/{p}/cerrar` | ✅ | 🚫 403 | 🚫 403 |
| `PATCH /configuracion` (campos nuevos) | ✅ | 🚫 403 | 🚫 403 |
| `GET /expensas` (con shape nuevo) | ✅ todas | ✅ propias | 🚫 |
| `GET /movimientos/mi-cuenta` (incluye intereses) | n/a | ✅ | n/a |

Igual al patrón Fase 3.5: identidad y rol siempre del JWT.

## Sección 6 — Tests

### Distribución

| Archivo | Cobertura |
|---|---|
| `tests/test_cierre.py` (nuevo) | Unit tests de `calcular_preview_cierre` + `calcular_intereses_al_cierre`. |
| `tests/test_periodos.py` (nuevo) | Endpoints `/periodos/*`: GET listar/estado/preview + POST cerrar. Happy + 401/403/404/409. |
| `tests/test_gastos.py` (existente, agregar) | 409 al POST/PATCH/DELETE en período cerrado. |
| `tests/test_expensas.py` (existente, agregar) | Shape nueva (`monto_primer_vencimiento`, `saldo_anterior`, `detalle[]`). 409 al editar/borrar expensa de período cerrado. |
| `tests/test_configuracion.py` (existente, agregar) | Validaciones de los 4 nuevos campos. |
| `tests/test_liquidaciones.py` (existente, agregar) | 409 al operar liquidaciones cuyos gastos caen en período cerrado. |

### Casos clave de `test_cierre.py`

```
# Prorrateo
test_preview_periodo_vacio_genera_warning_sin_gastos
test_preview_un_gasto_clase_se_prorratea_por_coeficientes
test_preview_gasto_particular_va_solo_al_depto_indicado
test_preview_rubros_se_agrupan_correctamente_en_detalle
test_preview_suma_detalles_igual_monto_primer_venc

# Vencimientos
test_preview_monto_segundo_venc_aplica_recargo_correcto
test_preview_fecha_default_por_regla_configurable
test_preview_fecha_explicita_override_regla

# Validaciones
test_preview_validacion_bloqueante_coef_faltante
test_preview_validacion_bloqueante_coef_no_suma_100
test_preview_validacion_bloqueante_gasto_huerfano
test_preview_validacion_bloqueante_fechas_invalidas
test_preview_validacion_warning_clase_sin_gastos
test_preview_validacion_warning_deptos_con_saldo_vencido

# Intereses
test_intereses_depto_al_dia_devuelve_cero
test_intereses_pago_a_tiempo_devuelve_cero
test_intereses_un_mes_de_mora_calcula_correcto
test_intereses_pago_parcial_solo_sobre_pendiente
test_intereses_varias_expensas_vencidas_se_suman
test_intereses_acumulados_se_incluyen_en_proximo_saldo_anterior
```

### Casos clave de `test_periodos.py`

```
# Listar e historial
test_listar_periodos_admin_200
test_listar_periodos_depto_403

# Estado
test_get_estado_admin_200_devuelve_validaciones
test_get_estado_periodo_cerrado_marca_cerrado_true

# Preview
test_get_preview_admin_200
test_get_preview_periodo_cerrado_409
test_get_preview_depto_403
test_get_preview_con_fechas_query_params_usa_esas

# Cierre
test_cerrar_periodo_genera_n_expensas_con_movimientos
test_cerrar_periodo_genera_intereses_para_deptos_morosos
test_cerrar_periodo_persiste_expensa_detalle_completo
test_cerrar_periodo_persiste_saldo_anterior_correcto
test_cerrar_periodo_marca_periodo_cerrado
test_cerrar_periodo_idempotente_segundo_call_409
test_cerrar_periodo_con_bloqueante_409_sin_escribir_nada
test_cerrar_periodo_atomico_si_falla_a_medias_nada_persiste

# Bloqueos cross-recurso
test_post_gasto_periodo_cerrado_409
test_patch_gasto_periodo_cerrado_409
test_delete_gasto_periodo_cerrado_409
test_post_expensa_individual_periodo_cerrado_409
test_delete_expensa_periodo_cerrado_409
test_post_liquidacion_periodo_cerrado_409

# Operaciones que SIGUEN funcionando
test_comprobante_periodo_cerrado_sigue_funcionando_200
test_nota_credito_periodo_cerrado_sigue_funcionando_200
```

### Fixtures

- Reutilizar `conftest.py` existente (admin + depto_a + depto_b + clase_prorrateo 50/50).
- Fixture nuevo `db_lista_para_cierre`: agrega 1 clase de prorrateo 50/50, 3-4 gastos del período de prueba (mix de rubros, mix clase/particular), una expensa previa con saldo pendiente para forzar cálculo de intereses.
- Composable sobre las fixtures existentes; sin rewrite.

### Verificación cruzada

Después de implementar:
- Suite total verde (453 actuales + ~40 nuevos ≈ 490+).
- Build de frontend verde.
- Smoke manual del flujo Estado → Preview → Confirmar → Historial.

## Out-of-scope (NO va en Fase 4)

- Recargo automático aplicado como nota_débito al pasar 2° vencimiento (Escuela 2 — descartado, decisión 9).
- Reapertura de período cerrado (decisión 8).
- PDF de la liquidación (Fase 6).
- Reporte de morosos / evolución de cobranzas (Fase 6).
- Caja, fondo de reparación, conciliación (Fase 5).
- Notificación/envío automático de boletas (out-of-scope global del roadmap).
- Job nocturno de intereses (descartado en decisión 4).

## Próximo paso

Plan de implementación TDD vía skill `superpowers:writing-plans`.

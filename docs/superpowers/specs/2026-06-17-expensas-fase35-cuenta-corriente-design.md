# Expensas — Fase 3.5: cuenta corriente por departamento — diseño

Fecha: 2026-06-17
Estado: aprobado por el usuario, pendiente de plan de implementación.
Roadmap: [2026-06-16-expensas-completas-roadmap.md](2026-06-16-expensas-completas-roadmap.md)

## Objetivo

Reemplazar el modelo binario actual de pagos (`Expensa.estado=pendiente|pagada`) por un modelo de **cuenta corriente por departamento**: cada depto tiene un libro de movimientos contables (débitos/créditos) cuyo saldo refleja su deuda real. Soporta pagos parciales, sobre-pagos, notas de crédito/débito, y deja base sólida para que Fase 4 modele intereses sobre mora correctamente.

Esta fase es **prerrequisito de Fase 4** — surgió durante el brainstorming de Fase 4 al descubrir que el modelo binario no soporta los casos requeridos.

## Reglas del proyecto aplicables

- `business-rules.md`: Departamentos ven solo su cuenta; Administración gestiona todas. Las notas crédito/débito son admin-only.
- `backend.md`: routers en `backend/routers/`, modelos en `backend/models.py`, tests por router con 401/403/404/400/409.
- `openapi-first.md`: endpoints nuevos documentados primero en `openapi.yaml`.
- `frontend.md`: HTML semántico, mobile-first, paleta vía variables CSS.
- `security.md`: identidad y rol vienen del JWT.

## Decisiones de diseño

| Decisión | Elegida | Alternativas descartadas | Razón |
|---|---|---|---|
| Asignación de pagos a expensas | FIFO automático | Manual; híbrido | Estándar contable. Cero decisiones para admin. Override manual queda para fase futura. |
| Estado de la expensa | Calculado on-the-fly desde movimientos | Persistido + actualizado; cache denormalizado | Volumen real (decenas de movimientos/depto/año) es trivial recalcular. Cache puede divergir. |
| Modelo `MovimientoCuenta` | Tabla única con `tipo` enum + `monto` siempre positivo | Una tabla por tipo; montos signados | Una tabla = un extracto. Monto positivo evita errores de signo (el `tipo` decide). |
| `Comprobante.expensa_id` | Eliminado; reemplazado por `departamento_id` | Mantener como hint opcional; eliminar Comprobante entero | El depto presenta pago a su cuenta, no a expensa específica. FIFO decide. |
| Migración | Clean start (consorcio.db borrado, seed actualizado) | Script de migración de datos existentes | Patrón consistente con Fases 1-3. Sin producción real todavía. |
| Reversión de aprobación de comprobante | Inmutable (compensación con nota crédito/débito) | Reversión directa; reversión con anulación visible | Lo que ya hay codificado. Errores raros se compensan manualmente. |
| Estado `vencida` | Calculado lazy desde fecha_vencimiento + saldo | Job programado que actualiza | Sin jobs en el proyecto. Lazy es suficiente. |

## Modelo de datos

### Enum nuevo

```python
class TipoMovimiento(str, enum.Enum):
    expensa_emitida = "expensa_emitida"      # débito
    pago_recibido = "pago_recibido"          # crédito
    interes_punitorio = "interes_punitorio"  # débito (Fase 4)
    nota_debito = "nota_debito"              # débito
    nota_credito = "nota_credito"            # crédito
```

**Mapeo tipo → signo:** débito suma al saldo, crédito resta. Listas:
- Débitos: `expensa_emitida`, `interes_punitorio`, `nota_debito`.
- Créditos: `pago_recibido`, `nota_credito`.

### Tabla nueva `MovimientoCuenta`

```python
class MovimientoCuenta(Base):
    __tablename__ = "movimientos_cuenta"

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tipo: Mapped[TipoMovimiento] = mapped_column(
        SqlEnum(TipoMovimiento, name="tipo_movimiento"), nullable=False
    )
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)  # SIEMPRE positivo

    expensa_id: Mapped[int | None] = mapped_column(
        ForeignKey("expensas.id", ondelete="SET NULL"), nullable=True
    )
    comprobante_id: Mapped[int | None] = mapped_column(
        ForeignKey("comprobantes.id", ondelete="SET NULL"), nullable=True
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

Validación Pydantic: `monto > 0` siempre.

### Modificaciones a tablas existentes

**`Expensa` — quitar `estado` y relación a comprobantes:**

```python
class Expensa(Base):
    __tablename__ = "expensas"
    __table_args__ = (
        UniqueConstraint("departamento_id", "periodo", name="uq_expensa_depto_periodo"),
    )
    id: Mapped[int]
    departamento_id: Mapped[int] = mapped_column(ForeignKey("departamentos.id", ondelete="RESTRICT"))
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)
    # ELIMINADO: estado
    # ELIMINADA: relationship comprobantes

    departamento: Mapped["Departamento"] = relationship(back_populates="expensas")
```

**`Comprobante` — `expensa_id` → `departamento_id`:**

```python
class Comprobante(Base):
    __tablename__ = "comprobantes"
    id: Mapped[int]
    # ELIMINADO: expensa_id
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    fecha_pago: Mapped[date]
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    archivo_path: Mapped[str | None]
    estado: Mapped[EstadoComprobante]  # sigue igual
    fecha_creacion: Mapped[datetime]
```

**`EstadoExpensa` enum** — se queda en `models.py` para uso en schemas/responses (no se persiste). Sumar `parcial`:

```python
class EstadoExpensa(str, enum.Enum):
    pendiente = "pendiente"
    parcial = "parcial"     # nuevo
    pagada = "pagada"
    vencida = "vencida"
```

## Lógica FIFO — `backend/cuenta_corriente.py` (módulo nuevo)

Función pura sin side-effects. Lee movimientos del depto ordenados cronológicamente y aplica FIFO mentalmente:

```python
def calcular_estado_cuenta(db: Session, departamento_id: int, hoy: date | None = None):
    """
    Returns:
        EstadoCuenta(
            saldo_total: float,  # positivo = debe, negativo = a favor
            por_expensa: dict[int, EstadoExpensaCalculado]
        )
    """
    # 1. Obtener todos los movimientos del depto, ordenados por fecha + id.
    # 2. Iterar acumulando saldo. Cada vez que un crédito entra, se aplica
    #    contra la(s) expensa(s) pendiente(s) más vieja(s) (FIFO).
    # 3. Para cada expensa, determinar:
    #    - monto_pagado_acumulado (cuánto del pago/crédito le aplicó FIFO).
    #    - monto_pendiente (= monto - pagado).
    #    - estado (pendiente / parcial / pagada / vencida si fecha_vencimiento < hoy).
    # 4. Saldo total = sum(débitos) - sum(créditos).
```

Esta función es la fuente de verdad. Se usa desde:
- `GET /expensas` (depto y admin) — para mostrar estado calculado.
- `GET /movimientos/mi-cuenta` (depto) y `/departamentos/{id}/cuenta` (admin) — para mostrar saldo + extracto.

## Endpoints

### Movimientos — `backend/routers/movimientos.py` (nuevo)

| Método | Path | Rol | Notas |
|---|---|---|---|
| GET | `/movimientos/mi-cuenta` | depto | Movimientos del depto autenticado. Filtros opcionales `?desde=YYYY-MM-DD&hasta=YYYY-MM-DD`. Devuelve lista + saldo_total. |
| GET | `/departamentos/{departamento_id}/cuenta` | admin | Igual que arriba pero para cualquier depto. |
| POST | `/movimientos/nota` | admin | Body: `{departamento_id, tipo: nota_credito\|nota_debito, monto>0, descripcion, fecha?}`. Crea movimiento manual. |

### Expensas — modificaciones

- `GET /expensas` y `GET /expensas/{expensa_id}`: response suma `estado_calculado: EstadoExpensa` y `monto_pendiente: float` (vienen de la lógica FIFO).
- `POST /expensas` (admin): igual + internamente crea su `MovimientoCuenta(expensa_emitida, monto, departamento_id, expensa_id, fecha=fecha_creacion)`.
- `DELETE /expensas/{expensa_id}` (admin, **nuevo**): borra expensa solo si no tiene pagos asignados (sus créditos pueden recalcularse FIFO sobre otras). Caso simple: si `calcular_estado_cuenta` muestra `monto_pendiente == monto` (sin pago aplicado), permite borrar. Sino 409.
- El campo `estado` desaparece del schema `ExpensaOut`. Si algún test viejo lo asserta, actualizar.

### Comprobantes — modificaciones

- `POST /expensas/{expensa_id}/comprobantes` → **eliminado**.
- `POST /comprobantes` (depto, multipart/form-data) → **nuevo**: `{fecha_pago, monto, archivo}`. `departamento_id` se toma del JWT.
- `GET /comprobantes` → igual (sigue mostrando comprobantes con filtros).
- `PATCH /comprobantes/{comprobante_id}` (admin, aprobar/rechazar) → al aprobar, internamente crea `MovimientoCuenta(pago_recibido, monto=comprobante.monto, departamento_id=comprobante.departamento_id, comprobante_id=comprobante.id, fecha=comprobante.fecha_pago)`. Al rechazar, no hace nada extra.

### Códigos de error

| Código | Cuándo |
|---|---|
| 400 | Pydantic falla (monto<=0, fecha inválida, etc.). |
| 401 | Sin token. |
| 403 | Rol incorrecto (ej. depto intentando ver cuenta de otro). |
| 404 | Recurso no existe. |
| 409 | Borrar expensa con pagos aplicados; comprobante ya verificado. |

## Frontend

### Sidebar

```
Depto:
  General
    · Comunicación
  Expensas y pagos
    · Mi cuenta             ← nuevo (primero)
    · Expensas
    · Comprobantes

Admin:
  (igual a hoy + acceso a /departamentos/{id}/cuenta via botón)
```

### Pantalla `/mi-cuenta` (depto, nueva)

- Header: "Saldo: $X.XXX" (verde si crédito, rojo si deuda, gris si cero).
- Lista de movimientos cronológicos descendentes (más reciente arriba) con columnas: fecha, tipo (con badge), descripción, monto (con signo según tipo), saldo acumulado.
- Filtros: fecha desde/hasta (month picker o date picker).
- Botón "+ Presentar pago" → abre modal con form (fecha_pago, monto, archivo). Submit hace POST /comprobantes.
- Mensaje informativo: "Tu pago será visible cuando administración lo apruebe."

### Pantalla `/departamentos/{id}/cuenta` (admin, nueva)

- Cabecera con datos del depto (código, descripción).
- Misma vista de movimientos que `/mi-cuenta`.
- Botón "+ Nota de crédito" → modal: monto, descripción, fecha. Submit POST /movimientos/nota con `tipo=nota_credito`.
- Botón "+ Nota de débito" → idem con `tipo=nota_debito`.

### Pantalla `/expensas` (modificada)

- Las tarjetas muestran ahora `estado_calculado` (Pagada / Parcial / Pendiente / Vencida) en lugar del estado persistido.
- Se elimina el botón "Presentar comprobante" por tarjeta. Para pagar, depto va a `/mi-cuenta` o usa el botón "Mi cuenta" si está en /expensas.
- Sumar pill `Vence el DD/MM` con color de alerta si próximo a vencer.

### Pantalla `/comprobantes` (depto)

- Sin cambios estructurales. El depto ve sus comprobantes con su estado (pendiente_verificacion / aprobado / rechazado).
- Si en la lista no hay comprobantes, mostrar mensaje "Aún no presentaste pagos. Andá a 'Mi cuenta' para hacerlo."

### Pantalla `/comprobantes` (admin)

- UI igual a hoy. Al aprobar, ya no marca expensa — el backend genera movimiento.

### API clients (frontend)

- `frontend/src/api/movimientos.js` (nuevo): `listarMisMovimientos`, `listarMovimientosDepto`, `crearNota`.
- `frontend/src/api/comprobantes.js` (modificado): la función `presentarComprobante` cambia firma — ya no recibe expensaId. Solo `{fechaPago, monto, archivo}`.
- `frontend/src/api/expensas.js`: el response de listar y obtener trae `estado_calculado` y `monto_pendiente`.

## Tests

| Archivo | Cobertura |
|---|---|
| `tests/test_movimientos.py` (nuevo) | GET mi-cuenta (401, 403, 200 con depto); GET cuenta admin (401, 403 si depto, 404 si depto inexistente); POST nota (admin, 400 si monto<=0, 404 si depto inexistente, 403 si no admin); filtros desde/hasta. |
| `tests/test_cuenta_corriente.py` (nuevo) | Tests unitarios FIFO: pago exacto, pago parcial, sobre-pago (crédito), múltiples expensas cubiertas por un pago, mix nota crédito/débito, expensa vencida. Sin HTTP, directo a la función. |
| `tests/test_expensas.py` (modificar) | Sacar asserts sobre `estado` persistido. Sumar asserts sobre `estado_calculado` derivado. Test de DELETE: 204 si sin pagos, 409 si con pagos. |
| `tests/test_comprobantes.py` (modificar) | Cambiar POST de `/expensas/{id}/comprobantes` a `/comprobantes`. Sacar tests del `expensa_id`. Sumar test: aprobar comprobante genera movimiento en cuenta (verificable con GET cuenta). Rechazar no genera. |

## Seed inicial

Extender `backend/seed.py`:
- Por cada `Expensa` que ya se sembraba, también crear su `MovimientoCuenta(expensa_emitida, monto, departamento_id, expensa_id, fecha=fecha_vencimiento - 30 días)`.
- Por cada `Comprobante` ya aprobado en seed, crear su `MovimientoCuenta(pago_recibido, monto, departamento_id, comprobante_id, fecha=fecha_pago)`.
- Para variedad visual: crear 1-2 notas (1 crédito + 1 débito) sobre un depto cualquiera, montos pequeños.
- Eliminar referencias a `Comprobante.expensa_id` y `Expensa.estado` que ya no existen.

**Conftest** (`tests/conftest.py`): mismo ajuste, los Comprobantes y Expensas seedeados generan movimientos.

## Fuera de scope (Fase 3.5)

- **Intereses sobre mora** (Fase 4).
- **Cálculo automático de "vencida + interés"** (Fase 4).
- **Reversión de aprobación/rechazo** de comprobantes (queda inmutable; admin compensa con nota).
- **Asignación manual** de pagos a expensas (FIFO automático único; override queda para fase futura).
- **Tabla `AsignacionPago`** (cache de qué pago cubre qué expensa): cálculo on-the-fly es suficiente. Si el volumen crece, se agrega.
- **Audit log** de notas crédito/débito (quién las creó, por qué cambio): solo `fecha_creacion` por ahora.
- **Pago multi-expensa con checkbox** que el usuario propuso originalmente: cubierto naturalmente por FIFO sin checkbox.
- **Reversión / anulación** de movimientos creados por error: por ahora se compensan con notas inversas.
- **Notificaciones al depto** cuando se aprueba/rechaza su comprobante: fase futura.
- **Export del extracto a PDF/CSV**: Fase 6.

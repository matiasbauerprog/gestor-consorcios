# Fase 12 — Reservas de espacios comunes (diseño)

Fecha: 2026-06-28
Estado: diseño aprobado. Próximo paso: plan de implementación.

## Objetivo

Cerrar el módulo "Reserva de espacios" del CLAUDE.md con un flujo end-to-end usable: políticas configurables por amenity, cobro automático vía cuenta corriente, notificaciones, frontend mobile-first. El backend tiene los modelos `Amenity` y `Reserva` con CRUD básico desde fases tempranas; Fase 12 los extiende y suma el frontend completo.

## Decisiones tomadas en brainstorming

| Tema | Decisión |
|---|---|
| Alcance | Completo (MVP + costo + notificaciones). |
| Cobro | `MovimientoCuenta` `nota_debito` al confirmar, `nota_credito` al cancelar (con reglas de penalty). |
| Políticas | Por amenity (no globales). |
| Set de políticas | `precio_reserva`, `duracion_maxima_horas`, `anticipacion_maxima_dias`, `max_reservas_activas_por_depto`, `horas_minimas_cancelacion`. Todas opcionales (`None` = sin límite). |
| Notificaciones | Email-only al depto cuando confirma su reserva. Doble canal (email + campanita) al depto cuando admin cambia algo de su reserva. |
| Roles que reservan | Departamento + Administración (admin no paga). Representante sin acceso. |
| UX | Lista + form (sin calendario). |
| Soft-delete amenity | Flag `activo`. |

## Modelo de datos

### Cambios en `Amenity`

```python
class Amenity(Base):
    # ... campos existentes (id, nombre, descripcion) ...

    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    precio_reserva: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    duracion_maxima_horas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anticipacion_maxima_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_reservas_activas_por_depto: Mapped[int | None] = mapped_column(Integer, nullable=True)
    horas_minimas_cancelacion: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

Todos los campos de política son opcionales para que un amenity sea válido sin configuración explícita (compatibilidad con datos existentes).

### Cambios en `Reserva`

```python
class Reserva(Base):
    # ... campos existentes (id, amenity_id, usuario_id, inicio, fin, estado, fecha_creacion) ...

    movimiento_cuenta_id: Mapped[int | None] = mapped_column(
        ForeignKey("movimientos_cuenta.id", ondelete="SET NULL"),
        nullable=True,
    )
```

FK al `MovimientoCuenta` creado al confirmar, si tuvo costo. Null si la reserva fue gratuita o el reservante no era depto. Sirve para localizar el movimiento original cuando hay que revertirlo en la cancelación.

### Enums

Sin cambios. `EstadoReserva` queda con `confirmada` y `cancelada`.

### Migración

Clean start: drop + create + seed. No requiere migración real porque SQLite acepta los nuevos campos con default. El seed se actualiza con 1-2 amenities demo (SUM con precio, Laundry gratuita).

## Endpoints

### Existentes (modificados)

| Endpoint | Cambio |
|---|---|
| `GET /amenities` | Filtra `activo=true` por default. Query `?incluir_inactivos=true` solo aplica si el usuario es admin → ve todos. Para depto/representante el flag se ignora silenciosamente (siempre ven solo activos). No devuelve 403 — el flag pasa a no-op. |
| `POST /amenities` | Body suma campos de política. Schema valida tipos/rangos. |
| `PATCH /amenities/{amenity_id}` | Edita políticas y `activo`. |
| `POST /amenities/{amenity_id}/reservas` | Suma validaciones (ver abajo) y creación de `MovimientoCuenta` si aplica. |
| `DELETE /reservas/{reserva_id}` (cancelar) | Suma reversa de `MovimientoCuenta` con reglas de penalty. |

### Nuevos

| Endpoint | Roles | Descripción |
|---|---|---|
| `DELETE /amenities/{amenity_id}` | admin | Soft-delete (set `activo=false`). 409 si ya inactivo. |
| `GET /reservas/{reserva_id}` | admin / dueño | Detalle. 403 a otros, 404 si inexistente. |

### Validaciones del `POST /amenities/{amenity_id}/reservas`

Aplican en este orden (rechazo en la primera que falla):

1. Token presente → 401 si no.
2. Rol depto o admin → 403 si representante.
3. Amenity existe → 404.
4. `amenity.activo` es `True` → 409 si está inactivo.
5. `inicio > now` → 400 (no se puede reservar en el pasado).
6. `fin > inicio` → 400 (intervalo válido).
7. `(fin - inicio).total_seconds() / 3600 ≤ amenity.duracion_maxima_horas` (si está configurado) → 400.
8. `(inicio.date() - now.date()).days ≤ amenity.anticipacion_maxima_dias` (si está configurado) → 400.
9. Si depto y `amenity.max_reservas_activas_por_depto` está configurado: contar reservas del depto del usuario para ese amenity en estado `confirmada` con `inicio > now`. Si ese conteo es `>=` al límite, rechazar con 409 (la nueva reserva haría superar el tope). Si reservante es admin, no se aplica esta regla.
10. Anti-solapamiento (ya implementado): no debe existir otra `confirmada` con `inicio < payload.fin AND fin > payload.inicio` para el mismo amenity → 409.

Si todas pasan:

- Crear `Reserva(amenity_id, usuario_id=user.id, inicio, fin, estado=confirmada)`.
- **Si reservante es depto y `amenity.precio_reserva` no es null:**
  - Crear `MovimientoCuenta(departamento_id=user.departamento_id, fecha=date.today(), tipo=nota_debito, monto=amenity.precio_reserva, descripcion=f"Reserva {amenity.nombre} {inicio.date().isoformat()}")`.
  - `reserva.movimiento_cuenta_id = movimiento.id`.
- **Si reservante es admin:** no se crea movimiento, `movimiento_cuenta_id` queda null.
- Email de confirmación al depto (solo si reservante es depto), con detalle de fecha/hora/costo. No-op si reservante es admin.

### Validaciones del `DELETE /reservas/{reserva_id}` (cancelar)

1. Token presente → 401.
2. Reserva existe → 404.
3. Permiso: `user.id == reserva.usuario_id` o `user.rol == administracion` → 403 si no.
4. `reserva.estado != cancelada` → 409 si ya está cancelada.

Si todas pasan:

- `reserva.estado = cancelada`.
- **Reversa del cargo:** si `reserva.movimiento_cuenta_id` no es null, se decide si crear `nota_credito` reversora:
  - **Caso A (admin cancela reserva ajena):** se reversa SIEMPRE, sin importar el plazo. La cancelación no es decisión del depto, no corresponde penalty.
  - **Caso B (dueño cancela su propia reserva):**
    - Si `amenity.horas_minimas_cancelacion` es null → se reversa siempre (sin plazo configurado significa "siempre se permite cancelar gratis").
    - Si está configurado y `(reserva.inicio - now).total_seconds() / 3600 ≥ amenity.horas_minimas_cancelacion` → se reversa.
    - Si está configurado y el cálculo da `<` el plazo → NO se reversa (penalty 100%, el cargo original queda firme).
  - Reversa, cuando aplica = `MovimientoCuenta(departamento_id=..., fecha=date.today(), tipo=nota_credito, monto=mismo_monto, descripcion=f"Reversa de reserva cancelada {reserva.inicio.date().isoformat()}")`.
- **Notificación**: si quien cancela es admin sobre reserva ajena → doble canal (campanita + email) al depto dueño. Si dueño cancela su propia: sin notif.

## Frontend (mobile-first)

### Pantallas nuevas

**`/amenities`** (admin only) — CRUD.
- En desktop: tabla con columnas `nombre / precio / duración / anticipación / max activas / horas cancelación / activo`.
- En mobile (`<600px`): cada amenity es una card con título (nombre) y los campos como pares "label: value" debajo.
- Toggle "Mostrar inactivos" (default off).
- Botones "+ Nuevo amenity" (header) y "Editar" / "Dar de baja" por card/fila.
- "Dar de baja" muestra `window.confirm` antes de DELETE.

**`/reservas`** (depto + admin) — listado y creación.
- Header: `<select>` nativo de amenities activos (default primero) + link "Gestionar amenities" si admin.
- Sección **Banner de políticas**: muestra duración máx, anticipación máx, costo y plazo de cancelación gratuita del amenity seleccionado. En mobile colapsa a una línea con "ver más".
- Sección **Form de nueva reserva**: inputs `<input type="date">` + `<input type="time">` × 2 (inicio y fin). Validación cliente básica (fin > inicio, duración respeta límite). Submit → POST → manejo de 400/409 con `detail` del backend en pantalla. Sticky bottom bar en mobile con CTA "Confirmar reserva ($X)" o "Confirmar reserva" si gratis.
- Sección **Próximas reservas (todos los deptos)**: lista de las `confirmadas` futuras del amenity. Tabla en desktop, cards en mobile. Muestra depto/fecha/inicio/fin. Sirve como vista de disponibilidad sin calendario.
- Sección **Mis reservas** (solo depto): tabla/cards con propias (futuras y pasadas, últimas 20). Botón "Cancelar" si es futura. Mensaje informativo si cae fuera del plazo gratuito ("Cancelar ahora no reintegra el monto").

### Componentes

- `ModalAmenity` — form crear/editar amenity (compartido entre alta y edición).
- Reusa `Modal` base existente y los patrones de `acciones-modal`, `error`, `info`.

### Sidebar

Nueva sección **"Espacios comunes"** insertada entre "Tareas y presupuestos" y "Expensas y pagos":

```js
{
  titulo: "Espacios comunes",
  modulos: [
    { ruta: "/reservas", nombre: "Reservas", rolesPermitidos: ["administracion", "departamento"] },
    { ruta: "/amenities", nombre: "Amenities", rolesPermitidos: ["administracion"] },
  ],
}
```

Representante no ve la sección.

### API clients nuevos

- `frontend/src/api/amenities.js`: `listar`, `crear`, `actualizar`, `eliminar` (soft).
- `frontend/src/api/reservas.js`: `listar`, `obtener`, `crear` (anidado a amenity), `cancelar`.

### Reglas mobile-first

- Tablas → cards apiladas en `<600px`. Sin scroll horizontal nunca.
- Form vertical, inputs nativos de fecha/hora.
- Targets táctiles ≥44px.
- CTA principal sticky bottom en mobile.
- Test mínimo: usable a 375px.

## Edge cases y reglas técnicas

| Caso | Comportamiento |
|---|---|
| Dos POST simultáneos al mismo slot | Aceptamos: el segundo igual lo detecta porque ambos commits son secuenciales en SQLite. Sin lock optimista (escala consorcio). |
| MovimientoCuenta del cargo cae en período cerrado | El cargo usa `fecha=date.today()`, no `reserva.inicio`. Garantiza que cae en el período actual (en curso). |
| Reversa cae en otro período que el cargo original | Aceptamos. La `nota_credito` usa `fecha=date.today()` también; refleja contabilidad correcta sin reescribir historia. |
| Admin cancela su propia reserva | Solo cambia estado. Sin reversa (no había cargo). Sin notif. |
| Amenity desactivado con reservas futuras | Las reservas existentes se mantienen. Depto las puede cancelar. No se pueden crear nuevas reservas. |
| Depto sin `departamento_id` (admin con rol erróneo) | No debería pasar — el schema garantiza `departamento_id` no null para rol `departamento`. Si pasara, el cobro rompe con KeyError → es un bug de datos, no defendemos contra él. |
| `precio_reserva` cambia después de reservas existentes | Las reservas históricas mantienen su `movimiento_cuenta_id` con el monto original. El cambio solo afecta a reservas futuras. |
| Cancelación con `horas_minimas_cancelacion = null` | Significa "siempre se permite reversar". Se aplica reversa sin chequear plazo. |

## Status HTTP esperados

| Caso | Status |
|---|---|
| Reservar OK | 201 |
| Reservar datos inválidos (duración, body, fecha pasada) | 400 |
| Reservar sin token | 401 |
| Reservar como representante | 403 |
| Reservar amenity inexistente | 404 |
| Reservar amenity inactivo, solapamiento, o límite por depto | 409 |
| Cancelar OK | 200 |
| Cancelar reserva ajena (no admin) | 403 |
| Cancelar ya cancelada | 409 |
| Soft-delete amenity OK | 200 |
| Soft-delete amenity ya inactivo | 409 |

## Tests planificados (~30 nuevos)

**`test_amenities.py` (extensión):**
- Alta con políticas completas y parciales (200/201).
- Edit (PATCH) campos individuales.
- Soft-delete: 200 OK, 409 si ya inactivo, 403 si no admin.
- Listado: depto solo ve activos, admin con `?incluir_inactivos=true` ve todos.
- Gating por rol en CRUD.

**`test_reservas.py` (archivo nuevo):**
- POST: cada validación con su test (duración, anticipación, fecha pasada, límite por depto, amenity inactivo, solapamiento).
- Gating: representante 403, depto crea para sí, admin crea sin cobro.
- Cobro: depto reserva amenity con precio → se crea `MovimientoCuenta`. Sin precio → no se crea.
- Cancelación: dentro de plazo + dueño → reversa creada. Fuera de plazo → sin reversa. Admin cancela ajena → siempre reversa + notif doble canal al depto.
- GET /reservas/{id}: 200 admin/dueño, 403 otros, 404 inexistente.

## Out-of-scope (explícito)

- Calendario visual (mensual o semanal). Decisión P7: lista + form.
- Slots fijos predefinidos (ej. Laundry de 2h). Decisión P1: scope "Completo", no "Premium".
- Horario operativo del amenity (ej. SUM solo 10-22h). Decisión P1: scope "Completo".
- Lista de espera cuando está ocupado. Decisión P1: scope "Completo".
- Recordatorio 24h antes (cron real). Decisión P5: descartado — no hay scheduler en el proyecto.
- Pago real / pasarela. El cargo es solo un asiento en cuenta corriente del depto; la cobranza se materializa en la expensa del período.
- Edición de reserva existente. Solo cancelar y crear nueva. Más simple, evita lógica de "revertir + recrear movimiento".

## Estimación

~18 tasks. Similar a Fase 11 — 1-2 sesiones largas con subagent-driven-development. Backend ~8 commits, frontend ~6 commits, docs/seed/merge ~3 commits.

## Próximo paso

Invocar `superpowers:writing-plans` para generar el plan detallado de implementación.

# Fase 11 — Tareas y Presupuestos (end-to-end)

Fecha: 2026-06-26
Estado: spec aprobado (brainstorming cerrado con el usuario)

## Contexto y motivación

El módulo de tareas/presupuestos está en CLAUDE.md sección 3 desde el inicio del proyecto: los departamentos crean peticiones, la administración convierte peticiones en trabajos y aprueba presupuestos de proveedores. El backend tiene modelos `Peticion`, `Trabajo` y `Presupuesto` con routers parciales (peticiones, trabajos), pero **sin router para presupuestos**, **sin integración con `Gasto`** y **sin frontend**. Esta fase cierra el módulo end-to-end.

## Decisiones (cerradas en brainstorming)

1. **Scope completo**: workflow real petición → trabajo → presupuestos → aprobar → completar → genera Gasto.
2. **Migrar `Presupuesto.proveedor`** (string libre) a **FK del `Proveedor`** (entidad de Fase 1).
3. **Generar Gasto al completar trabajo** (no al aprobar presupuesto): botón "Sumar gasto a la caja" en el detalle del trabajo abre el form de Gasto pre-completado.
4. **2 pantallas**: `/peticiones` + `/trabajos` (con presupuestos embebidos en el detalle del trabajo).
5. **Peticiones**: depto crea, admin/representante NO. Todos ven todas (transparencia). Admin/rep editan estado o descripción. Depto borra **solo la suya y solo si está `abierta`**.
6. **Trabajos**: admin/representante los crean (opcionalmente ligados a una petición). Depto sin acceso a `/trabajos`.
7. **Presupuesto**: archivo opcional (PDF/JPG/PNG/WebP, ≤5MB) reusa patrón Comprobante.
8. **Notificaciones email** automáticas al depto cuando su petición cambia de estado (`abierta → en_curso` o `* → cerrada`). Reusa `backend/email.py` (Fase 6a; modo console si SMTP vacío).
9. **Trabajos recurrentes**: plantilla manual estilo `GastoHabitual` — admin las define en una pantalla aparte y materializa con un click cuando toca.
10. **Sin IA, sin portal de proveedores, sin scheduling automático** en esta fase.

## Modelos

### Cambios a modelos existentes

`Peticion` (sin cambios al esquema; sigue con id, departamento_id, titulo, descripcion, estado, fecha_creacion).

`Trabajo` — sumar 2 FKs nuevos:
```python
presupuesto_aprobado_id: Mapped[int | None] = mapped_column(ForeignKey("presupuestos.id"))
gasto_id: Mapped[int | None] = mapped_column(ForeignKey("gastos.id"))
```

`Presupuesto` — cambiar tipo del campo proveedor (breaking) + sumar campos:
```python
# antes:  proveedor: Mapped[str]
# ahora:
proveedor_id: Mapped[int] = mapped_column(
    ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False, index=True
)
archivo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
observaciones: Mapped[str | None] = mapped_column(String(1000), nullable=True)
```

### Modelo nuevo: `TrabajoRecurrente`

```python
class TrabajoRecurrente(Base):
    __tablename__ = "trabajos_recurrentes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(2000), nullable=False)
    periodicidad: Mapped[PeriodicidadRecurrente] = mapped_column(...)  # mensual / trimestral / semestral / anual
    proveedor_sugerido_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"))
    monto_estimado: Mapped[float | None] = mapped_column(Float)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = ...
```

Enum nuevo:
```python
class PeriodicidadRecurrente(str, enum.Enum):
    mensual = "mensual"
    trimestral = "trimestral"
    semestral = "semestral"
    anual = "anual"
```

## Estados

`EstadoPeticion`: `abierta` (default) | `en_curso` | `cerrada`
`EstadoTrabajo`: `en_curso` (default) | `completado` | `cancelado`
`EstadoPresupuesto`: `presentado` (default) | `aprobado` | `rechazado`

## Reglas operativas

- **Solo 1 presupuesto aprobado por trabajo**: aprobar uno rechaza automáticamente los demás del mismo trabajo.
- **No se puede completar un Trabajo sin presupuesto aprobado** → 409.
- **Completar trabajo es atómico**: al crear el Gasto via `POST /gastos` con `trabajo_id` en el body, el backend actualiza `Trabajo.gasto_id` + `Trabajo.estado=completado` en la misma transacción.
- **Petición se cierra automáticamente** cuando el Trabajo asociado se completa o cancela.
- **DELETE Petición por depto**: solo si es del propio depto AND `estado == abierta` (sin trabajo asociado). Sino 409 / 403.
- **DELETE Presupuesto**: solo si `estado == presentado` (no si fue aprobado ni rechazado).
- **PATCH Presupuesto**: solo si `estado == presentado`.
- **Notificación email**: trigger en cambio de estado `abierta → en_curso` y `* → cerrada` de Peticion. Asunto: "Tu petición #X fue actualizada". Cuerpo simple con estado nuevo. Si SMTP_HOST vacío → modo console.
- **Bloqueo cross-recurso**: el Gasto generado al completar trabajo hereda el bloqueo de Fase 4 (si el período está cerrado → 409 al crear el Gasto). El trabajo queda `en_curso` hasta que se libere.

## Endpoints

### Existentes a adaptar

`POST /peticiones` — antes admin+depto; ahora **solo depto** (admin → 403).
`PATCH /peticiones/{peticion_id}` — solo admin/representante.
`DELETE /peticiones/{peticion_id}` (nuevo verbo):
- admin/representante: cualquiera.
- depto: solo la suya y solo si `estado == abierta`; sino 403/409.
`GET /peticiones` — todos los roles ven todas.

### Nuevos: presupuestos

```
GET    /trabajos/{trabajo_id}/presupuestos               → list[PresupuestoOut]
POST   /trabajos/{trabajo_id}/presupuestos               → multipart (admin/rep)
PATCH  /trabajos/{trabajo_id}/presupuestos/{ppto_id}     → admin/rep, solo si presentado
DELETE /trabajos/{trabajo_id}/presupuestos/{ppto_id}     → admin/rep, solo si presentado
POST   /trabajos/{trabajo_id}/presupuestos/{ppto_id}/aprobar   → admin/rep
POST   /trabajos/{trabajo_id}/presupuestos/{ppto_id}/rechazar  → admin/rep
GET    /trabajos/{trabajo_id}/presupuestos/{ppto_id}/archivo   → admin/rep/depto (lectura archivo adjunto)
```

### Nuevos: trabajos

```
GET    /trabajos                                         → admin/representante
GET    /trabajos/{trabajo_id}                            → con presupuestos embebidos
POST   /trabajos/{trabajo_id}/completar                  → devuelve payload pre-completado para el form de Gasto
POST   /trabajos/{trabajo_id}/cancelar                   → cancela sin gasto
```

`POST /trabajos/{trabajo_id}/completar` **no crea el Gasto**. Devuelve `{ proveedor_id, monto, concepto_sugerido, trabajo_id }`. El frontend abre el modal de Gasto pre-completado. Cuando se confirma `POST /gastos` con `trabajo_id`, el backend persiste atómicamente Trabajo.gasto_id + Trabajo.estado=completado.

### Nuevos: trabajos recurrentes

```
GET    /trabajos-recurrentes                             → list (admin)
POST   /trabajos-recurrentes                             → crear plantilla
PATCH  /trabajos-recurrentes/{recurrente_id}             → editar
DELETE /trabajos-recurrentes/{recurrente_id}             → eliminar (sin trabajos materializados activos)
POST   /trabajos-recurrentes/{recurrente_id}/materializar → crea un Trabajo concreto desde la plantilla
```

### Modificación a `POST /gastos`

El payload `GastoCrear` acepta opcionalmente `trabajo_id: int | None`. Si viene, el backend:
1. Crea el Gasto como siempre (lógica de Fase 5: MovimientoCaja egreso, etc.).
2. Setea `Trabajo.gasto_id = gasto.id` y `Trabajo.estado = completado`.
3. Si el Trabajo tiene `peticion_id`, cierra la petición.
4. Manda email de notificación al depto de la petición.

Todo en la misma transacción.

## Frontend

### Sidebar — sección nueva "Tareas y presupuestos"

Entre "Comunicación" y "Expensas y pagos":
```
📋 Peticiones                (admin/representante/depto)
🔧 Trabajos                  (admin/representante)
🔁 Trabajos recurrentes      (admin/representante)
```

### Pantalla `/peticiones` (todos los roles)

- Tabla: depto, título, descripción (truncada), estado (badge), fecha.
- Filtros: estado, depto (admin/rep), "solo las mías" (depto).
- **Botón "+ Nueva petición" SOLO para depto**. Admin/rep no lo ven.
- Click en fila → `ModalDetallePeticion`:
  - Admin/rep: ver datos + botones **"Convertir en trabajo"** + **"Cerrar petición"** + **"Editar descripción"**.
  - Depto si es suya y `abierta`: botón **"Eliminar"** con confirmación.
  - Depto si no cumple: solo lectura.

### Pantalla `/trabajos` (admin/representante)

- Tabla: id, descripción truncada, petición (link "#X" si tiene), estado, cant. presupuestos, monto aprobado, gasto (link si está completado).
- Filtros: estado, con/sin aprobado.
- **Botón "+ Nuevo trabajo"** — dropdown opcional de petición + descripción.
- Click en fila → `ModalDetalleTrabajo` (el más grande):
  - **Tab Info**: descripción editable, estado, fecha, link a petición.
  - **Tab Presupuestos** (embebido):
    - Tabla: proveedor (razon_social), monto, fecha presentación, archivo (link "Ver" si hay), observaciones, estado, acciones.
    - Botón **"+ Sumar presupuesto"** → `ModalNuevoPresupuesto`.
    - Por presupuesto `presentado`: botones **"Aprobar"** / **"Rechazar"** / **"Eliminar"**.
    - El aprobado se destaca (badge verde + fila resaltada).
    - Si ya hay aprobado y aprobás otro, confirm "¿Reemplazar el actual?".
  - **Tab Acciones**:
    - Si `en_curso` con aprobado → **"Sumar gasto a la caja"** abre `ModalNuevoGasto` pre-completado.
    - Si `en_curso` sin aprobado → **"Cancelar trabajo"**.
    - Si `completado` → link al Gasto + dato del MovimientoCaja generado.

### Pantalla `/trabajos/recurrentes` (admin/representante)

CRUD simple estilo `/gastos-habituales`:
- Tabla: nombre, descripción, periodicidad (badge), proveedor sugerido, monto estimado, activa.
- Botón **"+ Nueva plantilla"** → modal con campos.
- Por fila: botón **"Materializar ahora"** → crea un Trabajo desde la plantilla con estado `en_curso`, abre el detalle del nuevo trabajo.

### Componentes nuevos

- `frontend/src/components/ModalDetallePeticion.jsx`
- `frontend/src/components/ModalDetalleTrabajo.jsx` (más grande — tabs/secciones)
- `frontend/src/components/ModalNuevoPresupuesto.jsx` (con input file)
- `frontend/src/components/ModalNuevoTrabajoRecurrente.jsx`
- `frontend/src/components/Campanita.jsx` (badge + dropdown de notificaciones; va en AppLayout)

### Campanita de notificaciones

Componente `Campanita.jsx` montado en el header de `AppLayout` (al lado del email/logout del usuario, visible para todos los roles):

- **Badge rojo** con el count de no leídas (oculto si 0).
- **Polling**: useEffect con setInterval cada 60s que llama a `GET /notificaciones/no-leidas-count`. Si el count cambió → recarga la lista (`GET /notificaciones`).
- **Click en la campanita** → toggle de un dropdown que muestra las últimas 10 notificaciones (mensaje + fecha relativa "hace 5 min").
- **Click en una notificación** → llama a `POST /marcar-leida` + navega con `useNavigate(link)`.
- **Botón "Marcar todas como leídas"** al fondo del dropdown.
- Si SMTP está en modo console, igual aparecen en la campanita — son canales independientes.

### API clients

- `frontend/src/api/peticiones.js` (revisar/extender existente si está, o crear)
- `frontend/src/api/trabajos.js` (idem)
- `frontend/src/api/presupuestos.js` (nuevo)
- `frontend/src/api/trabajosRecurrentes.js` (nuevo)
- `frontend/src/api/notificaciones.js` (nuevo)

## Notificaciones (email + in-app con campanita)

**Modelo nuevo `Notificacion`:**
```python
class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mensaje: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[str | None] = mapped_column(String(200))  # ej. "/peticiones"
    leida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

**Endpoints nuevos `/notificaciones`:**
```
GET    /notificaciones                       → últimas 50 del usuario actual
GET    /notificaciones/no-leidas-count       → { count: int } — request liviano para polling
POST   /notificaciones/{id}/marcar-leida     → marca una
POST   /notificaciones/marcar-todas-leidas   → marca todas las del usuario
```

Acceso: cada usuario solo ve/marca SUS notificaciones (filtro por `usuario_id == current_user.id`). Admin no tiene vista global.

**Módulo `backend/notificaciones.py`:**
```python
def crear_notificacion(db: Session, usuario_id: int, mensaje: str, link: str | None = None) -> None:
    """Crea una Notificacion en la DB. Helper reusable para cualquier evento."""
    db.add(Notificacion(usuario_id=usuario_id, mensaje=mensaje, link=link))


def notificar_cambio_estado_peticion(db: Session, peticion: Peticion, estado_anterior: EstadoPeticion) -> None:
    """Doble canal: in-app (Notificacion en DB) + email. Best-effort en el email."""
    if estado_anterior == peticion.estado:
        return
    if peticion.estado not in (EstadoPeticion.en_curso, EstadoPeticion.cerrada):
        return

    usuarios = list(db.scalars(
        select(Usuario).where(
            Usuario.departamento_id == peticion.departamento_id,
            Usuario.rol == Rol.departamento,
        )
    ).all())
    mensaje = f"Tu petición '{peticion.titulo}' cambió de estado a: {peticion.estado.value}."

    for u in usuarios:
        # In-app
        crear_notificacion(db, usuario_id=u.id, mensaje=mensaje, link="/peticiones")
        # Email best-effort
        if u.email:
            enviar_email(
                to=u.email,
                subject=f"Tu petición #{peticion.id} fue actualizada",
                body=f"Hola,\n\n{mensaje}\n\nSaludos,\nAdministración.",
                attachments=[],
            )
```

Se invoca desde los endpoints que cambian estado de petición:
- `PATCH /peticiones/{id}` cuando cambia el estado.
- `POST /trabajos/{id}/completar` (cierra petición asociada).
- `POST /trabajos/{id}/cancelar` (cierra petición asociada).
- `POST /trabajos` cuando se crea con peticion_id (abre → en_curso).

En modo SMTP_HOST vacío, los emails se loggean al stdout (igual que Fase 6a). Si el envío falla, NO bloquea el flujo (los emails son best-effort).

## Tests

### Backend (~25 tests nuevos + adaptaciones)

- `tests/test_peticiones.py` (adaptar):
  - `POST como admin → 403` (nuevo: solo depto).
  - `DELETE depto su propia abierta → 204`.
  - `DELETE depto su propia en_curso → 409`.
  - `DELETE depto ajena → 403`.
  - `GET como depto devuelve todas` (no solo las suyas).
  - `PATCH como depto → 403`.

- `tests/test_trabajos.py` (adaptar):
  - `POST /trabajos/{id}/completar sin presupuesto aprobado → 409`.
  - `POST /trabajos/{id}/completar con aprobado → devuelve payload`.
  - `POST /trabajos/{id}/cancelar marca cancelado + cierra petición si la había`.
  - Adaptar tests existentes al nuevo schema de presupuesto.

- `tests/test_presupuestos.py` (nuevo, ~10 tests):
  - GET listar, POST crear con file, POST sin file, monto<=0 → 400.
  - Aprobar un segundo → desaprueba el primero.
  - PATCH solo presentado, DELETE solo presentado.
  - GET archivo devuelve bytes con tipo correcto.

- `tests/test_trabajos_recurrentes.py` (nuevo, ~6 tests):
  - CRUD admin (POST/PATCH/DELETE/GET).
  - `POST /materializar` crea Trabajo con datos de la plantilla.

- `tests/test_notificaciones.py` (nuevo, ~6 tests):
  - Cambio `abierta → en_curso` crea Notificacion en DB + dispara email (modo console).
  - Cambio `* → cerrada` idem.
  - PATCH solo descripción NO dispara nada.
  - GET /notificaciones devuelve solo las del usuario actual.
  - POST /marcar-leida solo afecta a la propia.
  - GET /no-leidas-count devuelve número correcto.

- `tests/test_gastos.py` (sumar):
  - Crear Gasto con `trabajo_id` → trabajo queda `completado` con `gasto_id` apuntando.

### Sin tests E2E del frontend
Smoke manual al cierre.

## Migración

Clean start (patrón histórico): borrar `consorcio.db` y re-seed.

**Seed actualizado:**
- Sumar 1-2 trabajos recurrentes de ejemplo ("Limpieza tanque trimestral", "Mantenimiento ascensores mensual").
- Los presupuestos demo del seed Fase 3 (si los hay) ahora usan `proveedor_id` en vez de string.

## Out-of-scope explícito

- ❌ AI para sugerir precios de presupuestos.
- ❌ Portal de proveedores (login + carga propia).
- ❌ Integración email/WhatsApp para solicitar presupuestos a proveedores.
- ❌ Scheduling automático de materialización de recurrentes (admin click manual).
- ❌ Histórico/audit log por trabajo.
- ❌ Comparativo gráfico de presupuestos.
- ❌ Adjuntar múltiples archivos al presupuesto (1 sólo).
- ❌ WebSocket para notificaciones en tiempo real (polling 60s alcanza).
- ❌ Notificaciones push del browser (HTML5 Notification API) — solo in-app + email.
- ❌ Reportes específicos de tareas (ranking proveedores por trabajos completados, etc.).

## Estimación

- ~16-18 tasks:
  - Modelos + migración (1)
  - Schemas + módulo notificaciones (con Notificacion model + helper) (1)
  - Router presupuestos + tests (1)
  - Router notificaciones + tests (1)
  - Adaptar peticiones (cambio de auth + delete + integración con notificaciones + tests) (1)
  - Adaptar trabajos (completar/cancelar + tests) (1)
  - Router trabajos-recurrentes + tests (1)
  - Integración POST /gastos con trabajo_id + tests (1)
  - OpenAPI (1)
  - Seed (1)
  - Frontend API clients (1)
  - Frontend pantalla peticiones + ModalDetallePeticion (1)
  - Frontend pantalla trabajos + ModalDetalleTrabajo + ModalNuevoPresupuesto (1)
  - Frontend pantalla trabajos-recurrentes (1)
  - Frontend Campanita + integración en AppLayout (1)
  - Sidebar + Routes (1)
  - Smoke + merge + roadmap (1)

- Tiempo total estimado: **2.5-3 semanas**.

## Historial

- 2026-06-26: brainstorming + spec inicial post-merge Fase 6b. Decisiones clave: scope completo end-to-end con integración a Gasto, presupuesto con archivo adjunto, notificaciones doble canal (in-app campanita con polling 60s + email best-effort), trabajos recurrentes con materialización manual.

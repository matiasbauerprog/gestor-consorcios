# Módulo de Expensas y Comprobantes — diseño

Fecha: 2026-06-11
Estado: aprobado por el usuario, pendiente de plan de implementación.

## Objetivo

Implementar el segundo módulo funcional del frontend del Sistema Integral de Gestión de Consorcios: **Expensas y Comprobantes**. El módulo cubre el flujo completo entre Administración y los Departamentos:

1. Administración carga expensas mensuales por departamento.
2. El Departamento ve sus expensas pendientes y presenta un comprobante de pago.
3. Administración revisa los comprobantes presentados y los aprueba o rechaza.
4. Una aprobación cierra el ciclo: la expensa pasa a "Confirmada".

Roles que ven el módulo: **Administración** y **Departamento**. Representante no participa de este flujo y no ve los links en el sidebar.

Como precondición, esta tarea agrega dos cambios al backend (sin los cuales el dashboard no se puede renderizar) y suma componentes al frontend.

## Reglas del proyecto aplicables

- `business-rules.md`: Administración crea expensas y ve el historial general; Departamentos presentan comprobantes y ven solo su propio historial.
- `frontend.md`: HTML semántico, paleta vía variables CSS, estado en hooks, gating por rol en UI, **mobile-first** como default.
- `backend.md`: routers en `backend/routers/`, modelos en `backend/models.py`, schemas en `backend/schemas.py`, tests por router.
- `openapi-first.md`: cualquier endpoint nuevo se documenta primero en `openapi.yaml`.
- `security.md`: identidad y rol salen del JWT, nunca del body; representante recibe 403 al intentar acceder.

## Decisiones de diseño

| Decisión | Elegida | Alternativas descartadas | Razón |
|---|---|---|---|
| Estructura de navegación | 2 links en sidebar: "Expensas" y "Comprobantes" (ambos para admin + depto) | Un solo link con tabs internos; todo embebido | Un módulo = un link, coherente con la convención. Fácil de extender. |
| Layout del dashboard `/expensas` | Sólo sección de expensas (sin sección separada de comprobantes) | Dashboard con dos secciones (expensas + últimos comprobantes) | Más simple. La info del comprobante asociado a cada expensa ya aparece en la tarjeta. |
| Cómo carga Admin las expensas | Una por una (modal) | Lote (grilla con un monto por depto); CSV/Excel | Backend ya lo soporta sin cambios. Suficiente para esta iteración. |
| Listar comprobantes | Nuevo `GET /comprobantes` con filtros | Embeber en `ExpensaOut`; endpoint anidado por expensa | Más flexible y desacopla el listado de la jerarquía. |
| Mostrar estado del comprobante en cada expensa | `ExpensaOut.ultimo_comprobante: ComprobanteOut \| None` | Lista completa de comprobantes; N+1 requests | Una sola request carga todo el dashboard. Suficiente porque la UI sólo muestra uno. |
| Acción "Confirmar" (Admin) en dashboard | Botón oculto si no hay comprobante; leyenda visible siempre que aclara estado | Botón siempre visible con modal explicativo; permitir confirmar sin comprobante | Alineado con el backend actual; preserva auditoría vía comprobantes. |
| "Confirmar" abre modal con Aprobar/Rechazar | Modal muestra detalle del comprobante + ambos botones | Aprobación directa sin modal | Acción reversible sólo desde modal evita misclicks; ambas opciones disponibles desde un único entry point. |
| Acciones en `/comprobantes` | Botones inline directos `[Aprobar]` / `[Rechazar]` | Modal de confirmación | El usuario está en modo "triage", no quiere fricción en cada decisión. |
| `archivo_url` del comprobante | Input de texto (URL externa: Drive, foto, etc.) | File upload | El backend sólo guarda URL. File upload requiere storage, MIME validation, otro feature. |
| Selector de depto en Admin/`/expensas` | Mandatorio antes de mostrar expensas (default vacío → "Elegí un departamento") | Selector con primer depto autoseleccionado | Evita renderizar lista enorme; obliga a una intención explícita. |
| Vencida visualmente | Computada client-side (`fecha_vencimiento < hoy && estado === pendiente`) | Esperar que el backend lo setee | El backend tiene el estado pero no lo setea automáticamente. La UI lo deriva. |

## Cambios en el backend (precondición)

Cuatro cambios independientes. Se hacen **antes** del frontend (sin ellos, el dashboard no puede renderizar).

### Cambio 1: nuevo `GET /comprobantes`

1. **OpenAPI primero**. Documentar en `openapi.yaml`:
   - Path: `/comprobantes` con `get`. Tag: `Expensas`.
   - Query params: `estado` (enum opcional), `departamento_id` (int opcional), `limit` (int default 50, ge 1, le 200), `offset` (int default 0, ge 0).
   - Response 200: `array[ComprobanteOut]`. 401, 403 standard.

2. **Router** (`backend/routers/comprobantes.py`):
   ```python
   @router.get(
       "",
       response_model=list[ComprobanteOut],
       status_code=status.HTTP_200_OK,
       summary="Listar comprobantes",
   )
   def listar_comprobantes(
       estado: EstadoComprobante | None = Query(default=None),
       departamento_id: int | None = Query(default=None, gt=0),
       limit: int = Query(default=50, ge=1, le=200),
       offset: int = Query(default=0, ge=0),
       db: Session = Depends(get_db),
       user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.departamento)),
   ) -> list[Comprobante]:
       # Join con Expensa para poder filtrar/aislar por departamento.
       stmt = (
           select(Comprobante)
           .join(Expensa, Comprobante.expensa_id == Expensa.id)
           .order_by(Comprobante.fecha_creacion.desc(), Comprobante.id.desc())
       )

       # Aislamiento por unidad: el Departamento solo ve los comprobantes de sus expensas.
       # departamento_id viene del token, nunca del query, para usuarios depto.
       if user.rol == Rol.departamento:
           stmt = stmt.where(Expensa.departamento_id == user.departamento_id)
       elif departamento_id is not None:
           stmt = stmt.where(Expensa.departamento_id == departamento_id)

       if estado is not None:
           stmt = stmt.where(Comprobante.estado == estado)

       stmt = stmt.offset(offset).limit(limit)
       return list(db.scalars(stmt).all())
   ```

3. **Tests** (`tests/test_comprobantes.py`):
   - Happy path admin lista todo.
   - Happy path admin filtra por `estado`.
   - Happy path admin filtra por `departamento_id`.
   - Happy path depto solo ve los suyos.
   - Depto NO puede usar `departamento_id` para ver de otra unidad (server-side se ignora).
   - Representante recibe 403.
   - Sin token → 401.

### Cambio 2: `ExpensaOut.ultimo_comprobante`

1. **OpenAPI**: actualizar el componente `Expensa` (es el que mapea a `ExpensaOut` en código) para incluir `ultimo_comprobante` opcional con shape de `Comprobante`.

2. **Schema Pydantic** (`backend/schemas.py`):
   ```python
   class ExpensaOut(BaseModel):
       model_config = ConfigDict(from_attributes=True)

       id: int
       departamento_id: int
       periodo: str
       monto: float
       estado: EstadoExpensa
       fecha_vencimiento: date
       ultimo_comprobante: ComprobanteOut | None = None
   ```

3. **Modelo SQLAlchemy** (`backend/models.py`): agregar `relationship` desde `Expensa` a `Comprobante`:
   ```python
   class Expensa(Base):
       # ... campos existentes ...
       comprobantes: Mapped[list["Comprobante"]] = relationship(
           back_populates="expensa",
           order_by="Comprobante.fecha_creacion.desc()",
           lazy="selectin",
       )

   class Comprobante(Base):
       # ... campos existentes ...
       expensa: Mapped["Expensa"] = relationship(back_populates="comprobantes")
   ```

4. **Router** (`backend/routers/expensas.py`): después de cargar las expensas, popular el campo en una capa de mapeo:
   ```python
   def _to_out(expensa: Expensa) -> dict:
       return {
           "id": expensa.id,
           "departamento_id": expensa.departamento_id,
           "periodo": expensa.periodo,
           "monto": expensa.monto,
           "estado": expensa.estado,
           "fecha_vencimiento": expensa.fecha_vencimiento,
           "ultimo_comprobante": expensa.comprobantes[0] if expensa.comprobantes else None,
       }
   ```
   `listar_expensas` y `obtener_expensa` devuelven `[_to_out(e) for e in ...]` / `_to_out(expensa)`. Como `ExpensaOut` tiene `from_attributes=True`, también funciona pasar la entidad y dejar que Pydantic lea `expensa.comprobantes[0]` vía property — alternativa equivalente.

5. **Tests** (`tests/test_expensas.py`): tests nuevos para verificar:
   - `ultimo_comprobante` es `None` cuando no hay comprobantes.
   - `ultimo_comprobante` es el más reciente (por `fecha_creacion desc, id desc`) cuando hay varios.
   - Sigue funcionando todo lo previo (lista, filtros, crear, presentar, detalle).

### Cambio 3: `GET /expensas` acepta `departamento_id`

1. **OpenAPI**: sumar a la operación `listarExpensas` el query param `departamento_id: integer (opcional, gt 0)`.
2. **Router** (`backend/routers/expensas.py`): agregar el param y aplicarlo al `stmt`:
   ```python
   departamento_id: int | None = Query(default=None, gt=0),
   # ...
   # Si Admin pasa departamento_id, filtra por ese depto.
   # Si el usuario es Departamento, el filtro existente (por su token) prevalece y este param se ignora.
   if user.rol != Rol.departamento and departamento_id is not None:
       stmt = stmt.where(Expensa.departamento_id == departamento_id)
   ```
3. **Tests:** Admin pasa `departamento_id` y obtiene solo expensas de ese depto. Depto pasa `departamento_id` ajeno y sigue viendo sólo las suyas (server-side ignora el query).

### Cambio 4: `ComprobanteOut.expensa` (resumen)

Para que la tarjeta de `/comprobantes` muestre contexto del depto y periodo sin N+1 requests.

1. **OpenAPI**: extender el componente `Comprobante` con un campo opcional `expensa: { departamento_id, periodo, monto }`.
2. **Schema Pydantic** (`backend/schemas.py`):
   ```python
   class ExpensaResumen(BaseModel):
       model_config = ConfigDict(from_attributes=True)
       departamento_id: int
       periodo: str
       monto: float

   class ComprobanteOut(BaseModel):
       model_config = ConfigDict(from_attributes=True)
       id: int
       expensa_id: int
       fecha_pago: date
       monto: float
       archivo_url: str | None
       estado: EstadoComprobante
       expensa: ExpensaResumen | None = None
   ```
3. **Router**: la `relationship` `Comprobante.expensa` ya quedó configurada en el Cambio 2; Pydantic lo lee directamente.
4. **Tests**: el `GET /comprobantes` y el `POST /expensas/{id}/comprobantes` devuelven `expensa` populated.

## Frontend

### Sidebar

`Sidebar.jsx` agrega dos `MODULOS` nuevos con `rolesPermitidos: ["administracion", "departamento"]`:

```js
{ ruta: "/expensas", nombre: "Expensas", rolesPermitidos: ["administracion", "departamento"] },
{ ruta: "/comprobantes", nombre: "Comprobantes", rolesPermitidos: ["administracion", "departamento"] },
```

Representante no ve ninguno (consistente con el backend).

### Routes (`App.jsx`)

Sumar bajo el `<Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>`:
```jsx
<Route path="expensas" element={<Expensas />} />
<Route path="comprobantes" element={<Comprobantes />} />
```

### Estructura de archivos nueva

```
frontend/src/
  api/
    departamentos.js     ← nuevo: listarDepartamentos()
    expensas.js          ← nuevo: listarExpensas, crearExpensa, obtenerExpensa, presentarComprobante
    comprobantes.js      ← nuevo: listarComprobantes, actualizarComprobante
  components/
    BadgeEstado.jsx      ← nuevo: badge visual ("Pendiente", "Confirmada", "Vencida", "Pend. verif.", etc.)
    SelectorDepartamento.jsx  ← nuevo: select gateado a Admin (carga con listarDepartamentos)
  screens/
    Expensas.jsx         ← nueva pantalla
    Comprobantes.jsx     ← nueva pantalla
```

Reusa `Modal`, `Tarjeta`, `RequireAuth` y demás del módulo Comunicación. No se crean componentes nuevos para los modales — cada modal se define inline dentro de la pantalla que lo abre (igual que `FormularioNuevoComunicado` en `Comunicados.jsx`).

### Pantalla `/expensas` (dashboard)

Componente `screens/Expensas.jsx`.

**Estado:**

| Variable | Tipo | Uso |
|---|---|---|
| `expensas` | `ExpensaOut[]` | lista cargada del backend |
| `cargando` | `boolean` | spinner durante el GET inicial |
| `errorCarga` | `string \| null` | error del GET |
| `departamentoSeleccionado` | `number \| null` | sólo para Admin; null = "Elegí un departamento" |
| `modalCrear` | `boolean` | abierto/cerrado |
| `modalPresentar` | `Expensa \| null` | expensa para la cual el depto presenta comprobante |
| `modalConfirmar` | `{ expensa, comprobante } \| null` | datos del comprobante pendiente que Admin va a aprobar/rechazar |
| `modalVer` | `ComprobanteOut \| null` | comprobante en modo lectura |
| `errorAccion` | `string \| null` | error global de mutaciones (crear / aprobar / rechazar / presentar) |

**Ciclo de vida:**

- `useEffect` al montar: si Admin → no dispara nada hasta elegir depto. Si Depto → `listarExpensas()` (el backend filtra por su depto vía token).
- `useEffect` con dependencia `departamentoSeleccionado` (sólo Admin): cuando cambia, `listarExpensas({ departamento_id })`.
  - **El query param `departamento_id` no existe** en el backend de expensas hoy. Hay que sumarlo. (Ver "Otros cambios menores" más abajo.)

**Render (esqueleto):**

```jsx
<section>
  <header className="seccion-header">
    <h2>Expensas</h2>
    {user.rol === "administracion" && (
      <>
        <SelectorDepartamento
          valor={departamentoSeleccionado}
          onChange={setDepartamentoSeleccionado}
        />
        <button
          type="button"
          disabled={departamentoSeleccionado === null}
          onClick={() => setModalCrear(true)}
        >
          + Nueva expensa
        </button>
      </>
    )}
  </header>

  {user.rol === "administracion" && departamentoSeleccionado === null && (
    <p>Elegí un departamento para ver sus expensas.</p>
  )}

  {cargando && <p>Cargando…</p>}
  {errorCarga && <p role="alert" className="error-banner">{errorCarga}</p>}
  {errorAccion && <p role="alert" className="error-banner">{errorAccion}</p>}

  <ul className="lista-expensas">
    {expensas.map(e => (
      <li key={e.id}>
        <TarjetaExpensa
          expensa={e}
          rol={user.rol}
          onPresentar={() => setModalPresentar(e)}
          onConfirmar={() => setModalConfirmar({ expensa: e, comprobante: e.ultimo_comprobante })}
          onVer={() => setModalVer(e.ultimo_comprobante)}
        />
      </li>
    ))}
  </ul>

  <p>
    <Link to="/comprobantes">Ver todos los comprobantes →</Link>
  </p>

  {modalCrear && <ModalNuevaExpensa ... />}
  {modalPresentar && <ModalPresentarComprobante ... />}
  {modalConfirmar && <ModalConfirmarComprobante ... />}
  {modalVer && <ModalVerComprobante ... />}
</section>
```

### Tarjeta de expensa: leyenda + botón según estado y rol

La lógica de qué leyenda y qué botón mostrar se calcula del lado cliente a partir de `expensa.estado` y `expensa.ultimo_comprobante`. Tabla canónica:

| Estado expensa | Último comprobante | Leyenda | Botón Depto | Botón Admin |
|---|---|---|---|---|
| `pendiente` | `None` | "Aún no presentó comprobante" | "Presentar comprobante" | (ninguno) |
| `pendiente` | `pendiente_verificacion` | "Comprobante pendiente de verificación" | (ninguno) | "Confirmar" |
| `pendiente` | `rechazado` | "Último comprobante rechazado" | "Presentar otro comprobante" | (ninguno) |
| `pagada` | cualquiera | (sin leyenda extra, "Confirmada" en el badge) | "Ver comprobante" | "Ver comprobante" |

Cuando `expensa.estado === "pendiente"` y `fecha_vencimiento < hoy`, el `<BadgeEstado>` muestra "Vencida" (rojo) en vez de "Pendiente" (gris). La leyenda se mantiene.

### Modal "+ Nueva expensa" (Admin)

- Campos: `departamento_id` (preseleccionado al del selector — lectura solamente; muestra el código), `periodo` (input texto con regex `YYYY-MM` y placeholder), `monto` (number, > 0), `fecha_vencimiento` (date).
- Submit: `crearExpensa({ departamento_id, periodo, monto, fecha_vencimiento })`.
  - `201` → prepend a la lista local y cerrar.
  - `400` → mostrar `detail`.
  - `404` → "El departamento indicado no existe." (defensa en profundidad).
  - `409` → "Ya existe una expensa para ese departamento en ese período."
  - otro → genérico.

### Modal "Presentar comprobante" (Depto)

- Campos: `fecha_pago` (date), `monto` (number, > 0), `archivo_url` (input texto opcional, max 2048).
- Submit: `presentarComprobante(expensa.id, { fecha_pago, monto, archivo_url })`.
  - `201` → actualiza `expensas` (reemplaza la expensa por su versión con el nuevo `ultimo_comprobante`) y cierra.
  - `400` → mostrar `detail`.
  - `403` → "No tenés permisos para presentar este comprobante." (defensa en profundidad).
  - `404` → "La expensa solicitada no existe."
  - otro → genérico.

### Modal "Confirmar" (Admin)

- Muestra detalle del comprobante pendiente: `fecha_pago`, `monto`, link al `archivo_url` (si existe).
- Botones: `[Aprobar]` y `[Rechazar]`.
- Aprobar: `actualizarComprobante(id, { estado: "aprobado" })`.
  - `200` → actualiza la expensa local (estado pagada, ultimo_comprobante aprobado) y cierra. La tarjeta pasa a "Confirmada" + "Ver comprobante".
- Rechazar: `actualizarComprobante(id, { estado: "rechazado" })`.
  - `200` → actualiza la expensa local (estado sigue pendiente, ultimo_comprobante rechazado) y cierra. La tarjeta pasa a "Último comprobante rechazado" + "Presentar otro comprobante" para el depto (la admin sigue sin botón).
- `409` → "El comprobante ya fue verificado y no puede modificarse." (race condition).
- otro → genérico.

### Modal "Ver comprobante" (ambos roles, modo lectura)

- Muestra `fecha_pago`, `monto`, `archivo_url` (como link), `estado`.
- Sin acciones. Botón "Cerrar".

### Pantalla `/comprobantes`

Componente `screens/Comprobantes.jsx`.

**Estado:**

| Variable | Tipo | Uso |
|---|---|---|
| `comprobantes` | `ComprobanteOut[]` | lista del backend |
| `cargando` | `boolean` | spinner |
| `errorCarga` | `string \| null` | error del GET |
| `filtroEstado` | `EstadoComprobante \| ""` | filtro por estado, vacío = todos |
| `filtroDepartamento` | `number \| null` | solo Admin; null = todos |
| `accionando` | `number \| null` | id del comprobante con request en vuelo (deshabilita botones) |
| `errorAccion` | `string \| null` | error de aprobar/rechazar |

**Ciclo de vida:**

- `useEffect` con dependencias `filtroEstado` y `filtroDepartamento` (este último sólo se considera si Admin): llama `listarComprobantes({ estado, departamento_id })`. El backend ignora `departamento_id` cuando viene del depto (server-side).

**Render (esqueleto):**

```jsx
<section>
  <header className="seccion-header">
    <h2>Comprobantes</h2>
  </header>

  <div className="filtros">
    <label>
      Estado
      <select value={filtroEstado} onChange={...}>
        <option value="">Todos</option>
        <option value="pendiente_verificacion">Pendientes</option>
        <option value="aprobado">Aprobados</option>
        <option value="rechazado">Rechazados</option>
      </select>
    </label>
    {user.rol === "administracion" && (
      <SelectorDepartamento valor={filtroDepartamento} onChange={setFiltroDepartamento} permitirVacio />
    )}
  </div>

  {cargando && <p>Cargando…</p>}
  {errorCarga && <p role="alert" className="error-banner">{errorCarga}</p>}
  {errorAccion && <p role="alert" className="error-banner">{errorAccion}</p>}
  {!cargando && comprobantes.length === 0 && <p>No hay comprobantes con esos filtros.</p>}

  <ul className="lista-comprobantes">
    {comprobantes.map(c => (
      <li key={c.id}>
        <TarjetaComprobante
          comprobante={c}
          rol={user.rol}
          deshabilitado={accionando === c.id}
          onAprobar={() => handleAccion(c.id, "aprobado")}
          onRechazar={() => handleAccion(c.id, "rechazado")}
        />
      </li>
    ))}
  </ul>
</section>
```

`TarjetaComprobante` muestra: fecha_pago, monto, link a archivo_url si hay, BadgeEstado, y para Admin si `estado === pendiente_verificacion` los botones `[Aprobar]` y `[Rechazar]` inline (sin modal — el admin está triando).

`TarjetaComprobante` usa el campo `comprobante.expensa` (resumen poblado por el backend según el Cambio 4) para mostrar el contexto (depto + período) sin requests adicionales.

## Manejo de status codes (frontend)

Sigue `frontend.md`:

| Código | Acción |
|---|---|
| 200 / 201 / 204 | Continuar el flujo (refrescar local, cerrar modal) |
| 400 | Mostrar `detail` del backend en el modal |
| 401 | `apiFetch` dispara logout automático; usuario vuelve a `/login` |
| 403 | "No tenés permisos para esta operación." |
| 404 | "El recurso no existe." (depto, expensa o comprobante según contexto) |
| 409 | Mostrar `detail` del backend (duplicado, comprobante ya verificado) |

## CSS y mobile-first

Todo el módulo respeta la regla `frontend.md` "Responsive / Mobile-first":

- Base targets ≥320px. `@media (min-width: 600px)` para tablet, `@media (min-width: 960px)` para desktop.
- Tarjetas de expensa / comprobante apilan en mobile, pueden ir en grid de 2 col en desktop.
- Filtros en `/comprobantes`: column en mobile, row en tablet.
- Modales: full-screen en mobile, max-width 520px en tablet+.
- Selectores (`<select>`) con altura ≥44px (los inputs base ya cumplen).
- Botones de acción `[Aprobar]` / `[Rechazar]` con min-height 44px.

No se agregan variables CSS nuevas — la paleta de Comunicación cubre todo (`--color-primary`, `--color-danger`, `--color-success`, etc.).

Para el `BadgeEstado`, usamos las variables existentes:
- "Pendiente" → texto gris (`--color-text-muted`), borde 1px gris.
- "Vencida" → texto y borde `--color-danger`.
- "Confirmada" / "Aprobado" → texto y borde `--color-success`.
- "Pendiente de verificación" → texto y borde con un naranja — agregamos UNA variable nueva al `:root`: `--color-warning: #d97706;` y `--color-warning-bg: #fef3c7;`.
- "Rechazado" → mismo `--color-danger`.

## Fuera de alcance

- File upload real (storage backend, MIME validation). `archivo_url` queda como input de texto.
- Carga en lote / CSV de expensas. Sólo una por una en esta iteración.
- Edición o anulación de una expensa ya creada (backend tampoco la soporta).
- Edición de un comprobante ya presentado (idem).
- Historial completo de comprobantes de una expensa en el dashboard (sólo se muestra el último). El historial se ve en `/comprobantes` filtrando por estado.
- Notificaciones push o por email.
- Cálculo automático server-side de "vencida" — se computa client-side.
- Filtros adicionales en `/comprobantes` (por periodo, por monto). Solo estado y depto.

## Dependencias nuevas

- Sin dependencias nuevas. El módulo usa lo que ya está (`react-router-dom`, fetch helper).

# Módulo de Comunicación — diseño

Fecha: 2026-06-09
Estado: aprobado por el usuario, pendiente de plan de implementación.

## Objetivo

Implementar el primer módulo funcional del frontend del Sistema Integral de Gestión de Consorcios: **Comunicación**. Permite a Administración publicar y gestionar comunicados, y a Departamentos / Representantes verlos en modo lectura.

Como precondición, esta tarea agrega:

- La **arquitectura de navegación** de la SPA (sidebar + React Router), que también va a usar el resto de los módulos.
- Los componentes reutilizables base (`Modal`, `Tarjeta`, `AppLayout`, `Sidebar`, `RequireAuth`) que los próximos módulos van a consumir.
- En el backend, la posibilidad de **borrado soft** de comunicados, que hoy no existe (sólo hay `GET` y `POST`).

## Reglas del proyecto aplicables

- `business-rules.md`: Administración crea y gestiona comunicados; Departamentos sólo leen.
- `frontend.md`: HTML semántico, paleta vía variables CSS, estado en hooks, gating por rol en UI.
- `backend.md`: routers en `backend/routers/`, modelos en `backend/models.py`, schemas en `backend/schemas.py`, tests por router.
- `openapi-first.md`: cualquier endpoint nuevo se documenta primero en `openapi.yaml`.
- `security.md`: identidad y rol salen del JWT, nunca del body.

## Decisiones de diseño

| Decisión | Elegida | Alternativas descartadas | Razón |
|---|---|---|---|
| Navegación entre módulos | Sidebar + React Router (`react-router-dom`) | Tabs con estado interno; sidebar con estado interno | URLs reales (`/comunicados`), back/forward del navegador, patrón estándar para SPAs. |
| Layout de creación | Botón "Nuevo comunicado" que abre modal | Form inline siempre visible; ruta separada `/comunicados/nuevo` | La lista queda limpia, el form aparece sólo cuando se necesita. |
| Presentación del cuerpo | Tarjeta con preview + botón "Ver más" inline | Tarjeta + modal de detalle; cuerpo completo siempre | Sin saltos de contexto, suficiente para el caso de uso. |
| Identificación del autor | Etiqueta fija "Administración" | Resolver email vía `GET /usuarios`; no mostrar autor | Sólo Administración crea comunicados; `GET /usuarios` está gateado a admin, así que resolver el nombre real generaría inconsistencia entre roles. |
| Borrado | Soft-delete (`eliminado_at` nullable) | Hard-delete | Queda historial recuperable; el costo extra (columna + migración + filtro) es bajo y consistente con buenas prácticas. |
| Refresco tras crear/borrar | Optimista local | Re-fetch del GET tras cada mutación | El backend ya devuelve el comunicado completo en el `POST`; evitar round-trip extra. |

## Arquitectura del shell

`App.jsx` deja de renderizar el shell directamente. Pasa a definir las rutas con `react-router-dom` y delegar el layout a `AppLayout`.

- **Rutas públicas**: `/login`. Si el usuario ya está autenticado, redirige a `/`.
- **Rutas privadas** (envueltas en `<RequireAuth>`): `/` (redirige a `/comunicados`), `/comunicados`. Una ruta `*` muestra `NotFound`.
- `<RequireAuth>` consulta `useAuth()`; si `!user` redirige a `/login` con `<Navigate replace>`.
- `Login.jsx` agrega `useNavigate()`; tras `login()` exitoso navega a `/comunicados`.

`AppLayout` arma la estructura visual:

```
<div class="app-shell">
  <header>          ← título de la app, email + rol, botón "Cerrar sesión"
  <aside>           ← <Sidebar /> con NavLinks por módulo
  <main>            ← <Outlet /> del router
</div>
```

`Sidebar` recibe `user.rol` y aplica gating por link. Por ahora sólo aparece "Comunicación" (visible para los tres roles). Se preparan los huecos para los próximos módulos pero no se renderizan hasta que existan.

## Estructura de archivos

Archivos nuevos en `frontend/src/`:

```
src/
  components/
    Sidebar.jsx         ← nav lateral con NavLinks (gating por rol)
    AppLayout.jsx       ← header + sidebar + <Outlet />
    RequireAuth.jsx     ← guard de rutas privadas
    Modal.jsx           ← reutilizable (cerrar con X, backdrop y Escape)
    Tarjeta.jsx         ← <article> con estilos consistentes
  screens/
    Login.jsx           ← (existente; sólo se le agrega useNavigate)
    Comunicados.jsx     ← lista + modales de crear y borrar
    NotFound.jsx        ← ruta *
  api/
    client.js           ← (sin cambios)
    comunicados.js      ← listarComunicados(), crearComunicado(), borrarComunicado()
  App.jsx               ← define el router; pasa de Shell propio a AppLayout
```

`api/comunicados.js` envuelve `apiFetch` y devuelve `{ ok, status, data }` directo. Un módulo por recurso evita que `client.js` se infle con cada módulo nuevo.

`Modal` y `Tarjeta` se hacen genéricos desde el inicio porque ya sé que los van a reutilizar Expensas (modal de pago, tarjeta de expensa), Tareas y Reservas. No se inventan más componentes "por si acaso".

## Cambios en el backend (precondición del borrado)

El borrado se hace soft. Hoy el modelo no tiene la columna y no existe endpoint. Cambios necesarios, en orden:

1. **OpenAPI primero**. Documentar `DELETE /comunicados/{comunicado_id}` en `openapi.yaml` bajo la entrada `/comunicados/{comunicado_id}` (path param con nombre completo del recurso, según `openapi-first.md`).
2. **Modelo** (`backend/models.py`). Agregar a `Comunicado`:
   ```python
   eliminado_at: Mapped[datetime | None] = mapped_column(
       DateTime(timezone=True), nullable=True, default=None
   )
   ```
3. **Migración manual**. El proyecto no usa Alembic; el esquema se crea con `Base.metadata.create_all`. Para entornos existentes correr una sola vez:
   ```sql
   ALTER TABLE comunicados ADD COLUMN eliminado_at DATETIME NULL;
   ```
   En entornos de desarrollo sin datos relevantes alcanza con borrar `consorcio.db` y dejar que se recree.
4. **GET `/comunicados`**. Agregar `.where(Comunicado.eliminado_at.is_(None))` al `select`. Los registros marcados nunca se devuelven.
5. **DELETE `/comunicados/{comunicado_id}`** (nuevo en `backend/routers/comunicados.py`):
   - Auth: `require_roles(Rol.administracion)` — devuelve 401/403 automáticamente.
   - `db.get(Comunicado, comunicado_id)`; si `None` o ya tiene `eliminado_at`, devolver `404` con `"El comunicado no existe."`.
   - Marcar `comunicado.eliminado_at = datetime.now(timezone.utc)` y `db.commit()`.
   - Status `204 No Content`, sin body.
6. **Tests** (`tests/test_comunicados.py`). Cubrir: happy path (204), 401 sin token, 403 con rol depto/representante, 404 inexistente, 404 ya borrado, y que el GET no devuelve los marcados.

Esta sección usa la skill `add-endpoint` para mantenerse consistente con las 6 fases del proyecto.

## UI del módulo `/comunicados`

Componente `screens/Comunicados.jsx`.

### Estado

| Variable | Tipo | Uso |
|---|---|---|
| `comunicados` | `ComunicadoOut[]` | lista cargada del backend |
| `cargando` | `boolean` | spinner/texto durante el primer GET |
| `errorCarga` | `string \| null` | error del GET |
| `modalCrear` | `boolean` | abierto/cerrado |
| `modalBorrar` | `{ id, titulo } \| null` | comunicado en confirmación de borrado |
| `idBorrando` | `number \| null` | deshabilita el botón "Borrar" durante el DELETE |
| `errorBorrado` | `string \| null` | error global del DELETE, mostrado arriba de la lista |
| `expandidos` | `Set<number>` | ids de tarjetas con "ver más" abierto |

### Ciclo de vida

- `useEffect` al montar → `listarComunicados()`.
  - `200` → `setComunicados(data)`.
  - `401` → `apiFetch` ya dispara logout automático; no se hace nada extra.
  - otro → `setErrorCarga("No se pudieron cargar los comunicados.")`.

### Render (esqueleto)

```jsx
<main>
  <header>
    <h2>Comunicados</h2>
    {user.rol === "administracion" && (
      <button onClick={() => setModalCrear(true)}>+ Nuevo comunicado</button>
    )}
  </header>

  {errorBorrado && <p role="alert">{errorBorrado}</p>}
  {cargando && <p>Cargando…</p>}
  {errorCarga && <p role="alert">{errorCarga}</p>}
  {!cargando && comunicados.length === 0 && <p>No hay comunicados publicados.</p>}

  <section>
    {comunicados.map(c => (
      <Tarjeta key={c.id}>
        <h3>{c.titulo}</h3>
        <p className="meta">{formatearFecha(c.fecha_publicacion)} · Administración</p>
        <p className={expandidos.has(c.id) ? "" : "truncado"}>{c.cuerpo}</p>
        {cuerpoLargo(c.cuerpo) && (
          <button onClick={() => toggleExpandir(c.id)}>
            {expandidos.has(c.id) ? "Ver menos" : "Ver más"}
          </button>
        )}
        {user.rol === "administracion" && (
          <button
            className="boton-borrar"
            disabled={idBorrando === c.id}
            onClick={() => setModalBorrar({ id: c.id, titulo: c.titulo })}
          >
            Borrar
          </button>
        )}
      </Tarjeta>
    ))}
  </section>

  {modalCrear && <ModalNuevoComunicado onClose={...} onCreado={...} />}
  {modalBorrar && <ModalConfirmarBorrado data={modalBorrar} onClose={...} onConfirm={...} />}
</main>
```

### Truncado

Se considera "cuerpo largo" si la cadena tiene más de 280 caracteres **o** más de 3 saltos de línea. El truncado visual se hace con CSS (`-webkit-line-clamp: 3; display: -webkit-box; -webkit-box-orient: vertical; overflow: hidden`) — el string no se modifica.

### Modal de creación (`ModalNuevoComunicado`)

Definido en el mismo archivo (`Comunicados.jsx`) o aparte; está bien cualquiera de los dos.

- Form con `<input type="text">` para título (required, `maxLength={255}`) y `<textarea>` para cuerpo (required, `maxLength={5000}`).
- Estado local: `titulo`, `cuerpo`, `enviando`, `error`.
- `onSubmit`: `e.preventDefault()` → `crearComunicado({ titulo, cuerpo })`.
  - `201`: `onCreado(nuevo)` (prepend a la lista del padre) y cerrar.
  - `400`: mostrar `result.data?.detail`.
  - `403`: "No tenés permisos para publicar comunicados." (defensa en profundidad — el botón ya está gateado).
  - otro: "Ocurrió un error inesperado. Intentá de nuevo.".
- Botón "Publicar" deshabilitado mientras `enviando === true`; texto pasa a "Publicando…".

### Modal de confirmación de borrado (`ModalConfirmarBorrado`)

- Texto: `¿Borrar el comunicado «{titulo}»? Esta acción no se puede deshacer.`
- Botones: `Cancelar` (cierra) y `Borrar` (color `--color-danger`).
- `onConfirm`: marca `idBorrando = id` y llama `borrarComunicado(id)`.
  - `204`: `setComunicados(prev => prev.filter(c => c.id !== id))`; limpia `errorBorrado`.
  - `404`: lo saca de la lista igual (`filter`) y setea `errorBorrado = "El comunicado ya no existe."`.
  - `403`: setea `errorBorrado = "No tenés permisos para borrar comunicados."`.
  - otro: setea `errorBorrado = "No se pudo borrar el comunicado. Intentá de nuevo."`.
- En **todos los casos** (éxito y error) se cierra el modal de confirmación y se limpia `idBorrando = null`. El `errorBorrado` se muestra arriba de la lista, no dentro del modal cerrado.
- Botón "Borrar" del modal deshabilitado y con texto "Borrando…" mientras hay request en vuelo.

## Manejo de status codes (frontend)

Sigue `frontend.md`:

| Código | Acción |
|---|---|
| 200 / 201 / 204 | Continuar el flujo (mostrar, refrescar local) |
| 400 | Mostrar `detail` del backend en el modal correspondiente |
| 401 | `apiFetch` dispara `_onUnauthorized` → `AuthContext.logout()`; el usuario vuelve a `/login` |
| 403 | Mensaje claro, sin exponer detalles internos |
| 404 | "El comunicado no existe" / "ya no existe" según el contexto |

## Paleta y tokens (CSS)

Variables nuevas en `src/index.css`:

```css
:root {
  --color-bg: #f5f5f7;
  --color-surface: #ffffff;
  --color-text: #1d1d1f;
  --color-text-muted: #6e6e73;
  --color-primary: #0066cc;
  --color-danger: #c0392b;
  --color-border: #e1e1e6;

  --radius-sm: 6px;
  --radius-md: 10px;

  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
}
```

Regla: **ningún componente nuevo usa hex/rgb inline**. Si hace falta un color que no existe en la paleta, se agrega una variable a `:root` primero.

## Fuera de alcance

- Notificaciones push o por email cuando se publica un comunicado.
- Edición de comunicados publicados (no hay `PATCH` en el backend; no se planea agregar acá).
- "Restaurar" un comunicado borrado: el soft-delete deja el dato en DB pero la UI no expone restauración en esta iteración.
- Filtros por fecha o por autor en la lista.
- Búsqueda full-text dentro de los comunicados.
- Internacionalización: toda la UI en español.

## Dependencias nuevas

- `react-router-dom` en `frontend/package.json`.
- Sin dependencias backend nuevas (sólo cambios en código).

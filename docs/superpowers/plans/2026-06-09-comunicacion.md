# Módulo de Comunicación — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar el módulo de Comunicación end-to-end: agregar borrado soft en el backend, montar la arquitectura de navegación de la SPA (sidebar + React Router), y construir la pantalla `/comunicados` con listar / crear / borrar.

**Architecture:** Backend FastAPI agrega columna `eliminado_at` a `Comunicado` y nuevo endpoint `DELETE /comunicados/{comunicado_id}` con permiso de Administración. Frontend pasa de un shell simple a una SPA enrutada con `react-router-dom`, `AppLayout` (sidebar + outlet), y componentes reutilizables (`Modal`, `Tarjeta`, `RequireAuth`). La pantalla `Comunicados` maneja lista, modal de creación y modal de confirmación de borrado con refresco optimista local.

**Tech Stack:**
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2.0, SQLite, pytest.
- Frontend: React 19, Vite 8, `react-router-dom` v6 (a instalar).
- Tests backend: `pytest -v` o `./.venv/Scripts/python.exe -m pytest -v` en Windows.
- Servidor dev backend: `uvicorn backend.main:app --reload`.
- Servidor dev frontend: `npm run dev` desde `frontend/`.

**Notas previas para el implementador:**
- El proyecto **no es un repo git** en esta workstation. Donde el plan dice "verificar y avanzar", asumir que es el punto de control entre tasks; no correr `git commit`. Si más adelante se inicializa git, los puntos de control pueden volverse commits reales.
- El proyecto sigue la regla **OpenAPI-first**: antes de implementar un endpoint nuevo, hay que documentarlo en `openapi.yaml`. La Task 1 cumple eso.
- Los nombres de path param deben ser **completos**: `{comunicado_id}`, nunca `{id}`. Regla de `.claude/rules/openapi-first.md`.
- La paleta CSS en `frontend/src/index.css` ya tiene todas las variables necesarias (`--color-primary`, `--color-danger`, `--color-surface`, `--color-border`, `--color-text-muted`, `--radius`, `--shadow-md`, etc.). **No agregar variables nuevas** para este módulo.

---

## Fase A — Backend: soporte de borrado soft

### Task 1: Documentar `DELETE /comunicados/{comunicado_id}` en OpenAPI

**Files:**
- Modify: `openapi.yaml` (insertar nueva sección debajo de la entrada `/comunicados` existente, antes del bloque de `/amenities`)

- [ ] **Step 1: Editar `openapi.yaml`**

Insertar este bloque **debajo** del bloque `/comunicados:` actual (que ya cubre `get` y `post`), antes del comentario `# 4. AMENITIES`:

```yaml
  /comunicados/{comunicado_id}:
    delete:
      tags: [Comunicación]
      summary: Borrar un comunicado (soft-delete)
      description: |
        Marca el comunicado como eliminado. Operación irreversible desde la UI.
        Solo accesible para Administración. Los comunicados eliminados dejan de
        aparecer en `GET /comunicados`.
      operationId: borrarComunicado
      parameters:
        - name: comunicado_id
          in: path
          required: true
          schema:
            type: integer
      responses:
        '204':
          description: Comunicado eliminado exitosamente.
        '401':
          $ref: '#/components/responses/NoAutenticado'
        '403':
          $ref: '#/components/responses/AccesoDenegado'
        '404':
          $ref: '#/components/responses/NoEncontrado'
```

- [ ] **Step 2: Validar que el YAML sigue siendo válido**

Run: `python -c "import yaml; yaml.safe_load(open('openapi.yaml', encoding='utf-8'))"`
Expected: sin salida (parsea bien). Si hay error, revisar indentación del bloque insertado.

- [ ] **Step 3: Verificar y avanzar a Task 2**

Confirmar visualmente que en `openapi.yaml` ahora existe la entrada `/comunicados/{comunicado_id}` con el verbo `delete`.

---

### Task 2: Agregar columna `eliminado_at` al modelo `Comunicado`

**Files:**
- Modify: `backend/models.py:158-171` (clase `Comunicado`)

- [ ] **Step 1: Editar la clase `Comunicado`**

Reemplazar el contenido actual de la clase (líneas 158-171) por:

```python
class Comunicado(Base):
    __tablename__ = "comunicados"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    cuerpo: Mapped[str] = mapped_column(String(5000), nullable=False)
    fecha_publicacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    autor_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    eliminado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
```

- [ ] **Step 2: Verificar que el módulo importa sin errores**

Run: `python -c "from backend.models import Comunicado; print(Comunicado.__table__.columns.keys())"`
Expected: lista con `['id', 'titulo', 'cuerpo', 'fecha_publicacion', 'autor_id', 'eliminado_at']`.

- [ ] **Step 3: Verificar y avanzar a Task 3**

---

### Task 3: Migrar la DB de desarrollo (`consorcio.db`)

**Files:**
- Modify: `consorcio.db` (vía SQL `ALTER TABLE`)

> Esta task se hace **una sola vez** sobre la DB de desarrollo. Los tests usan `:memory:` y se recrean con `Base.metadata.create_all`, así que para tests no hace falta migrar.

- [ ] **Step 1: Hacer backup de la DB**

Run: `cp consorcio.db consorcio.db.bak`
Expected: archivo `consorcio.db.bak` creado.

- [ ] **Step 2: Verificar el esquema actual**

Run: `python -c "import sqlite3; c = sqlite3.connect('consorcio.db'); print(c.execute('PRAGMA table_info(comunicados)').fetchall())"`
Expected: lista de columnas **sin** `eliminado_at`.

- [ ] **Step 3: Aplicar la migración**

Run: `python -c "import sqlite3; c = sqlite3.connect('consorcio.db'); c.execute('ALTER TABLE comunicados ADD COLUMN eliminado_at DATETIME NULL'); c.commit()"`
Expected: sin salida (éxito).

- [ ] **Step 4: Verificar el esquema actualizado**

Run: `python -c "import sqlite3; c = sqlite3.connect('consorcio.db'); print(c.execute('PRAGMA table_info(comunicados)').fetchall())"`
Expected: la lista ahora incluye `eliminado_at` con `type='DATETIME'` y `notnull=0`.

- [ ] **Step 5: Verificar y avanzar a Task 4**

---

### Task 4 (TDD): Filtrar comunicados eliminados en `GET /comunicados`

**Files:**
- Test: `tests/test_comunicados.py` (agregar al final del archivo, antes de las funciones de POST, en el bloque GET)
- Modify: `backend/routers/comunicados.py:19-26` (función `listar_comunicados`)

- [ ] **Step 1: Escribir el test que falla**

Agregar al final del bloque GET en `tests/test_comunicados.py` (después de `test_listar_comunicados_orden_por_fecha_desc`):

```python
def test_listar_comunicados_omite_los_eliminados(client, headers_admin, db_session):
    from datetime import datetime, timezone
    from backend.models import Comunicado

    # Marcar el comunicado sembrado (id=200) como eliminado.
    db_session.get(Comunicado, 200).eliminado_at = datetime.now(timezone.utc)
    db_session.commit()

    r = client.get("/comunicados", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []
```

- [ ] **Step 2: Correr el test y ver que falla**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comunicados.py::test_listar_comunicados_omite_los_eliminados -v`
Expected: FAIL — devuelve `[{"id": 200, ...}]` en vez de `[]`, porque el GET no filtra.

- [ ] **Step 3: Modificar `listar_comunicados` para filtrar**

En `backend/routers/comunicados.py`, reemplazar:

```python
    stmt = select(Comunicado).order_by(
        Comunicado.fecha_publicacion.desc(), Comunicado.id.desc()
    )
    return list(db.scalars(stmt).all())
```

por:

```python
    stmt = (
        select(Comunicado)
        .where(Comunicado.eliminado_at.is_(None))
        .order_by(Comunicado.fecha_publicacion.desc(), Comunicado.id.desc())
    )
    return list(db.scalars(stmt).all())
```

- [ ] **Step 4: Correr el test y ver que pasa**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comunicados.py::test_listar_comunicados_omite_los_eliminados -v`
Expected: PASS.

- [ ] **Step 5: Correr el archivo completo y verificar que nada se rompió**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comunicados.py -v`
Expected: todos los tests existentes siguen verdes.

- [ ] **Step 6: Verificar y avanzar a Task 5**

---

### Task 5 (TDD): Implementar `DELETE /comunicados/{comunicado_id}` — caso happy path

**Files:**
- Test: `tests/test_comunicados.py` (agregar nuevo bloque al final del archivo)
- Modify: `backend/routers/comunicados.py` (agregar nuevo endpoint al final)

- [ ] **Step 1: Escribir el test happy path**

Agregar al final de `tests/test_comunicados.py`:

```python
# ---------------------------------------------------------------------------
# DELETE /comunicados/{comunicado_id}
# ---------------------------------------------------------------------------


def test_borrar_comunicado_admin_devuelve_204(client, headers_admin):
    r = client.delete("/comunicados/200", headers=headers_admin)
    assert r.status_code == 204
    assert r.content == b""

    # El comunicado ya no aparece en el GET.
    r = client.get("/comunicados", headers=headers_admin)
    assert r.json() == []
```

- [ ] **Step 2: Correr el test y ver que falla**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comunicados.py::test_borrar_comunicado_admin_devuelve_204 -v`
Expected: FAIL — devuelve 405 (Method Not Allowed) porque el endpoint no existe.

- [ ] **Step 3: Implementar el endpoint mínimo**

En `backend/routers/comunicados.py`, agregar los imports faltantes arriba (si no están):

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
```

Agregar al final del archivo:

```python
@router.delete(
    "/{comunicado_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar un comunicado (soft-delete)",
)
def borrar_comunicado(
    comunicado_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> None:
    comunicado = db.get(Comunicado, comunicado_id)
    if comunicado is None or comunicado.eliminado_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El comunicado no existe.",
        )
    comunicado.eliminado_at = datetime.now(timezone.utc)
    db.commit()
    return None
```

- [ ] **Step 4: Correr el test y ver que pasa**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comunicados.py::test_borrar_comunicado_admin_devuelve_204 -v`
Expected: PASS.

- [ ] **Step 5: Verificar y avanzar a Task 6**

---

### Task 6 (TDD): Tests de errores del endpoint DELETE

**Files:**
- Test: `tests/test_comunicados.py` (agregar después del happy path)

- [ ] **Step 1: Escribir los tests de errores**

Agregar al final de `tests/test_comunicados.py`:

```python
def test_borrar_comunicado_sin_token_devuelve_401(client):
    r = client.delete("/comunicados/200")
    assert r.status_code == 401


def test_borrar_comunicado_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.delete("/comunicados/200", headers=headers_depto_a)
    assert r.status_code == 403


def test_borrar_comunicado_como_representante_devuelve_403(client, headers_representante):
    r = client.delete("/comunicados/200", headers=headers_representante)
    assert r.status_code == 403


def test_borrar_comunicado_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/comunicados/99999", headers=headers_admin)
    assert r.status_code == 404
    assert r.json()["detail"] == "El comunicado no existe."


def test_borrar_comunicado_ya_borrado_devuelve_404(client, headers_admin):
    # Primero borrarlo.
    r1 = client.delete("/comunicados/200", headers=headers_admin)
    assert r1.status_code == 204
    # Segunda vez: 404.
    r2 = client.delete("/comunicados/200", headers=headers_admin)
    assert r2.status_code == 404
    assert r2.json()["detail"] == "El comunicado no existe."
```

- [ ] **Step 2: Correr el bloque DELETE completo**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comunicados.py -v -k "borrar"`
Expected: 6 tests PASS (1 happy path + 5 de errores).

- [ ] **Step 3: Correr toda la suite del proyecto**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: toda la suite verde. Ningún test de otros módulos roto.

- [ ] **Step 4: Verificar y avanzar a Fase B**

---

## Fase B — Frontend: infraestructura de navegación y componentes base

### Task 7: Instalar `react-router-dom`

**Files:**
- Modify: `frontend/package.json` (dependencia nueva)
- Modify: `frontend/package-lock.json` (autogenerado)

- [ ] **Step 1: Instalar la dependencia**

Run (desde `frontend/`): `npm install react-router-dom@^6.30.0`
Expected: el bloque `dependencies` de `package.json` ahora incluye `"react-router-dom": "^6.30.0"`. Se crea/actualiza `package-lock.json`.

- [ ] **Step 2: Verificar que el dev server arranca**

Run (desde `frontend/`): `npm run dev` (en otra terminal)
Expected: Vite arranca en `http://localhost:5173` sin errores en la consola.

Detener el dev server con Ctrl+C antes de avanzar.

- [ ] **Step 3: Verificar y avanzar a Task 8**

---

### Task 8: Crear componente `Modal` reutilizable

**Files:**
- Create: `frontend/src/components/Modal.jsx`

- [ ] **Step 1: Crear el archivo `Modal.jsx`**

Contenido completo:

```jsx
import { useEffect } from "react";

export default function Modal({ titulo, onClose, children }) {
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  function onBackdropClick(e) {
    if (e.target === e.currentTarget) onClose();
  }

  return (
    <div className="modal-backdrop" onClick={onBackdropClick}>
      <section className="modal" role="dialog" aria-modal="true" aria-label={titulo}>
        <header className="modal-header">
          <h3>{titulo}</h3>
          <button
            type="button"
            className="modal-cerrar"
            onClick={onClose}
            aria-label="Cerrar"
          >
            ×
          </button>
        </header>
        <div className="modal-cuerpo">{children}</div>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Verificar y avanzar a Task 9**

(Los estilos del modal se agregan en la Task 18, junto con el resto del CSS).

---

### Task 9: Crear componente `Tarjeta` reutilizable

**Files:**
- Create: `frontend/src/components/Tarjeta.jsx`

- [ ] **Step 1: Crear el archivo `Tarjeta.jsx`**

Contenido completo:

```jsx
export default function Tarjeta({ children, className = "" }) {
  return (
    <article className={`tarjeta ${className}`.trim()}>
      {children}
    </article>
  );
}
```

- [ ] **Step 2: Verificar y avanzar a Task 10**

---

### Task 10: Crear componente `RequireAuth` (guard de rutas privadas)

**Files:**
- Create: `frontend/src/components/RequireAuth.jsx`

- [ ] **Step 1: Crear el archivo `RequireAuth.jsx`**

Contenido completo:

```jsx
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function RequireAuth({ children }) {
  const { user, hydrating } = useAuth();
  const location = useLocation();

  if (hydrating) {
    return <p style={{ padding: "2rem", textAlign: "center" }}>Cargando...</p>;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}
```

- [ ] **Step 2: Verificar y avanzar a Task 11**

---

### Task 11: Crear componente `Sidebar` con gating por rol

**Files:**
- Create: `frontend/src/components/Sidebar.jsx`

- [ ] **Step 1: Crear el archivo `Sidebar.jsx`**

Contenido completo:

```jsx
import { NavLink } from "react-router-dom";

const MODULOS = [
  {
    ruta: "/comunicados",
    nombre: "Comunicación",
    rolesPermitidos: ["administracion", "representante", "departamento"],
  },
  // Los próximos módulos se agregan acá (expensas, peticiones, trabajos, reservas, administración).
];

export default function Sidebar({ rol }) {
  const visibles = MODULOS.filter((m) => m.rolesPermitidos.includes(rol));

  return (
    <aside className="app-sidebar">
      <nav>
        <ul>
          {visibles.map((m) => (
            <li key={m.ruta}>
              <NavLink
                to={m.ruta}
                className={({ isActive }) =>
                  isActive ? "sidebar-link activo" : "sidebar-link"
                }
              >
                {m.nombre}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: Verificar y avanzar a Task 12**

---

### Task 12: Crear componente `AppLayout` (shell autenticado)

**Files:**
- Create: `frontend/src/components/AppLayout.jsx`

- [ ] **Step 1: Crear el archivo `AppLayout.jsx`**

Contenido completo:

```jsx
import { Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import Sidebar from "./Sidebar";

export default function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Gestión de Consorcios</h1>
        <nav className="app-user">
          <span>
            {user.email} <strong>({user.rol})</strong>
          </span>
          <button type="button" onClick={logout}>
            Cerrar sesión
          </button>
        </nav>
      </header>

      <div className="app-body">
        <Sidebar rol={user.rol} />
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar y avanzar a Task 13**

---

### Task 13: Crear pantalla `NotFound`

**Files:**
- Create: `frontend/src/screens/NotFound.jsx`

- [ ] **Step 1: Crear el archivo `NotFound.jsx`**

Contenido completo:

```jsx
import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section>
      <h2>Página no encontrada</h2>
      <p>La ruta que intentaste abrir no existe.</p>
      <Link to="/comunicados">Volver al inicio</Link>
    </section>
  );
}
```

- [ ] **Step 2: Verificar y avanzar a Task 14**

---

### Task 14: Crear módulo de API `api/comunicados.js`

**Files:**
- Create: `frontend/src/api/comunicados.js`

- [ ] **Step 1: Crear el archivo**

Contenido completo:

```js
import { apiFetch } from "./client";

export function listarComunicados() {
  return apiFetch("/comunicados");
}

export function crearComunicado({ titulo, cuerpo }) {
  return apiFetch("/comunicados", {
    method: "POST",
    body: { titulo, cuerpo },
  });
}

export function borrarComunicado(id) {
  return apiFetch(`/comunicados/${id}`, {
    method: "DELETE",
  });
}
```

- [ ] **Step 2: Verificar y avanzar a Fase C**

---

## Fase C — Frontend: enrutado de `App.jsx` y `Login.jsx`

### Task 15: Reescribir `App.jsx` con `BrowserRouter`

**Files:**
- Modify: `frontend/src/App.jsx` (reemplazo completo)

- [ ] **Step 1: Reemplazar el contenido completo de `App.jsx`**

```jsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import AppLayout from "./components/AppLayout";
import RequireAuth from "./components/RequireAuth";
import Login from "./screens/Login";
import Comunicados from "./screens/Comunicados";
import NotFound from "./screens/NotFound";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="/comunicados" replace />} />
            <Route path="comunicados" element={<Comunicados />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

> Nota: `Comunicados.jsx` todavía no existe — el dev server va a romper en esta task. Se crea en la Task 17. Mientras tanto no probamos visualmente.

- [ ] **Step 2: Verificar y avanzar a Task 16**

---

### Task 16: Hacer que `Login.jsx` navegue a `/comunicados` después del login

**Files:**
- Modify: `frontend/src/screens/Login.jsx` (agregar `useNavigate` y redirección)

- [ ] **Step 1: Agregar el import de `useNavigate`**

En `frontend/src/screens/Login.jsx`, modificar el bloque de imports superior a:

```jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api/client";
import { useAuth } from "../auth/AuthContext";
```

- [ ] **Step 2: Usar el hook `useNavigate` dentro del componente**

Dentro de la función `Login()`, justo después de `const { login } = useAuth();`, agregar:

```jsx
  const navigate = useNavigate();
```

- [ ] **Step 3: Navegar tras el login exitoso**

En el bloque `if (result.status === 200)`, reemplazar:

```jsx
    if (result.status === 200) {
      login(result.data.access_token, result.data.user);
      return;
    }
```

por:

```jsx
    if (result.status === 200) {
      login(result.data.access_token, result.data.user);
      navigate("/comunicados", { replace: true });
      return;
    }
```

- [ ] **Step 4: Verificar y avanzar a Task 17**

---

## Fase D — Frontend: pantalla `Comunicados.jsx`

### Task 17: Crear esqueleto de `Comunicados.jsx` con carga inicial (GET)

**Files:**
- Create: `frontend/src/screens/Comunicados.jsx`

- [ ] **Step 1: Crear el archivo con la carga inicial mínima**

```jsx
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { listarComunicados } from "../api/comunicados";
import Tarjeta from "../components/Tarjeta";

function formatearFecha(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export default function Comunicados() {
  const { user } = useAuth();
  const [comunicados, setComunicados] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  useEffect(() => {
    let cancelado = false;

    async function cargar() {
      const r = await listarComunicados();
      if (cancelado) return;

      if (r.status === 200) {
        setComunicados(r.data);
        setErrorCarga(null);
      } else if (r.status !== 401) {
        // 401 lo maneja apiFetch (logout automático). El resto es error genérico.
        setErrorCarga("No se pudieron cargar los comunicados.");
      }
      setCargando(false);
    }

    cargar();
    return () => {
      cancelado = true;
    };
  }, []);

  return (
    <section>
      <header className="seccion-header">
        <h2>Comunicados</h2>
        {user.rol === "administracion" && (
          <button type="button">+ Nuevo comunicado</button>
        )}
      </header>

      {cargando && <p>Cargando…</p>}
      {errorCarga && <p role="alert" className="error-banner">{errorCarga}</p>}
      {!cargando && !errorCarga && comunicados.length === 0 && (
        <p>No hay comunicados publicados.</p>
      )}

      <ul className="lista-comunicados">
        {comunicados.map((c) => (
          <li key={c.id}>
            <Tarjeta>
              <h3>{c.titulo}</h3>
              <p className="meta">
                {formatearFecha(c.fecha_publicacion)} · Administración
              </p>
              <p>{c.cuerpo}</p>
            </Tarjeta>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

> Esta versión no tiene "ver más" ni modales — los agregamos en las próximas tasks. El botón "Nuevo comunicado" todavía no hace nada.

- [ ] **Step 2: Probar visualmente el flujo de login + lista**

Run (desde `frontend/`): `npm run dev`
Run (en otra terminal desde la raíz): `uvicorn backend.main:app --reload`

En el browser:
1. Abrir `http://localhost:5173` → redirige a `/login`.
2. Loguearse con un usuario de seed (`admin@test.local` / `test-pass-1234`, o el usuario que tengas seeded).
3. Verificar que después del login navega a `/comunicados` y muestra al menos un comunicado.
4. Verificar que el sidebar a la izquierda tiene un link "Comunicación" marcado como activo.

Expected: pantalla con header, sidebar, y al menos una tarjeta visible.

- [ ] **Step 3: Verificar y avanzar a Task 18**

---

### Task 18: Agregar el CSS del layout y los componentes nuevos

**Files:**
- Modify: `frontend/src/index.css` (agregar al final del archivo)

- [ ] **Step 1: Agregar estilos al final de `index.css`**

```css
/* ---------- App body (sidebar + content) ---------- */

.app-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.app-sidebar {
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  padding: 1rem 0;
  width: 220px;
  flex-shrink: 0;
}

.app-sidebar nav ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.sidebar-link {
  display: block;
  padding: 0.7em 1.5em;
  color: var(--color-text);
  text-decoration: none;
  border-left: 3px solid transparent;
  font-size: 0.95rem;
}

.sidebar-link:hover {
  background: var(--color-bg);
}

.sidebar-link.activo {
  background: var(--color-bg);
  border-left-color: var(--color-primary);
  color: var(--color-primary);
  font-weight: 600;
}

.app-content {
  flex: 1;
  padding: 2rem;
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
}

/* ---------- Sección genérica ---------- */

.seccion-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.error-banner {
  color: var(--color-danger);
  background: var(--color-danger-bg);
  padding: 0.6em 0.8em;
  border-radius: var(--radius);
  font-size: 0.9rem;
}

/* ---------- Tarjeta ---------- */

.tarjeta {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  box-shadow: var(--shadow-sm);
}

.tarjeta h3 {
  margin: 0 0 0.25rem;
  font-size: 1.05rem;
}

.tarjeta .meta {
  color: var(--color-text-muted);
  font-size: 0.85rem;
  margin: 0 0 0.5rem;
}

/* ---------- Lista de comunicados ---------- */

.lista-comunicados {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.cuerpo-truncado {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.tarjeta-acciones {
  margin-top: 0.75rem;
  display: flex;
  gap: 0.5rem;
}

.boton-link {
  background: transparent;
  color: var(--color-primary);
  padding: 0.3em 0.5em;
  border: none;
  font-size: 0.9rem;
}

.boton-link:hover:not(:disabled) {
  background: var(--color-bg);
  text-decoration: underline;
}

.boton-borrar {
  background: transparent;
  color: var(--color-danger);
  padding: 0.3em 0.5em;
  border: 1px solid var(--color-danger);
  font-size: 0.9rem;
}

.boton-borrar:hover:not(:disabled) {
  background: var(--color-danger-bg);
}

/* ---------- Modal ---------- */

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal {
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow-md);
  width: 100%;
  max-width: 520px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--color-border);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
}

.modal-cerrar {
  background: transparent;
  color: var(--color-text-muted);
  padding: 0.2em 0.5em;
  border: none;
  font-size: 1.5rem;
  line-height: 1;
}

.modal-cuerpo {
  padding: 1.25rem;
  overflow-y: auto;
}

.modal-cuerpo form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.modal-cuerpo textarea {
  font-family: inherit;
  font-size: 1rem;
  padding: 0.55em 0.75em;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-surface);
  color: var(--color-text);
  width: 100%;
  min-height: 140px;
  resize: vertical;
}

.modal-cuerpo textarea:focus {
  outline: 2px solid var(--color-primary);
  outline-offset: -1px;
  border-color: var(--color-primary);
}

.modal-acciones {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.boton-secundario {
  background: transparent;
  color: var(--color-text);
  border: 1px solid var(--color-border);
}

.boton-secundario:hover:not(:disabled) {
  background: var(--color-bg);
}

.boton-peligro {
  background: var(--color-danger);
  color: #fff;
}
```

- [ ] **Step 2: Verificar visualmente el layout**

Con el dev server corriendo, recargar el browser:
- El sidebar a la izquierda debe verse con borde derecho y el link "Comunicación" activo.
- Las tarjetas deben verse con fondo blanco, borde sutil y sombra.

- [ ] **Step 3: Verificar y avanzar a Task 19**

---

### Task 19: Agregar truncado del cuerpo + botón "Ver más" inline

**Files:**
- Modify: `frontend/src/screens/Comunicados.jsx`

- [ ] **Step 1: Agregar helpers y estado para expandidos**

Justo después de `formatearFecha`, agregar:

```jsx
function cuerpoLargo(cuerpo) {
  if (cuerpo.length > 280) return true;
  if (cuerpo.split("\n").length > 3) return true;
  return false;
}
```

Dentro del componente `Comunicados`, después de los demás `useState`, agregar:

```jsx
  const [expandidos, setExpandidos] = useState(() => new Set());

  function toggleExpandir(id) {
    setExpandidos((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
```

- [ ] **Step 2: Reemplazar el `<p>{c.cuerpo}</p>` del map por la versión con truncado**

En el JSX del `map`, reemplazar el bloque actual de la tarjeta:

```jsx
<Tarjeta>
  <h3>{c.titulo}</h3>
  <p className="meta">
    {formatearFecha(c.fecha_publicacion)} · Administración
  </p>
  <p>{c.cuerpo}</p>
</Tarjeta>
```

por:

```jsx
<Tarjeta>
  <h3>{c.titulo}</h3>
  <p className="meta">
    {formatearFecha(c.fecha_publicacion)} · Administración
  </p>
  <p className={expandidos.has(c.id) ? "" : "cuerpo-truncado"}>
    {c.cuerpo}
  </p>
  {cuerpoLargo(c.cuerpo) && (
    <div className="tarjeta-acciones">
      <button
        type="button"
        className="boton-link"
        onClick={() => toggleExpandir(c.id)}
      >
        {expandidos.has(c.id) ? "Ver menos" : "Ver más"}
      </button>
    </div>
  )}
</Tarjeta>
```

- [ ] **Step 3: Probar visualmente**

Recargar el browser. Si tu DB de dev tiene algún comunicado con cuerpo corto, va a verse entero sin botón. Para probar el truncado:
- Logueate como admin.
- Por ahora todavía no hay UI de crear; podés usar `curl` o ejecutar manualmente:

```bash
curl -X POST http://localhost:8000/comunicados \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"titulo":"Cuerpo largo de prueba","cuerpo":"'"$(printf 'línea %s\n' 1 2 3 4 5 6)"'"}'
```

(Si no podés probarlo cómodamente ahora, salteá: la creación se prueba en la Task 21.)

- [ ] **Step 4: Verificar y avanzar a Task 20**

---

### Task 20: Crear `ModalNuevoComunicado` y conectar el botón "+ Nuevo comunicado"

**Files:**
- Modify: `frontend/src/screens/Comunicados.jsx`

- [ ] **Step 1: Importar `Modal` y `crearComunicado`**

Modificar los imports superiores:

```jsx
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { listarComunicados, crearComunicado } from "../api/comunicados";
import Modal from "../components/Modal";
import Tarjeta from "../components/Tarjeta";
```

- [ ] **Step 2: Agregar estado para el modal y handler de creación**

Dentro del componente `Comunicados`, sumar a los `useState` existentes:

```jsx
  const [modalCrearAbierto, setModalCrearAbierto] = useState(false);
```

Y la función handler (debajo de `toggleExpandir`):

```jsx
  function handleCreado(nuevo) {
    setComunicados((prev) => [nuevo, ...prev]);
    setModalCrearAbierto(false);
  }
```

- [ ] **Step 3: Conectar el botón "+ Nuevo comunicado"**

Reemplazar:

```jsx
{user.rol === "administracion" && (
  <button type="button">+ Nuevo comunicado</button>
)}
```

por:

```jsx
{user.rol === "administracion" && (
  <button type="button" onClick={() => setModalCrearAbierto(true)}>
    + Nuevo comunicado
  </button>
)}
```

- [ ] **Step 4: Renderizar el modal al final del JSX**

Justo antes del `</section>` final, agregar:

```jsx
{modalCrearAbierto && (
  <Modal titulo="Nuevo comunicado" onClose={() => setModalCrearAbierto(false)}>
    <FormularioNuevoComunicado
      onCreado={handleCreado}
      onCancelar={() => setModalCrearAbierto(false)}
    />
  </Modal>
)}
```

- [ ] **Step 5: Agregar el componente `FormularioNuevoComunicado` al mismo archivo**

Al final del archivo (después de `export default function Comunicados()`), agregar:

```jsx
function FormularioNuevoComunicado({ onCreado, onCancelar }) {
  const [titulo, setTitulo] = useState("");
  const [cuerpo, setCuerpo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setEnviando(true);

    const r = await crearComunicado({ titulo, cuerpo });
    setEnviando(false);

    if (r.status === 201) {
      onCreado(r.data);
      return;
    }
    if (r.status === 400) {
      setError(r.data?.detail || "Revisá los campos del formulario.");
      return;
    }
    if (r.status === 403) {
      setError("No tenés permisos para publicar comunicados.");
      return;
    }
    if (r.status !== 401) {
      setError("Ocurrió un error inesperado. Intentá de nuevo.");
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <label>
        Título
        <input
          type="text"
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
          maxLength={255}
          required
          autoFocus
        />
      </label>

      <label>
        Cuerpo
        <textarea
          value={cuerpo}
          onChange={(e) => setCuerpo(e.target.value)}
          maxLength={5000}
          required
        />
      </label>

      {error && <p role="alert" className="error-banner">{error}</p>}

      <div className="modal-acciones">
        <button
          type="button"
          className="boton-secundario"
          onClick={onCancelar}
          disabled={enviando}
        >
          Cancelar
        </button>
        <button type="submit" disabled={enviando}>
          {enviando ? "Publicando…" : "Publicar"}
        </button>
      </div>
    </form>
  );
}
```

- [ ] **Step 6: Probar visualmente el flujo de creación**

Con backend + frontend corriendo, logueado como `administracion`:
1. Click en "+ Nuevo comunicado" → abre modal.
2. Llenar título y cuerpo, click "Publicar".
3. El modal se cierra y el comunicado aparece **arriba** de la lista.
4. Probar campos vacíos: el browser bloquea por `required`.
5. Probar cerrar con Escape, con la X, y con click en el backdrop.

Expected: los tres modos cierran el modal.

- [ ] **Step 7: Verificar y avanzar a Task 21**

---

### Task 21: Crear modal de confirmación de borrado y conectar botón "Borrar" en cada tarjeta

**Files:**
- Modify: `frontend/src/screens/Comunicados.jsx`

- [ ] **Step 1: Importar `borrarComunicado`**

Modificar el import del módulo de API:

```jsx
import { listarComunicados, crearComunicado, borrarComunicado } from "../api/comunicados";
```

- [ ] **Step 2: Agregar estado para el borrado**

Sumar a los `useState` existentes:

```jsx
  const [modalBorrar, setModalBorrar] = useState(null); // { id, titulo } | null
  const [idBorrando, setIdBorrando] = useState(null);
  const [errorBorrado, setErrorBorrado] = useState(null);
```

- [ ] **Step 3: Agregar el handler de confirmación de borrado**

Debajo de `handleCreado`, agregar:

```jsx
  async function handleConfirmarBorrado() {
    if (!modalBorrar) return;
    const id = modalBorrar.id;
    setIdBorrando(id);

    const r = await borrarComunicado(id);

    setIdBorrando(null);
    setModalBorrar(null);

    if (r.status === 204) {
      setComunicados((prev) => prev.filter((c) => c.id !== id));
      setErrorBorrado(null);
      return;
    }
    if (r.status === 404) {
      setComunicados((prev) => prev.filter((c) => c.id !== id));
      setErrorBorrado("El comunicado ya no existe.");
      return;
    }
    if (r.status === 403) {
      setErrorBorrado("No tenés permisos para borrar comunicados.");
      return;
    }
    if (r.status !== 401) {
      setErrorBorrado("No se pudo borrar el comunicado. Intentá de nuevo.");
    }
  }
```

- [ ] **Step 4: Mostrar el `errorBorrado` arriba de la lista**

Justo después de `{errorCarga && ...}` (línea de error de carga), agregar:

```jsx
{errorBorrado && <p role="alert" className="error-banner">{errorBorrado}</p>}
```

- [ ] **Step 5: Agregar el botón "Borrar" en cada tarjeta (solo admin)**

Dentro del `<div className="tarjeta-acciones">` agregar el botón borrar **después** del botón "Ver más". Como `tarjeta-acciones` solo aparece si `cuerpoLargo(c.cuerpo)`, hay que reestructurar para que las acciones aparezcan siempre que haya algo que mostrar (ver más, o borrar para admin):

Reemplazar el bloque actual:

```jsx
{cuerpoLargo(c.cuerpo) && (
  <div className="tarjeta-acciones">
    <button
      type="button"
      className="boton-link"
      onClick={() => toggleExpandir(c.id)}
    >
      {expandidos.has(c.id) ? "Ver menos" : "Ver más"}
    </button>
  </div>
)}
```

por:

```jsx
{(cuerpoLargo(c.cuerpo) || user.rol === "administracion") && (
  <div className="tarjeta-acciones">
    {cuerpoLargo(c.cuerpo) && (
      <button
        type="button"
        className="boton-link"
        onClick={() => toggleExpandir(c.id)}
      >
        {expandidos.has(c.id) ? "Ver menos" : "Ver más"}
      </button>
    )}
    {user.rol === "administracion" && (
      <button
        type="button"
        className="boton-borrar"
        disabled={idBorrando === c.id}
        onClick={() => setModalBorrar({ id: c.id, titulo: c.titulo })}
      >
        Borrar
      </button>
    )}
  </div>
)}
```

- [ ] **Step 6: Renderizar el modal de confirmación al final del JSX**

Justo antes del `</section>` final (y después del modal de creación), agregar:

```jsx
{modalBorrar && (
  <Modal titulo="Borrar comunicado" onClose={() => setModalBorrar(null)}>
    <p>
      ¿Borrar el comunicado «<strong>{modalBorrar.titulo}</strong>»? Esta acción
      no se puede deshacer.
    </p>
    <div className="modal-acciones">
      <button
        type="button"
        className="boton-secundario"
        onClick={() => setModalBorrar(null)}
        disabled={idBorrando === modalBorrar.id}
      >
        Cancelar
      </button>
      <button
        type="button"
        className="boton-peligro"
        onClick={handleConfirmarBorrado}
        disabled={idBorrando === modalBorrar.id}
      >
        {idBorrando === modalBorrar.id ? "Borrando…" : "Borrar"}
      </button>
    </div>
  </Modal>
)}
```

- [ ] **Step 7: Probar visualmente el flujo de borrado**

Con backend + frontend corriendo, logueado como `administracion`:
1. En una tarjeta, click "Borrar" → abre modal con el título del comunicado.
2. Click "Cancelar" → modal se cierra, la tarjeta sigue ahí.
3. Click "Borrar" → la tarjeta desaparece de la lista.
4. Refrescar la página → la tarjeta sigue sin aparecer (el backend respeta el filtro).
5. Cerrar sesión y entrar como un usuario rol `departamento` → no se ve el botón "Borrar" en ninguna tarjeta.

Expected: el flujo funciona en todos los casos. El botón "+ Nuevo comunicado" tampoco se ve para `departamento`.

- [ ] **Step 8: Verificar y avanzar a la verificación final**

---

## Verificación final

### Task 22: Smoke test end-to-end

- [ ] **Step 1: Correr toda la suite de tests del backend**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: todos los tests verdes.

- [ ] **Step 2: Verificar el flujo completo en el browser como admin**

1. Logout (si estás logueado).
2. Login como admin.
3. Sidebar muestra "Comunicación" activo.
4. Se ve la lista de comunicados (al menos el seed inicial).
5. Crear un comunicado nuevo → aparece arriba de la lista.
6. Crear un comunicado con cuerpo largo (>280 chars) → aparece truncado, botón "Ver más" lo expande.
7. Borrar un comunicado con confirmación → desaparece.
8. Refrescar la página → los borrados siguen sin aparecer, los nuevos siguen ahí.
9. Cerrar sesión → vuelve a `/login`.

- [ ] **Step 3: Verificar el flujo como rol `departamento`**

1. Login con un usuario rol `departamento` (seed: `a@test.local` / `test-pass-1234`).
2. Se ve la lista de comunicados.
3. **No** se ve el botón "+ Nuevo comunicado".
4. **No** se ven los botones "Borrar" en las tarjetas.
5. Si en el sidebar se intenta abrir manualmente `/comunicados` (que es la única ruta), funciona.
6. Probar abrir `/algo-inexistente` en la URL → muestra `NotFound`.

- [ ] **Step 4: Verificar el flujo como rol `representante`**

1. Login con un usuario rol `representante` (seed: `repre@test.local` / `test-pass-1234`).
2. Se ve la lista de comunicados pero **sin** botones de admin (igual que `departamento`).

- [ ] **Step 5: Listo**

Si todos los chequeos pasan, el módulo de Comunicación está terminado.

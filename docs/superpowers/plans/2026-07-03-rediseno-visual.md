# Rediseño Visual "Aire" + Paleta Command — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar la piel visual del frontend (colores, tipografía, botones, sidebar, tablas, modales) por el sistema "Aire" + paleta Command validado en `docs/superpowers/specs/2026-07-03-rediseno-visual-design.md`, sin tocar lógica ni comportamiento.

**Architecture:** Todo el design system vive en `frontend/src/index.css` (tokens en `:root` + clases globales reutilizadas por todas las pantallas). Los JSX solo reciben ajustes mínimos: unificación de clases de cards, bloque de logo en el sidebar y limpieza de 2 colores hardcodeados inline. La verificación es manual en navegador (no existe infraestructura de tests de frontend; TDD no aplica a cambios puramente visuales — cada task termina con verificación visual + commit).

**Tech Stack:** React + Vite, CSS plano con variables, Google Fonts (Inter).

**Contexto para el ejecutor:**
- Dev server: `npm run dev` desde `frontend/` (URL típica http://localhost:5173).
- Regla del proyecto: colores SIEMPRE vía `var(--color-...)`; nunca hex/rgb en componentes. Mobile-first, breakpoints `@media (min-width: 600px)` y `@media (min-width: 960px)`, targets táctiles ≥44px.
- Usuarios de prueba: ver `backend/seed.py` (roles administracion / departamento / representante).
- Estados transitorios aceptables entre tasks (p. ej. Task 2 deja las cards sin el estilo `inactivo` hasta que Task 3 lo agrega). Los tasks se ejecutan en orden, back-to-back.

---

### Task 1: Cargar Inter desde Google Fonts

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Agregar preconnect + link de Inter al `<head>`**

En `frontend/index.html`, después de la línea `<meta name="viewport" ...>`, agregar:

```html
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
      rel="stylesheet"
    />
```

El `<head>` completo queda:

```html
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
      rel="stylesheet"
    />
    <title>Gestión de Consorcios</title>
  </head>
```

- [ ] **Step 2: Verificar que la fuente carga**

Run: `npm run dev` (desde `frontend/`, dejarlo corriendo en background para todo el plan).
Abrir la app en el navegador → DevTools → Network → filtrar "fonts.googleapis". Debe aparecer la request del CSS de Inter con status 200. La UI todavía se ve igual (el token `--font-sans` se cambia en Task 3).

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "style(frontend): carga Inter desde Google Fonts"
```

---

### Task 2: Unificar cards de Amenities y Reservas sobre `.tarjeta`

**Files:**
- Modify: `frontend/src/screens/Amenities.jsx:55`
- Modify: `frontend/src/screens/Reservas.jsx:246` y `frontend/src/screens/Reservas.jsx:270`

- [ ] **Step 1: Reemplazar `card-amenity` en Amenities.jsx**

Línea 55, cambiar:

```jsx
          <li key={a.id} className={`card-amenity${a.activo ? "" : " inactivo"}`}>
```

por:

```jsx
          <li key={a.id} className={`tarjeta${a.activo ? "" : " inactivo"}`}>
```

- [ ] **Step 2: Reemplazar `card-reserva` en Reservas.jsx**

Línea 246, cambiar:

```jsx
              <li key={r.id} className="card-reserva">
```

por:

```jsx
              <li key={r.id} className="tarjeta">
```

Línea 270, cambiar:

```jsx
                    className={`card-reserva${activa ? "" : " cancelada"}`}
```

por:

```jsx
                    className={`tarjeta${activa ? "" : " cancelada"}`}
```

- [ ] **Step 3: Verificar en navegador**

Con sesión de administración, visitar `/amenities` y `/reservas`. Las cards deben verse como tarjetas (borde + fondo blanco). Los modificadores `inactivo`/`cancelada` quedan momentáneamente sin efecto visual — se re-estilan en Task 3 (esperado, no es bug).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/screens/Amenities.jsx frontend/src/screens/Reservas.jsx
git commit -m "refactor(frontend): amenities y reservas usan la clase tarjeta base"
```

---

### Task 3: Reescribir `index.css` con el design system "Aire" + Command

**Files:**
- Rewrite: `frontend/src/index.css` (reemplazo completo del archivo)

- [ ] **Step 1: Reemplazar el contenido completo de `frontend/src/index.css`**

Usar el tool Write con exactamente este contenido (mantiene TODOS los nombres de clase existentes; cambia la piel):

```css
/* =====================================================================
   Design system "Aire" + paleta Command
   Spec: docs/superpowers/specs/2026-07-03-rediseno-visual-design.md
   Los componentes consumen colores SIEMPRE vía var(--color-...).
   Sombras solo en elevaciones reales (modal, drawer, dropdown).
   ===================================================================== */

:root {
  /* Paleta */
  --color-bg: #faf9f6;
  --color-surface: #ffffff;
  --color-text: #1c1917;
  --color-text-muted: #78716c;
  --color-border: #eceae4;
  --color-border-strong: #e5e2da;
  --color-primary: #3460a8;
  --color-primary-hover: #2a4f8c;
  --color-primary-soft: #e9eff8;
  --color-danger: #c0443c;
  --color-danger-bg: #f9e9e8;
  --color-success: #24734c;
  --color-success-bg: #e7f4ec;
  --color-warning: #8a6d1a;
  --color-warning-bg: #fdf3d7;

  /* Geometría y elevación */
  --radius: 10px;
  --radius-sm: 8px;
  --shadow-md: 0 8px 24px rgba(28, 25, 23, 0.1);

  /* Tipografía */
  --font-sans: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;

  font-family: var(--font-sans);
  font-size: 16px;
  color: var(--color-text);
  background: var(--color-bg);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
}

h1, h2, h3 {
  margin: 0 0 0.5em;
  font-weight: 600;
  color: var(--color-text);
  letter-spacing: -0.01em;
}

h4 {
  margin: 0 0 0.25em;
  font-weight: 600;
  color: var(--color-text);
}

p {
  margin: 0 0 0.5em;
}

/* ---------- Controles base ---------- */

button {
  font-family: inherit;
  font-size: 0.95rem;
  font-weight: 600;
  padding: 0.6em 1.2em;
  min-height: 44px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: #fff;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

button:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

input,
select,
textarea {
  font-family: inherit;
  font-size: 1rem;
  padding: 0.55em 0.75em;
  min-height: 44px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text);
  width: 100%;
}

input:focus,
select:focus,
textarea:focus {
  outline: 2px solid var(--color-primary);
  outline-offset: -1px;
  border-color: var(--color-primary);
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.35em;
  font-size: 0.9rem;
  color: var(--color-text-muted);
}

img, svg, video {
  max-width: 100%;
  height: auto;
  display: block;
}

/* ---------- Tablas (global) ---------- */

table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 0.9rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
}

th {
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted);
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid var(--color-border);
}

td {
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid var(--color-border);
}

tr:last-child td {
  border-bottom: none;
}

/* ---------- Login ---------- */

.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 1rem;
}

.login-card {
  background: var(--color-surface);
  padding: 1.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  width: 100%;
  max-width: 380px;
}

.login-card h1 {
  font-size: 1.5rem;
  margin-bottom: 0.25rem;
}

.login-subtitle {
  color: var(--color-text-muted);
  margin-bottom: 1.5rem;
}

.login-card form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.login-error {
  color: var(--color-danger);
  background: var(--color-danger-bg);
  padding: 0.6em 0.8em;
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  margin: 0;
}

/* ---------- App shell (logged-in) — mobile-first ---------- */

.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.5rem;
}

.app-header-titulo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.app-header h1 {
  font-size: 1.1rem;
  margin: 0;
}

.hamburguesa {
  background: transparent;
  color: var(--color-text);
  border: 1px solid var(--color-border-strong);
  padding: 0.4em 0.7em;
  min-height: 44px;
  min-width: 44px;
  font-size: 1.3rem;
  line-height: 1;
}

.hamburguesa:hover:not(:disabled) {
  background: var(--color-surface);
}

.app-user {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  font-size: 0.85rem;
  color: var(--color-text-muted);
}

.app-user > span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.app-user button {
  background: transparent;
  color: var(--color-text);
  font-weight: 500;
  padding: 0.4em 0.8em;
  min-height: 44px;
  border: 1px solid var(--color-border-strong);
}

.app-user button:hover:not(:disabled) {
  background: var(--color-surface);
  border-color: var(--color-text-muted);
}

/* ---------- Campanita (notificaciones in-app) ---------- */

.campanita {
  position: relative;
  display: inline-block;
}

.campanita-boton {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 1.4rem;
  padding: 0.25rem 0.5rem;
  position: relative;
  min-height: 44px;
  min-width: 44px;
}

.campanita-boton:hover:not(:disabled) {
  background: var(--color-surface);
  border-radius: var(--radius-sm);
}

.campanita-badge {
  position: absolute;
  top: 0;
  right: 0;
  background: var(--color-danger);
  color: var(--color-surface);
  border-radius: 50%;
  padding: 0 0.35rem;
  font-size: 0.65rem;
  font-weight: 700;
  min-width: 1.1rem;
  line-height: 1.1rem;
  text-align: center;
}

.campanita-panel {
  position: absolute;
  top: 100%;
  right: 0;
  z-index: 100;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  min-width: 20rem;
  max-width: 90vw;
  max-height: 25rem;
  overflow-y: auto;
  box-shadow: var(--shadow-md);
  border-radius: var(--radius);
}

.campanita-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid var(--color-border);
}

.campanita-marcar-todas {
  background: transparent;
  border: 1px solid var(--color-border-strong);
  color: var(--color-primary);
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
  min-height: auto;
}

.campanita-vacio {
  padding: 1rem;
  color: var(--color-text-muted);
  margin: 0;
}

.campanita-lista {
  list-style: none;
  margin: 0;
  padding: 0;
}

.campanita-item {
  padding: 0.75rem 0.8rem;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
}

.campanita-item:last-child {
  border-bottom: none;
}

.campanita-item:hover {
  background: var(--color-bg);
}

.campanita-item-no-leida {
  background: var(--color-primary-soft);
}

.campanita-item-mensaje {
  margin: 0 0 0.25rem 0;
  font-size: 0.9rem;
  color: var(--color-text);
}

.campanita-item-fecha {
  margin: 0;
  font-size: 0.7rem;
  color: var(--color-text-muted);
}

/* ---------- App body (sidebar + content) — mobile-first ---------- */

.app-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.app-sidebar {
  background: var(--color-surface);
  padding: 0;
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  width: 80%;
  max-width: 320px;
  transform: translateX(-100%);
  transition: transform 0.2s ease-out;
  z-index: 1100;
  overflow-y: auto;
  box-shadow: var(--shadow-md);
  border-right: 1px solid var(--color-border);
}

.app-sidebar.abierto {
  transform: translateX(0);
}

.app-sidebar nav ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* Logo de la app: oculto en mobile (el drawer tiene su cabecera),
   visible arriba del sidebar en desktop */
.sidebar-logo {
  display: none;
}

.sidebar-cabecera {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--color-border);
}

.sidebar-cabecera-titulo {
  font-size: 0.85rem;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sidebar-cerrar {
  background: transparent;
  color: var(--color-text-muted);
  border: none;
  padding: 0.2em 0.6em;
  min-height: 44px;
  min-width: 44px;
  font-size: 1.4rem;
  line-height: 1;
}

.sidebar-cerrar:hover:not(:disabled) {
  background: var(--color-bg);
  color: var(--color-text);
}

.drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(28, 25, 23, 0.45);
  z-index: 1050;
}

.sidebar-section + .sidebar-section {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--color-border);
}

.sidebar-section-titulo {
  margin: 0;
  padding: 0.5em 1em 0.35em;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-muted);
}

.sidebar-link {
  display: flex;
  align-items: center;
  margin: 0 0.5rem;
  padding: 0.6em 0.75em;
  min-height: 44px;
  color: var(--color-text);
  text-decoration: none;
  font-size: 0.95rem;
  font-weight: 500;
  border-radius: var(--radius-sm);
}

.sidebar-link:hover {
  background: var(--color-bg);
}

.sidebar-link.activo {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 600;
}

.app-content {
  flex: 1;
  padding: 1rem;
  width: 100%;
  margin: 0;
}

/* ---------- Sección genérica ---------- */

.seccion-header {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.error-banner {
  color: var(--color-danger);
  background: var(--color-danger-bg);
  padding: 0.6em 0.8em;
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
}

/* ---------- Tarjeta (card base única) ---------- */

.tarjeta {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem;
}

.tarjeta h3 {
  margin: 0 0 0.25rem;
  font-size: 1.05rem;
  overflow-wrap: anywhere;
}

.tarjeta h4 {
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
}

.tarjeta .meta {
  color: var(--color-text-muted);
  font-size: 0.85rem;
  margin: 0 0 0.5rem;
}

.tarjeta p {
  overflow-wrap: anywhere;
}

.tarjeta.inactivo {
  opacity: 0.6;
}

.tarjeta.cancelada {
  opacity: 0.5;
  text-decoration: line-through;
}

.tarjeta .acciones {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.75rem;
}

.tarjeta .acciones button {
  flex: 1 1 auto;
  font-size: 0.85rem;
  padding: 0.4em 0.8em;
  min-height: 44px;
}

.tarjeta .vacio {
  color: var(--color-text-muted);
  font-style: italic;
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
  flex-wrap: wrap;
}

.boton-link {
  background: transparent;
  color: var(--color-primary);
  padding: 0.3em 0.5em;
  min-height: 44px;
  border: none;
  font-size: 0.9rem;
}

.boton-link:hover:not(:disabled) {
  background: var(--color-primary-soft);
  text-decoration: underline;
}

.boton-borrar {
  background: transparent;
  color: var(--color-danger);
  padding: 0.3em 0.5em;
  min-height: 44px;
  border: 1px solid var(--color-danger);
  font-size: 0.9rem;
}

.boton-borrar:hover:not(:disabled) {
  background: var(--color-danger-bg);
}

/* ---------- Modal — mobile-first (full screen en mobile) ---------- */

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(28, 25, 23, 0.45);
  display: flex;
  align-items: stretch;
  justify-content: stretch;
  z-index: 1000;
  padding: 0;
}

.modal {
  background: var(--color-surface);
  border-radius: 0;
  box-shadow: var(--shadow-md);
  width: 100%;
  max-width: 100%;
  max-height: 100vh;
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
  min-height: 44px;
  min-width: 44px;
  border: none;
  font-size: 1.5rem;
  line-height: 1;
}

.modal-cerrar:hover:not(:disabled) {
  background: var(--color-bg);
  color: var(--color-text);
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
  min-height: 140px;
  resize: vertical;
}

.modal-acciones {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
  flex-wrap: wrap;
}

.boton-secundario {
  background: var(--color-surface);
  color: var(--color-text);
  border: 1px solid var(--color-border-strong);
}

.boton-secundario:hover:not(:disabled) {
  background: var(--color-bg);
  border-color: var(--color-text-muted);
}

.boton-peligro {
  background: var(--color-danger);
  color: #fff;
}

.boton-peligro:hover:not(:disabled) {
  background: #a93b34;
}

/* ---------- Badges ---------- */

.badge {
  display: inline-block;
  padding: 0.25em 0.7em;
  border-radius: 999px;
  border: none;
  font-size: 0.8rem;
  font-weight: 600;
}

.badge--neutro {
  background: var(--color-border);
  color: var(--color-text-muted);
}

.badge--ok {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.badge--alerta {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.badge--warning {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

/* ---------- Leyenda ---------- */

.leyenda {
  color: var(--color-text-muted);
  font-size: 0.85rem;
  margin: 0.25rem 0 0.5rem;
}

/* ---------- Filtros ---------- */

.filtros {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.filtros label {
  font-size: 0.9rem;
}

/* ---------- Acciones del header (selector + botón) ---------- */

.seccion-acciones {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  align-items: stretch;
}

/* ---------- Listas de expensas y comprobantes ---------- */

.lista-expensas,
.lista-comprobantes {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* ---------- Imagen de comprobante ---------- */

.comprobante-img {
  max-width: 100%;
  max-height: 240px;
  margin: 0.5rem 0;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  object-fit: contain;
  cursor: zoom-in;
}

/* ============================================================ */
/* Tablet (≥600px)                                              */
/* ============================================================ */
@media (min-width: 600px) {
  .login-card {
    padding: 2rem;
  }

  .app-header {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem;
  }

  .app-user {
    flex-wrap: nowrap;
    justify-content: flex-end;
    font-size: 0.9rem;
  }

  .app-content {
    padding: 1.5rem;
  }

  .seccion-header {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }

  .modal-backdrop {
    padding: 1rem;
    align-items: center;
    justify-content: center;
  }

  .modal {
    max-width: 520px;
    max-height: 90vh;
    border-radius: var(--radius);
  }

  .filtros {
    flex-direction: row;
    align-items: flex-end;
  }

  .seccion-acciones {
    flex-direction: row;
    align-items: center;
    gap: 0.75rem;
  }
}

/* ============================================================ */
/* Desktop (≥960px) — sidebar vertical a la izquierda           */
/* ============================================================ */
@media (min-width: 960px) {
  .app-body {
    flex-direction: row;
  }

  /* El nombre de la app vive en el sidebar en desktop */
  .app-header h1 {
    display: none;
  }

  .hamburguesa,
  .drawer-backdrop,
  .sidebar-cabecera {
    display: none;
  }

  .app-sidebar {
    position: static;
    transform: none;
    width: 230px;
    max-width: none;
    height: auto;
    flex-shrink: 0;
    background: var(--color-bg);
    border-right: 1px solid var(--color-border);
    padding: 1.25rem 0;
    overflow-x: visible;
    box-shadow: none;
    z-index: auto;
  }

  .sidebar-logo {
    display: block;
    padding: 0 1.25rem 1rem;
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--color-text);
  }

  .sidebar-link {
    margin: 0 0.75rem;
  }

  .sidebar-section + .sidebar-section {
    margin-top: 1rem;
    padding-top: 1rem;
  }

  .sidebar-section-titulo {
    padding: 0.5em 1.25em 0.4em;
  }

  .app-content {
    padding: 2rem 1.5rem;
    max-width: 960px;
    margin: 0 auto;
  }
}

/* ---------- Pantallas de Configuración ---------- */

.cabecera-pantalla {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-block-end: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.cabecera-acciones {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.filtro-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
}

.error {
  color: var(--color-danger);
  font-weight: 600;
}

.exito {
  color: var(--color-success);
  font-weight: 600;
}

.formulario-configuracion fieldset {
  margin-block: 1rem;
  padding: 1rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.formulario-configuracion legend {
  font-weight: 600;
  padding-inline: 0.5rem;
}

.formulario-configuracion label {
  display: block;
  margin-block: 0.75rem;
}

.formulario-configuracion input {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
}

.lista-config {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.lista-coeficientes {
  list-style: none;
  margin: 0.5rem 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.lista-coeficientes li {
  font-size: 0.95rem;
}

/* ---------- Tabs reutilizables (pills, mobile-first) ---------- */

.tabs {
  display: flex;
  gap: 0.5rem;
  margin-block-end: 1rem;
  flex-wrap: wrap;
}

.tab {
  flex: 1;
  padding: 0.6rem 1rem;
  min-height: 44px;
  text-align: center;
  text-decoration: none;
  color: var(--color-text-muted);
  font-weight: 500;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tab:hover {
  background: var(--color-surface);
  color: var(--color-text);
}

.tab.activo {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 600;
}

@media (min-width: 600px) {
  .tabs {
    justify-content: flex-start;
  }
  .tab {
    flex: 0 0 auto;
    min-width: 140px;
  }
}

/* ---------- Pantalla Gastos ---------- */

.filtros-gastos {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-block-end: 1rem;
}

.filtros-gastos label {
  display: flex;
  flex-direction: column;
  font-size: 0.9rem;
  gap: 0.25rem;
}

.lista-gastos {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

@media (min-width: 960px) {
  .filtros-gastos {
    flex-direction: row;
    flex-wrap: wrap;
  }
  .filtros-gastos label {
    flex: 1 1 200px;
  }
}

/* ---------- Grid de cards (amenities) ---------- */

.lista-cards {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 1rem;
}

@media (min-width: 600px) {
  .lista-cards {
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  }
}

.amenity-policies {
  margin: 0.5rem 0;
  font-size: 0.85rem;
}

.amenity-policies > div {
  display: flex;
  gap: 0.5rem;
  padding: 0.15rem 0;
}

.amenity-policies dt {
  font-weight: 600;
  color: var(--color-text-muted);
  margin: 0;
}

.amenity-policies dd {
  margin: 0;
}

/* Checkbox inline (label-checkbox) */
.label-checkbox {
  flex-direction: row;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
}

.label-checkbox input[type="checkbox"] {
  width: auto;
  min-height: auto;
  accent-color: var(--color-primary);
}

/* ---------- Banner políticas + form reserva ---------- */

.banner-politicas {
  background: var(--color-warning-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.5rem 0.75rem;
  margin: 0.75rem 0;
}

.banner-politicas header {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.banner-politicas .banner-toggle {
  margin-left: auto;
}

.banner-politicas ul {
  margin: 0.5rem 0 0 1rem;
  font-size: 0.85rem;
}

.form-reserva {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem;
  margin: 0.75rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.form-reserva h3 {
  margin: 0;
}

.cta-sticky button {
  width: 100%;
  min-height: 48px;
}

@media (max-width: 599px) {
  .cta-sticky {
    position: sticky;
    bottom: 0;
    background: var(--color-surface);
    padding: 0.5rem 0;
    box-shadow: 0 -2px 8px rgba(28, 25, 23, 0.06);
  }
}
```

Notas sobre lo que cambió respecto del archivo anterior (para el ejecutor, no hace falta acción):
- `--shadow-sm` eliminado (nadie más lo referencia — verificado con grep; las tarjetas ya no llevan sombra).
- `.card-amenity` y `.card-reserva` eliminados (el markup migró a `.tarjeta` en Task 2; los modificadores `inactivo`/`cancelada` y `.acciones` ahora viven bajo `.tarjeta`).
- Los `input/select/textarea` ahora se estilan global (antes `select` solo dentro de `.filtros` y `textarea` solo dentro de `.modal-cuerpo`); las reglas redundantes se eliminaron.
- Se agregaron estilos globales de `table/th/td` (antes las tablas de Cajas/Periodos/Reportes/Liquidaciones no tenían estilo).
- `.sidebar-logo` es nuevo (markup en Task 4).
- `.tab` pasa de subrayado a pill; `.sidebar-link.activo` pasa de border-left a pill suave.

- [ ] **Step 2: Verificar que Vite recompila sin errores**

Mirar la consola del `npm run dev`: sin errores. Refrescar el navegador.

- [ ] **Step 3: Verificación visual rápida (smoke)**

1. `/login`: fondo marfil, card con borde (sin sombra), botón azul #3460A8, focus azul en inputs, tipografía Inter (verificar en DevTools → Computed → font-family).
2. Login como administración → dashboard: header marfil, sidebar con pills (activa = fondo azul claro + texto azul).
3. `/cajas` o `/periodos`: la tabla ahora tiene fondo blanco, borde redondeado y headers en mayúsculas chicas.
4. A 375px (DevTools device toolbar): drawer abre/cierra, backdrop oscuro cálido, sin overflow horizontal.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css
git commit -m "style(frontend): design system Aire + paleta Command en index.css"
```

---

### Task 4: Logo de la app en el sidebar

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx` (dentro del `<aside>`, antes de `.sidebar-cabecera`)

- [ ] **Step 1: Agregar el bloque de logo**

En `Sidebar.jsx`, el `return` actual empieza:

```jsx
  return (
    <aside className={abierto ? "app-sidebar abierto" : "app-sidebar"}>
      <div className="sidebar-cabecera">
```

Cambiarlo por:

```jsx
  return (
    <aside className={abierto ? "app-sidebar abierto" : "app-sidebar"}>
      <div className="sidebar-logo">Gestión de Consorcios</div>
      <div className="sidebar-cabecera">
```

(El CSS de Task 3 ya lo oculta en mobile y lo muestra en desktop; el `<h1>` del header se oculta en desktop vía CSS — `AppLayout.jsx` no se toca.)

- [ ] **Step 2: Verificar en navegador**

- Desktop (≥960px): "Gestión de Consorcios" arriba del sidebar en bold; el header ya no repite el nombre.
- Mobile (375px): el drawer NO muestra el logo (cabecera "Menú / ✕" como siempre); el header muestra el título.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Sidebar.jsx
git commit -m "style(frontend): logo de la app en el sidebar (desktop)"
```

---

### Task 5: Limpiar colores hardcodeados inline

**Files:**
- Modify: `frontend/src/screens/ReporteProveedores.jsx:57`
- Modify: `frontend/src/components/ModalPresentarPago.jsx:57`

- [ ] **Step 1: ReporteProveedores.jsx — borde de la fila de totales**

Línea 57, cambiar:

```jsx
            <tr style={{ fontWeight: "bold", borderTop: "2px solid #ccc" }}>
```

por:

```jsx
            <tr style={{ fontWeight: "bold", borderTop: "2px solid var(--color-border-strong)" }}>
```

- [ ] **Step 2: ModalPresentarPago.jsx — nota informativa**

Línea 57, cambiar:

```jsx
        <p style={{ color: "var(--color-text-muted, #666)", fontSize: "0.85rem", margin: "0.5rem 0 1rem", padding: "0.5rem 0.75rem", borderLeft: "3px solid var(--color-primary, #0d6efd)", background: "rgba(13, 110, 253, 0.05)" }}>
```

por:

```jsx
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.85rem", margin: "0.5rem 0 1rem", padding: "0.5rem 0.75rem", borderLeft: "3px solid var(--color-primary)", background: "var(--color-primary-soft)" }}>
```

- [ ] **Step 3: Verificar que no quedan hex/rgb hardcodeados en JSX**

Run (Grep tool o desde `frontend/`):

```bash
grep -rnE "#[0-9a-fA-F]{3,6}|rgba?\(" src --include="*.jsx"
```

Expected: solo fallbacks dentro de `var(--color-..., #666)` (aceptables) — ningún color suelto fuera de `var()`.

- [ ] **Step 4: Verificar en navegador**

`/reportes/proveedores` (fila de totales con borde cálido) y el modal "Presentar pago" desde `/mi-cuenta` o `/expensas` con rol departamento (nota con fondo azul suave).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/ReporteProveedores.jsx frontend/src/components/ModalPresentarPago.jsx
git commit -m "style(frontend): colores inline via tokens del design system"
```

---

### Task 6: Verificación integral pantalla por pantalla

**Files:** ninguno nuevo (fixes menores si aparecen, en `frontend/src/index.css`)

- [ ] **Step 1: Recorrido como administración**

Con `npm run dev` corriendo, login como admin y visitar cada una, en desktop **y** a 375px:
`/comunicados`, `/peticiones`, `/trabajos`, `/trabajos-recurrentes`, `/reservas`, `/amenities`, `/expensas`, `/comprobantes`, `/periodos`, `/gastos`, `/estado-financiero`, `/cajas`, `/transferencias`, `/reportes/morosos`, `/reportes/estado-financiero`, `/reportes/gastos`, `/reportes/proveedores`, `/liquidaciones`, `/haberes`, `/conceptos-liquidacion`, `/configuracion`, `/clases-prorrateo`, `/proveedores`, `/departamentos`, `/empleados`.

Checklist por pantalla:
- Sin overflow horizontal a 375px.
- Tablas legibles (headers uppercase muted, bordes cálidos).
- Badges con fondo suave (ok=verde, alerta=coral, warning=ámbar, neutro=gris).
- Botones: primario azul, secundario blanco con borde, borrar/peligro coral.
- Modales: full-screen en mobile, centrados con radius en desktop.
- Tabs (donde haya): pills, activa azul suave.

- [ ] **Step 2: Recorrido como departamento**

Login con usuario de rol departamento: `/mi-cuenta` (saldo con color semántico), `/expensas`, `/comprobantes`, `/reservas`, `/comunicados`, `/configuracion` (solo lectura). Verificar campanita: panel con sombra, item no leído en azul suave.

- [ ] **Step 3: Estados especiales**

- Forzar un error (p. ej. crear reserva inválida): `.error-banner` coral suave.
- Banner de políticas en `/reservas`: fondo ámbar suave.
- CTA sticky de reservas en mobile: pegado abajo con sombra sutil.

- [ ] **Step 4: Corregir hallazgos menores**

Cualquier desajuste (espaciados, contraste, overflow) se corrige en `index.css` respetando los tokens. Si un hallazgo requiere cambio de markup o de alcance, anotarlo y consultarlo en la review — no improvisar.

- [ ] **Step 5: Commit final (si hubo fixes)**

```bash
git add frontend/src/index.css
git commit -m "style(frontend): ajustes finales de verificación visual"
```

---

## Self-review del plan (hecho)

- **Cobertura del spec:** tokens (§1→Task 3), componentes (§2→Task 3), tipografía (§1→Tasks 1+3), sidebar/header (§3→Tasks 3+4), pasada por pantallas y hardcodes (§4→Tasks 2+5), verificación (§6→Task 6). Dark mode y frameworks: fuera de alcance, sin tasks. ✔
- **Placeholders:** el CSS está completo (archivo entero), los diffs de JSX son exactos con línea. ✔
- **Consistencia de nombres:** `--color-border-strong`, `--color-primary-soft`, `--radius-sm` usados de forma uniforme entre Task 3 y Task 5; clases `tarjeta/inactivo/cancelada` consistentes entre Tasks 2 y 3. ✔

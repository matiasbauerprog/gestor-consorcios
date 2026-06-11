---
paths:
  - "frontend/**/*.{js,jsx,ts,tsx,html,css}"
---

# Convenciones del frontend

## Stack
- React + Vite (SPA). Consumo de la API vía `fetch`.
- Comando de desarrollo: `npm run dev` desde la carpeta `frontend/`.

## Estructura (HTML / JSX)
- Usar etiquetas HTML semánticas: `<main>`, `<section>`, `<header>`, `<nav>`, `<form>`, `<article>`, `<button>`. Evitar la "sopa de divs": un `<div>` solo se usa cuando no hay alternativa semántica.
- Cada pantalla debe tener un único `<main>`. Los formularios siempre van dentro de `<form>` con `onSubmit`, y los botones de acción dentro de `<button type="submit">` (no `<div onClick>`).

## Estilo (CSS)
- Definir una paleta global mediante variables CSS en `src/index.css`:
  ```css
  :root {
    --color-bg: #...;
    --color-text: #...;
    --color-primary: #...;
    --color-danger: #...;
  }
  ```
- Consumir los colores siempre vía `var(--color-...)`. **Nunca hardcodear hex/rgb dentro de componentes** — eso rompe la paleta unificada.
- Cambiar el tema = editar una sola línea por variable.

## Responsive / Mobile-first
- **Mobile-first como default.** El CSS base apunta a viewports angostos (≥320px). Las mejoras para pantallas más grandes se hacen con `@media (min-width: ...)`, nunca con `max-width`.
- **Breakpoints estándar del proyecto:**
  ```css
  /* base = mobile (≥320px) */
  @media (min-width: 600px)  { /* tablet */ }
  @media (min-width: 960px)  { /* desktop */ }
  ```
- **Layout flexible:** en mobile las cosas apilan (`flex-direction: column`); a partir de tablet/desktop pasan a `row`. Sidebar visible sólo desde ≥960px (drawer/menú abajo en mobile).
- **Sin overflow horizontal.** Nada hardcodeado en px que pueda exceder 100vw. Imágenes/media siempre con `max-width: 100%; height: auto`.
- **Targets táctiles ≥44px de alto** (botones, links de nav, inputs).
- **Unidades relativas:** `rem`/`em`/`%` para tamaños; `px` sólo para bordes, sombras y detalles.
- **Test mínimo:** la pantalla tiene que ser usable a **375px** de ancho (iPhone SE). En el DevTools del browser: device toolbar → iPhone SE.
- Las clases existentes (`.app-shell`, `.app-sidebar`, `.app-content`, `.tarjeta`, `.modal`, etc.) deben revisarse y adaptarse a este criterio.

## Estado y comportamiento (React)
- **Estado siempre en hooks (`useState` / `useReducer`).** Nunca guardar datos de usuario, formularios o errores manipulando el DOM directamente (`document.querySelector`, `innerHTML`, etc.) ni en `useRef` para datos que deberían disparar re-render.
- **Triángulo dinámico explícito** en formularios:
  1. **Evento:** `onSubmit` del `<form>` con `e.preventDefault()`.
  2. **Estado:** llamar a `apiFetch`, guardar respuesta o error con `setState`.
  3. **Render:** React re-renderiza automáticamente al cambiar el estado; mostrar el error o el éxito según el estado actual.

### Status codes esperados del backend
Contrato cerrado con FastAPI. El helper `apiFetch` y los componentes deben manejar:

| Código | Significado | Acción típica en el frontend |
|---|---|---|
| `200` / `201` / `204` | Éxito | Continuar el flujo (mostrar, redirigir, refrescar) |
| `400` | Pedido inválido o body incompleto | Mostrar mensaje de validación |
| `401` | Token ausente / inválido / credenciales inválidas | Patear al login (limpiar `AuthContext` y `localStorage`) |
| `403` | Rol sin permisos para el recurso | Mensaje claro, sin exponer detalles |
| `404` | Recurso no existe | Mensaje "no encontrado" |
| `409` | Conflicto (transición de estado inválida, duplicado) | Mostrar el `detail` del backend |

## Auth y consumo de la API
- Helper `apiFetch(url, options)` que inyecta `Authorization: Bearer <token>` automáticamente y centraliza el manejo de 401.
- Estado de auth global: `AuthContext` con `{id, email, rol, departamento_id}` y el token.
- Persistir el token en `localStorage` para sobrevivir refresh; hidratar el `AuthContext` al cargar la app.

## Gating por rol
- La UI debe ocultar o deshabilitar elementos según `user.rol`. Ejemplo: el botón "Crear expensa" solo se renderiza si `rol === 'administracion'`.
- Aun así, **el backend valida server-side** (defensa en profundidad — el frontend nunca es la única barrera).

## Reutilización
- Preferir componentes parametrizables (`Tarjeta`, `Formulario`, `Lista`, `Header`, `Boton`) sobre duplicar markup.

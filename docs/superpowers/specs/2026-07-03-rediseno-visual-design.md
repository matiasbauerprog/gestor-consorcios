# Rediseño visual de la app — "Aire" + paleta Command

**Fecha:** 2026-07-03
**Alcance:** capa visual del frontend (CSS + ajustes menores de markup). Sin cambios de lógica, rutas, permisos ni comportamiento.

## Objetivo

Reemplazar el look genérico actual (azul #2563eb, fuente de sistema, gris frío) por una interfaz moderna y minimalista: layout limpio estilo Linear/Notion ("Aire") con la paleta de Command Soluciones (fondo marfil, azul #3460A8, coral para alertas). Dirección validada con mockups en el visual companion (`.superpowers/brainstorm/395-1783047449/content/`).

## Decisiones validadas

| Decisión | Elección |
|---|---|
| Dirección visual | "Aire" (bordes finos, sin sombras en tarjetas, mucho blanco) |
| Paleta | Command: marfil + azul #3460A8 + coral #C0443C |
| Estado activo del sidebar | Pill suave (fondo azul claro, texto azul) |
| Tipografía | Inter (Google Fonts, fallback system-ui) |
| Temas | Solo claro (dark mode queda fuera de alcance; los tokens lo permiten a futuro) |
| Alcance técnico | Reescritura de `index.css` + ajustes de markup donde el diseño lo exige |

## 1. Tokens (`:root` en `frontend/src/index.css`)

### Colores

| Token | Valor | Uso |
|---|---|---|
| `--color-bg` | `#faf9f6` | Fondo marfil de la app |
| `--color-surface` | `#ffffff` | Tarjetas, modales, inputs, drawer |
| `--color-text` | `#1c1917` | Texto principal |
| `--color-text-muted` | `#78716c` | Secundario, labels, metadatos |
| `--color-border` | `#eceae4` | Bordes de tarjetas/tablas |
| `--color-border-strong` | `#e5e2da` | Bordes de inputs y botones secundarios |
| `--color-primary` | `#3460a8` | Botones, links, focus, pill activa (texto) |
| `--color-primary-hover` | `#2a4f8c` | Hover del primario |
| `--color-primary-soft` | `#e9eff8` | Pill activa del sidebar, tabs activas, no-leídos |
| `--color-danger` | `#c0443c` | Errores, borrar, vencido |
| `--color-danger-bg` | `#f9e9e8` | Fondo suave de danger |
| `--color-success` | `#24734c` | Pagado, activo |
| `--color-success-bg` | `#e7f4ec` | Fondo suave de success |
| `--color-warning` | `#8a6d1a` | Parcial, pendiente |
| `--color-warning-bg` | `#fdf3d7` | Fondo suave de warning |

Regla del proyecto vigente: los componentes consumen colores **solo** vía `var(--color-...)`; ningún hex hardcodeado en JSX ni en reglas específicas de pantalla.

### Tipografía

- Inter cargada por `<link>` en `frontend/index.html` (pesos 400/500/600/700), `--font-sans: 'Inter', system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`.
- Títulos `font-weight: 600`; cuerpo 400/500.
- Cifras/KPIs: `font-weight: 700; letter-spacing: -0.02em`.

### Geometría y elevación

- `--radius: 10px` (tarjetas, panels, modales), `--radius-sm: 8px` (botones, inputs, pills del sidebar), `999px` (badges).
- Bordes de `1px`.
- **Tarjetas sin sombra** (solo borde). Sombra suave (`--shadow-md`) únicamente en elevaciones reales: modal, drawer mobile, panel de campanita.

## 2. Componentes base (clases globales, mismos nombres)

- **Botones:** primario azul sólido, radius 8, sin sombra, hover `--color-primary-hover`. `.boton-secundario`: blanco, borde `--color-border-strong`. `.boton-borrar`/`.boton-peligro`: coral. `.boton-link`: texto azul sin fondo. Alturas táctiles ≥44px se conservan.
- **Inputs/selects/textareas:** fondo blanco, borde `--color-border-strong`, focus con outline 2px `--color-primary`, radius 8. Labels chicos en muted.
- **Tarjetas:** `.tarjeta` es la base única (blanco, borde, radius 10, sin sombra). `.card-amenity` y `.card-reserva` migran a `.tarjeta` (+ modificador si hace falta). `.login-card` usa el mismo tratamiento.
- **Badges:** pill de fondo suave + texto oscuro del mismo tono (`--color-*-bg` + `--color-*`), sin borde. Aplica a `.badge--*` y `BadgeEstado`.
- **Tablas:** header con texto 0.75rem uppercase muted sin fondo; filas con separador sutil; contenedor con borde + radius 10.
- **Tabs:** pills suaves — activa con `--color-primary-soft` y texto azul (se abandona el subrayado inferior).
- **Modales:** full-screen en mobile (comportamiento actual), centrado con radius 10 y `--shadow-md` en ≥600px. Backdrop `rgba(28, 25, 23, 0.45)`.
- **Banners/leyendas:** `.error-banner` y `.banner-politicas` con fondo suave semántico + borde del mismo tono.
- **Campanita:** panel con borde cálido y sombra suave; item no leído con `--color-primary-soft` (reemplaza el amarillo warning actual).

## 3. Shell: sidebar y header

### Sidebar (`Sidebar.jsx` + CSS)

- **Desktop (≥960px):** fondo marfil (igual que la página) separado por borde derecho cálido. Bloque de **logo/nombre "Gestión de Consorcios"** arriba (nuevo markup). Links como pills (radius 8, margen lateral); activa = pill suave. Títulos de sección en mayúsculas chicas muted.
- **Mobile:** drawer actual intacto en comportamiento; panel blanco, cabecera "Menú / ✕" re-estilada.
- Sin cambios de lógica (filtrado por rol y visibilidad de reportes quedan igual).

### Header (`AppLayout.jsx` + CSS)

- Desktop: fondo marfil, borde inferior sutil; `<h1>` oculto vía CSS (el nombre vive en el sidebar); derecha: campanita + usuario + "Cerrar sesión" como botón fantasma.
- Mobile: hamburguesa + título como hoy.

## 4. Pasada por pantallas

- Reemplazar estilos hardcodeados que rompen el sistema: fieldsets/tabs de Configuración con `border: 1px solid var(--color-text)` pasan a `--color-border`.
- Unificar clases de card duplicadas (amenities, reservas) sobre `.tarjeta`.
- Revisar que ninguna pantalla dependa de sombras/colores viejos.

## 5. Manejo de errores visuales

No aplica manejo de errores de runtime (cambio puramente visual). Riesgos y mitigación:

- **Regresión de layout:** verificación manual pantalla por pantalla (ver §6).
- **FOUT de Inter:** `display=swap` en el link de Google Fonts + fallback system-ui en `--font-sans`.

## 6. Verificación

1. `npm run dev` desde `frontend/`.
2. Revisar en navegador por rol (administración y departamento como mínimo): dashboard/comunicados, expensas + modales, comprobantes, reservas/amenities, gastos, configuración, login.
3. Cada pantalla a **375px** (iPhone SE) y desktop ≥960px: sin overflow horizontal, targets ≥44px, drawer y modales funcionando.
4. Estados: error (banner), vacío, badges de todos los tonos, item no leído de campanita.
5. `pytest -v` no aplica (backend intacto); no hay tests de frontend en el proyecto.

## Fuera de alcance

- Dark mode (los tokens quedan preparados, no se implementa).
- Cambios de lógica, rutas, permisos, API o textos funcionales.
- Migración a frameworks CSS.
- `demo_estetica.html` queda como artefacto de exploración; no se integra al build (puede borrarse al finalizar).

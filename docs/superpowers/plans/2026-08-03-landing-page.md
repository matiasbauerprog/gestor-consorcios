# Landing page de venta — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar `index.html` de la raíz por una landing de venta nueva que muestre el producto mediante un simulador jugable de 4 pasos, con la identidad visual de la app.

**Architecture:** Un único archivo HTML autocontenido (CSS y JS inline), sin build ni dependencias externas más allá de Google Fonts. El simulador es una réplica en HTML/CSS de las pantallas reales con el estado en un objeto JS plano; cada paso deja un rastro visible en el siguiente.

**Tech Stack:** HTML5 + CSS custom properties + JavaScript vanilla. Fuentes Montserrat y Plus Jakarta Sans vía Google Fonts.

**Spec:** `docs/superpowers/specs/2026-08-03-landing-page-design.md`

## Global Constraints

Estas reglas aplican a **todas** las tareas.

- **Regla de copy (dura):** prohibido "te facilitamos la vida", "potenciá tu gestión", "optimizá", "solución integral" y equivalentes. Cada sección nombra el problema en el idioma del administrador; la prueba es la pantalla, no el adjetivo.
- **Prohibido escribir "Liquidación Ley 941".** La única mención permitida es: "gastos clasificados por rubro, como los pide la 941".
- **Tokens de color — copiados literal de `frontend/src/index.css`:** `--color-bg: #f4f0e6`, `--color-surface: #ffffff`, `--color-text: #121212`, `--color-text-muted: #706c64`, `--color-border: #e3ded2`, `--color-border-strong: #d6d0c4`, `--color-primary: #2c6473`, `--color-primary-hover: #24525e`, `--color-primary-soft: #e7f0f3`, `--color-danger: #b33f38`, `--color-danger-bg: #f7e0de`, `--color-success: #26784f`, `--color-success-bg: #e3efe7`, `--color-warning: #84691b`, `--color-warning-bg: #f7efd4`.
- **Colores por módulo:** `--color-mod-inicio: #1b3a4b`, `--color-mod-cobranzas: #305d4a`, `--color-mod-gastos: #c0443c`, `--color-mod-finanzas: #8a6d1c`, `--color-mod-expensas: #2c6473`, `--color-mod-operacion: #5b36b8`.
- **Geometría:** `--radius-sm: 12px`, `--radius: 16px`, `--radius-lg: 20px`, `--radius-pill: 999px`, `--shadow-md: 0 8px 24px rgba(18,18,18,0.1)`.
- **Tipografía:** `--font-display: "Montserrat"` para h1-h3 y cifras destacadas (weight 800); `--font-sans: "Plus Jakarta Sans"` para body. El piso de peso en UI es 600, no 400.
- **Responsive mobile-first.** Escribir el CSS para mobile y alivianar en `@media (min-width: 600px)`. **Nunca estirar un contenedor al subir de breakpoint** — reorganizar en columnas/grid o usar `max-width`/`fit-content`. Verificar siempre a 375px.
- **Número de WhatsApp: `5491178959108`.** Definido UNA sola vez como `const WHATSAPP = "5491178959108";` al inicio del `<script>`. Ningún link `wa.me` hardcodea el número.
- **Sin build, sin frameworks, sin CDN de JS.** Todo el CSS en un `<style>` y todo el JS en un `<script>`, ambos inline.
- **Demo real:** `https://consorciosdemo.vercel.app/`.

---

## File Structure

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `index.html` | Reemplazar | La landing completa. Sin copia de respaldo: la versión vieja queda en el historial de git. |
| `assets/.gitkeep` | Crear | Reserva la carpeta para `demo.mp4` y `demo-poster.jpg`, que el usuario sube después. |
| `demo-tutorial.html` | **No tocar** | Fuera de alcance. |
| `frontend/**` | **No tocar** | Fuera de alcance. |

**Nota sobre el archivo único:** normalmente convendría partir esto en varios archivos, pero el spec pide un HTML autocontenido que se abra con doble click y se publique en cualquier hosting estático. Para que siga siendo editable, el archivo se estructura con **anclas de comentario** fijas que cada tarea usa como punto de inserción. Las anclas se crean todas en la Task 1 y no se renombran nunca.

Anclas (en este orden dentro de `<body>`):

```html
<!-- ===== NAV ===== -->
<!-- ===== HERO ===== -->
<!-- ===== DOLORES ===== -->
<!-- ===== SIMULADOR ===== -->
<!-- ===== CTA-SIMULADOR ===== -->
<!-- ===== CONSORCIO ===== -->
<!-- ===== MODULOS ===== -->
<!-- ===== PRECIOS ===== -->
<!-- ===== CIERRE ===== -->
<!-- ===== FOOTER ===== -->
```

Y dentro de `<style>` / `<script>`, las mismas anclas con el mismo nombre para que cada tarea sepa dónde poner su CSS y su JS.

## Cómo se verifica cada tarea

Este entregable es un HTML estático: **no hay runner de tests**. `pytest` cubre el backend y no toca este archivo. El ciclo de verificación de cada tarea lo reemplaza una comprobación en browser con observaciones esperadas explícitas, y es igual de obligatorio que un test.

En cada tarea donde dice "Verificar en browser", hacer exactamente esto:

1. Abrir `file:///F:/backup/Command Soluciones/capacitaciones/IISAIA-main/proyecto/PROYECTO FINAL/index.html` en una pestaña nueva de Chrome.
2. Tomar screenshot con la ventana en **1440x900** y compararlo contra las observaciones esperadas de la tarea.
3. Redimensionar a **375x812** y tomar otro screenshot. Confirmar que no hay scroll horizontal en `<body>` y que ningún contenedor quedó estirado.
4. Leer la consola. **Cero errores.** Un warning de fuente no cargada es aceptable offline; un `TypeError` no.

Si alguna observación esperada no se cumple, arreglar antes de commitear.

## Datos del simulador (fuente única de verdad)

Todas las tareas del simulador usan estos valores. **No inventar otros.**

**Consorcio:** Edificio Libertad · 24 unidades funcionales · período activo `2026-08`.

**Gastos ya cargados en el período** (los tres se ven al abrir el paso 1):

| Rubro | Concepto | Proveedor | Monto |
|---|---|---|---|
| Sueldos y cargas sociales | Sueldo encargado agosto | — | $1.240.000 |
| Servicios públicos | Luz de partes comunes | Edenor | $186.400 |
| Seguros | Póliza integral del consorcio | Sancor Seguros | $92.700 |

Total del período **antes** del paso 1: **$1.519.100**.

**El gasto que carga el visitante en el paso 1:**
Rubro `Abonos y servicios` · Concepto "Abono mensual de ascensores" · Proveedor "Ascensores Del Plata" · Monto **$480.000** · Clase de prorrateo **"A — Expensas ordinarias"** · Caja "Banco Nación cta. cte." · Período 2026-08.

Total del período **después**: **$1.999.100**.

**Preview de cierre (paso 2):** Total a expensar **$1.999.100** · Boletas **24** · Intereses **$18.430**.

Filas visibles del preview (6 de 24):

| Unidad | Ubicación | Coef. | Monto |
|---|---|---|---|
| 1A | Piso 1, letra A | 3,90 % | $77.965 |
| 1B | Piso 1, letra B | 3,90 % | $77.965 |
| 2A | Piso 2, letra A | 4,15 % | $82.963 |
| 2B | Piso 2, letra B | 4,15 % | $82.963 |
| 3A | Piso 3, letra A | 4,40 % | $87.960 |
| 3B | Piso 3, letra B | 4,40 % | $87.960 |

**Cuenta corriente de la UF 2A (paso 3)** — titular Carlos G.:

| Período | Concepto | Monto | Estado inicial |
|---|---|---|---|
| 2026-05 | Expensa emitida | $74.200 | impaga |
| 2026-06 | Expensa emitida | $79.800 | impaga |
| 2026-07 | Expensa emitida | $83.500 | impaga |
| 2026-08 | Expensa emitida | $82.963 | impaga — **emitida en el paso 2** |

Saldo inicial: **$320.463**.

**Montos de pago ofrecidos:** `$74.200` · `$120.000` (el sugerido, porque muestra la imputación parcial) · `$320.463`.

**Resultado FIFO con $120.000:** mayo saldado al 100 % ($74.200), junio recibe los $45.800 restantes y queda debiendo $34.000, julio y agosto intactos. **Saldo final: $200.463.**

**Paso 4 — portal de la UF 2A:** saldo $200.463, tabs `Resumen · Expensas · Comprobantes · Movimientos`, la expensa de agosto por $82.963, el detalle de gastos del mes con el abono de ascensores de $480.000, y el SUM disponible para reservar.

---

### Task 1: Esqueleto, tokens y navegación

**Files:**
- Create: `index.html` (reemplaza el existente)
- Create: `assets/.gitkeep`

**Interfaces:**
- Consumes: nada.
- Produces: las diez anclas de comentario listadas en File Structure; la variable global `const WHATSAPP = "5491178959108";`; la función `linkWhatsApp(mensaje)` que devuelve la URL `wa.me`; la clase CSS `.seccion` (padding vertical y `max-width: 1120px` centrado) que todas las secciones posteriores usan.

- [ ] **Step 1: Crear la carpeta de assets**

```bash
mkdir -p assets && touch assets/.gitkeep
```

- [ ] **Step 2: Escribir el esqueleto de `index.html`**

Reemplazar el contenido completo de `index.html` por:

```html
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gestor Consorcios — Expensas, gastos y cuentas corrientes para administradores</title>
<meta name="description" content="Prorrateá los gastos por coeficiente, emití las expensas de todos tus edificios e imputá cada pago a la deuda más vieja. Probá el simulador sin registrarte.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
/* ===== TOKENS ===== */
:root {
  --color-bg: #f4f0e6;
  --color-surface: #ffffff;
  --color-text: #121212;
  --color-text-muted: #706c64;
  --color-text-muted-strong: #66625a;
  --color-border: #e3ded2;
  --color-border-strong: #d6d0c4;
  --color-primary: #2c6473;
  --color-primary-hover: #24525e;
  --color-primary-soft: #e7f0f3;
  --color-danger: #b33f38;
  --color-danger-bg: #f7e0de;
  --color-success: #26784f;
  --color-success-bg: #e3efe7;
  --color-warning: #84691b;
  --color-warning-bg: #f7efd4;

  --color-mod-inicio: #1b3a4b;
  --color-mod-cobranzas: #305d4a;
  --color-mod-gastos: #c0443c;
  --color-mod-finanzas: #8a6d1c;
  --color-mod-expensas: #2c6473;
  --color-mod-operacion: #5b36b8;

  --wa: #25d366;

  --radius-sm: 12px;
  --radius: 16px;
  --radius-lg: 20px;
  --radius-pill: 999px;
  --shadow-md: 0 8px 24px rgba(18, 18, 18, 0.1);

  --font-sans: "Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-display: "Montserrat", var(--font-sans);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: var(--font-sans);
  font-size: 16px;
  font-weight: 400;
  color: var(--color-text);
  background: var(--color-bg);
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}

h1, h2, h3 {
  font-family: var(--font-display);
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -0.02em;
  margin: 0 0 0.5em;
}

p { margin: 0 0 1em; line-height: 1.6; }
a { color: inherit; }

.seccion {
  max-width: 1120px;
  margin: 0 auto;
  padding: 3.5rem 1.25rem;
}

@media (min-width: 600px) {
  .seccion { padding: 5rem 2rem; }
}

/* Micro-label uppercase del design system de la app */
.eyebrow {
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: var(--color-primary);
  margin: 0 0 0.75rem;
}

/* Botones */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-family: var(--font-sans);
  font-weight: 700;
  font-size: 0.95rem;
  text-decoration: none;
  border: 1px solid transparent;
  border-radius: var(--radius-pill);
  padding: 0.9rem 1.5rem;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s, color 0.2s;
  width: 100%;
}

.btn-primario { background: var(--color-primary); color: #fff; }
.btn-primario:hover { background: var(--color-primary-hover); }

.btn-wa { background: var(--wa); color: #06301a; }
.btn-wa:hover { background: #1fbb59; }
.btn-wa svg { flex-shrink: 0; }

@media (min-width: 600px) {
  .btn { width: auto; padding: 0.7rem 1.35rem; font-size: 0.9rem; }
}

/* ===== NAV ===== */
/* ===== HERO ===== */
/* ===== DOLORES ===== */
/* ===== SIMULADOR ===== */
/* ===== CTA-SIMULADOR ===== */
/* ===== CONSORCIO ===== */
/* ===== MODULOS ===== */
/* ===== PRECIOS ===== */
/* ===== CIERRE ===== */
/* ===== FOOTER ===== */
</style>
</head>
<body>

<!-- ===== NAV ===== -->
<!-- ===== HERO ===== -->
<!-- ===== DOLORES ===== -->
<!-- ===== SIMULADOR ===== -->
<!-- ===== CTA-SIMULADOR ===== -->
<!-- ===== CONSORCIO ===== -->
<!-- ===== MODULOS ===== -->
<!-- ===== PRECIOS ===== -->
<!-- ===== CIERRE ===== -->
<!-- ===== FOOTER ===== -->

<script>
const WHATSAPP = "5491178959108";

function linkWhatsApp(mensaje) {
  return "https://wa.me/" + WHATSAPP + "?text=" + encodeURIComponent(mensaje);
}

/* ===== HERO ===== */
/* ===== SIMULADOR ===== */
/* ===== CTA-SIMULADOR ===== */
/* ===== CIERRE ===== */
</script>
</body>
</html>
```

- [ ] **Step 3: Escribir la barra de navegación**

Reemplazar la línea `<!-- ===== NAV ===== -->` del `<body>` por el ancla seguida de la nav:

```html
<!-- ===== NAV ===== -->
<nav class="nav">
  <div class="nav-inner">
    <span class="nav-marca">Gestor Consorcios</span>
    <div class="nav-links">
      <a href="#simulador">Cómo funciona</a>
      <a href="#modulos">Módulos</a>
      <a href="#precios">Precios</a>
    </div>
    <a class="btn btn-primario nav-cta" href="https://consorciosdemo.vercel.app/" target="_blank" rel="noopener">Entrar al demo</a>
  </div>
</nav>
```

Y reemplazar la línea `/* ===== NAV ===== */` del `<style>` por:

```css
/* ===== NAV ===== */
.nav {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(244, 240, 230, 0.9);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--color-border);
}

.nav-inner {
  max-width: 1120px;
  margin: 0 auto;
  padding: 0.75rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.nav-marca {
  font-family: var(--font-display);
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--color-mod-inicio);
}

.nav-links { display: none; }

.nav-cta { width: auto; padding: 0.5rem 1rem; font-size: 0.82rem; }

@media (min-width: 600px) {
  .nav-inner { padding: 0.85rem 2rem; }
  .nav-links {
    display: flex;
    gap: 1.75rem;
    font-size: 0.9rem;
    font-weight: 600;
  }
  .nav-links a {
    color: var(--color-text-muted-strong);
    text-decoration: none;
  }
  .nav-links a:hover { color: var(--color-primary); }
}
```

- [ ] **Step 4: Escribir el footer**

Reemplazar la línea `<!-- ===== FOOTER ===== -->` del `<body>` por:

```html
<!-- ===== FOOTER ===== -->
<footer class="footer">
  <div class="footer-inner">
    <span class="footer-marca">Gestor Consorcios</span>
    <span class="footer-legal">Sistema de gestión para administradores de consorcios.</span>
  </div>
</footer>
```

Y la línea `/* ===== FOOTER ===== */` del `<style>` por:

```css
/* ===== FOOTER ===== */
.footer {
  border-top: 1px solid var(--color-border);
  background: var(--color-bg);
}

.footer-inner {
  max-width: 1120px;
  margin: 0 auto;
  padding: 2rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.footer-marca {
  font-family: var(--font-display);
  font-weight: 800;
  color: var(--color-mod-inicio);
}

.footer-legal { font-size: 0.85rem; color: var(--color-text-muted); }

@media (min-width: 600px) {
  .footer-inner {
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    padding: 2rem;
  }
}
```

- [ ] **Step 5: Verificar en browser**

Seguir el procedimiento de "Cómo se verifica cada tarea".

Observaciones esperadas a 1440x900:
- Fondo marfil `#f4f0e6` en toda la página.
- Nav pegada arriba con "Gestor Consorcios" a la izquierda en Montserrat 800, tres links al centro y el botón teal "Entrar al demo" a la derecha.
- Footer al pie con el borde superior.
- Entre nav y footer no hay nada (las secciones son anclas vacías todavía).

Observaciones esperadas a 375x812:
- Los tres links del centro **desaparecen** (`.nav-links { display: none }`), quedan solo marca y botón.
- Sin scroll horizontal.

- [ ] **Step 6: Commit**

```bash
git add index.html assets/.gitkeep
git commit -m "feat(landing): esqueleto, tokens de la app, nav y footer"
```

---

### Task 2: Hero con video y los dos CTAs

**Files:**
- Modify: `index.html` (anclas `HERO` en `<body>`, `<style>` y `<script>`)

**Interfaces:**
- Consumes: `.seccion`, `.btn`, `.btn-primario`, `.btn-wa`, `.eyebrow`, `linkWhatsApp(mensaje)` de la Task 1.
- Produces: el `id="simulador"` es el destino del CTA primario — la Task 4 debe ponerlo en su `<section>`. El SVG del glifo de WhatsApp definido acá se reutiliza literal en las Tasks 8 y 11.

- [ ] **Step 1: Escribir el markup del hero**

Reemplazar la línea `<!-- ===== HERO ===== -->` del `<body>` por:

```html
<!-- ===== HERO ===== -->
<header class="hero seccion">
  <div class="hero-texto">
    <p class="eyebrow">Para administradores de consorcios</p>
    <h1>Cerrás el mes con la duda de si los números cierran.</h1>
    <p class="hero-bajada">
      Cargás las facturas con su rubro, confirmás el cierre y salen las expensas
      de todas las unidades con el coeficiente aplicado. Cada pago que entra se
      imputa solo a la deuda más vieja. El saldo de una unidad es un solo número,
      lo mire quien lo mire.
    </p>
    <p class="hero-bajada hero-bajada-multi">
      Todos tus edificios en el mismo sistema, cada uno con sus coeficientes,
      sus proveedores y su encargado.
    </p>
    <div class="hero-acciones">
      <a class="btn btn-primario" href="#simulador">Ver cómo funciona</a>
      <a class="btn btn-wa" id="wa-hero" href="#" target="_blank" rel="noopener">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm0 18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.18 8.18 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.25-8.24 2.2 0 4.27.86 5.83 2.42a8.19 8.19 0 0 1 2.41 5.83c0 4.54-3.7 8.23-8.24 8.23Zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.24-.64.8-.78.97-.15.16-.29.18-.54.06-.25-.13-1.05-.39-1.99-1.23-.74-.66-1.24-1.47-1.38-1.72-.15-.25-.02-.38.11-.5.11-.11.25-.29.37-.44.13-.15.17-.25.25-.41.08-.17.04-.31-.02-.44-.06-.12-.56-1.35-.77-1.85-.2-.48-.4-.42-.56-.43h-.47c-.17 0-.44.06-.66.31-.23.25-.87.85-.87 2.07s.89 2.4 1.02 2.57c.12.16 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.47-.07 1.47-.6 1.68-1.18.21-.58.21-1.08.14-1.18-.06-.11-.22-.17-.47-.29Z"/></svg>
        Escribinos por WhatsApp
      </a>
    </div>
    <p class="hero-nota">Recorrelo sin registrarte. No pedimos tarjeta.</p>
  </div>

  <div class="hero-video">
    <video controls preload="none" poster="assets/demo-poster.jpg">
      <source src="assets/demo.mp4" type="video/mp4">
      Tu navegador no puede reproducir el video.
    </video>
  </div>
</header>
```

- [ ] **Step 2: Escribir el CSS del hero**

Reemplazar la línea `/* ===== HERO ===== */` del `<style>` por:

```css
/* ===== HERO ===== */
.hero {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  padding-top: 2.5rem;
}

.hero h1 { font-size: clamp(2rem, 7vw, 2.6rem); }

.hero-bajada {
  font-size: 1.02rem;
  color: var(--color-text-muted-strong);
  max-width: 46ch;
}

.hero-bajada-multi {
  font-weight: 600;
  color: var(--color-text);
}

.hero-acciones {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.hero-nota {
  font-size: 0.85rem;
  color: var(--color-text-muted);
  margin: 0;
}

.hero-video video {
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-strong);
  background: var(--color-mod-inicio);
  box-shadow: var(--shadow-md);
  display: block;
}

@media (min-width: 900px) {
  .hero {
    flex-direction: row;
    align-items: center;
    gap: 3.5rem;
    padding-top: 4rem;
  }
  .hero-texto { flex: 1 1 52%; }
  .hero-video { flex: 1 1 48%; }
  .hero h1 { font-size: 3.1rem; }
  .hero-acciones { flex-direction: row; flex-wrap: wrap; }
}
```

- [ ] **Step 3: Cablear el link de WhatsApp del hero**

Reemplazar la línea `/* ===== HERO ===== */` del `<script>` por:

```js
/* ===== HERO ===== */
document.getElementById("wa-hero").href = linkWhatsApp(
  "Hola! Vi la página de Gestor Consorcios y quiero saber más."
);
```

- [ ] **Step 4: Verificar en browser**

Observaciones esperadas a 1440x900:
- Dos columnas: texto a la izquierda, video a la derecha, alineados verticalmente al centro.
- Titular "Cerrás el mes con la duda de si los números cierran." en Montserrat 800 a ~3.1rem.
- Dos botones en una fila: teal "Ver cómo funciona" y verde `#25d366` "Escribinos por WhatsApp" con el glifo a la izquierda del texto.
- El video se ve como un rectángulo 16:9 azul oscuro con los controles nativos (el poster todavía no existe — es esperado).

Observaciones esperadas a 375x812:
- Una sola columna: texto arriba, video abajo.
- Los dos botones apilados y a ancho completo.
- Sin scroll horizontal.

Verificación adicional del link (en la consola del browser):

```js
document.getElementById("wa-hero").href
```

Esperado: `https://wa.me/5491178959108?text=Hola!%20Vi%20la%20p%C3%A1gina%20de%20Gestor%20Consorcios%20y%20quiero%20saber%20m%C3%A1s.`

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(landing): hero con video, CTA al simulador y CTA de WhatsApp"
```

---

### Task 3: Sección de los tres dolores

**Files:**
- Modify: `index.html` (anclas `DOLORES` en `<body>` y `<style>`)

**Interfaces:**
- Consumes: `.seccion`, `.eyebrow` de la Task 1.
- Produces: los links `href="#simulador"` con el texto "Velo en el paso N" apuntan a la sección que crea la Task 4.

- [ ] **Step 1: Escribir el markup**

Reemplazar la línea `<!-- ===== DOLORES ===== -->` del `<body>` por:

```html
<!-- ===== DOLORES ===== -->
<section class="seccion dolores">
  <p class="eyebrow">Lo que pasa hoy</p>
  <h2 class="dolores-titulo">Tres cosas que te comen la semana.</h2>

  <div class="dolores-grid">
    <article class="dolor" style="--acento: var(--color-mod-cobranzas);">
      <h3>Un pago parcial y ya no sabés cuánto debe la unidad.</h3>
      <p>
        Entran $120.000 de una unidad que arrastra tres expensas vencidas.
        ¿A cuál se lo imputás? La planilla dice una cosa, el recibo otra y el
        propietario una tercera.
      </p>
      <p class="dolor-respuesta">
        Acá el cobro se imputa solo a la deuda más antigua: mayo se salda entero,
        junio queda a la mitad, julio intacto. El saldo que ve el propietario en
        su portal es el mismo número que ves vos.
      </p>
      <a class="dolor-link" href="#simulador">Velo en el paso 3 →</a>
    </article>

    <article class="dolor" style="--acento: var(--color-mod-gastos);">
      <h3>El cierre de mes se te come tres días.</h3>
      <p>
        Prorratear a mano, rubro por rubro, coeficiente por coeficiente. Y si
        entró una factura tarde, empezás de nuevo.
      </p>
      <p class="dolor-respuesta">
        Cargás cada factura durante el mes con su rubro y su clase de prorrateo.
        El día del cierre mirás la vista previa con el total y la cantidad de
        boletas, confirmás, y salen las 24 expensas con el coeficiente aplicado.
      </p>
      <a class="dolor-link" href="#simulador">Velo en los pasos 1 y 2 →</a>
    </article>

    <article class="dolor" style="--acento: var(--color-mod-operacion);">
      <h3>Atendés el mismo llamado veinte veces.</h3>
      <p>
        "¿Cuánto debo?", "¿en qué se fue la plata este mes?", "¿está libre el SUM
        el sábado?". Siempre en el peor momento.
      </p>
      <p class="dolor-respuesta">
        El propietario entra con su usuario y ve su expensa, el detalle de gastos
        del mes, los comprobantes que presentó y la agenda del SUM. Reserva solo.
        Sin llamarte.
      </p>
      <a class="dolor-link" href="#simulador">Velo en el paso 4 →</a>
    </article>
  </div>
</section>
```

- [ ] **Step 2: Escribir el CSS**

Reemplazar la línea `/* ===== DOLORES ===== */` del `<style>` por:

```css
/* ===== DOLORES ===== */
.dolores { border-top: 1px solid var(--color-border); }

.dolores-titulo {
  font-size: clamp(1.6rem, 5.5vw, 2.1rem);
  max-width: 20ch;
  margin-bottom: 2.5rem;
}

.dolores-grid {
  display: grid;
  gap: 1.25rem;
}

.dolor {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-top: 4px solid var(--acento);
  border-radius: var(--radius);
  padding: 1.5rem;
}

.dolor h3 {
  font-size: 1.12rem;
  color: var(--acento);
  margin-bottom: 0.75rem;
}

.dolor p {
  font-size: 0.94rem;
  color: var(--color-text-muted-strong);
}

.dolor-respuesta {
  color: var(--color-text);
  font-weight: 600;
  border-top: 1px solid var(--color-border);
  padding-top: 0.9rem;
}

.dolor-link {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--acento);
  text-decoration: none;
}

.dolor-link:hover { text-decoration: underline; }

@media (min-width: 900px) {
  .dolores-grid { grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
}
```

- [ ] **Step 3: Verificar en browser**

Observaciones esperadas a 1440x900:
- Tres tarjetas blancas en una fila, cada una con una franja superior de 4px de color distinto: verde `#305d4a`, rojo `#c0443c` y violeta `#5b36b8`.
- El título de cada tarjeta toma el color de su franja.
- El párrafo de respuesta está separado por una línea y en peso 600.

Observaciones esperadas a 375x812:
- Las tres tarjetas apiladas, ancho completo de la columna, sin desbordar.

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat(landing): seccion de los tres dolores del administrador"
```

---

### Task 4: Simulador — shell, stepper y estado

**Files:**
- Modify: `index.html` (anclas `SIMULADOR` en `<body>`, `<style>` y `<script>`)

**Interfaces:**
- Consumes: `.seccion`, `.eyebrow` de la Task 1; el ancla `#simulador` que esperan las Tasks 2 y 3.
- Produces:
  - `<section id="simulador">` — destino de todos los links `#simulador`.
  - Objeto de estado `sim` con la forma exacta: `{ paso: 1, gastoCargado: false, periodoCerrado: false, pagoAplicado: null }` donde `pagoAplicado` es `null` o el monto numérico imputado.
  - `function irAPaso(n)` — cambia `sim.paso`, muestra el `<div class="sim-paso" data-paso="n">` correspondiente, actualiza el stepper y llama a `render()`.
  - `function render()` — vuelve a pintar todos los pasos según `sim`. Las Tasks 5-8 **agregan** su lógica dentro de `render()`, no crean funciones de render paralelas.
  - `function resetSim()` — devuelve `sim` a sus valores iniciales y llama a `irAPaso(1)`.
  - `function money(n)` — formatea a `$ 1.999.100` (es-AR, sin decimales). Las Tasks 5-8 la usan; ninguna define la suya.
  - Contenedores vacíos `<div class="sim-paso" data-paso="1|2|3|4">` que las Tasks 5, 6, 7 y 8 rellenan.

- [ ] **Step 1: Escribir el markup del shell**

Reemplazar la línea `<!-- ===== SIMULADOR ===== -->` del `<body>` por:

```html
<!-- ===== SIMULADOR ===== -->
<section class="seccion simulador" id="simulador">
  <p class="eyebrow">Probalo acá</p>
  <h2 class="sim-titulo">Un mes de trabajo, en cuatro pasos.</h2>
  <p class="sim-intro">
    Esto es el sistema de verdad, con las mismas pantallas. Tocá los botones:
    lo que hacés en un paso aparece en el siguiente.
  </p>

  <ol class="sim-stepper" id="sim-stepper">
    <li><button type="button" data-ir="1"><span>1</span> Cargar un gasto</button></li>
    <li><button type="button" data-ir="2"><span>2</span> Cerrar el período</button></li>
    <li><button type="button" data-ir="3"><span>3</span> Imputar un cobro</button></li>
    <li><button type="button" data-ir="4"><span>4</span> Lo ve el propietario</button></li>
  </ol>

  <div class="browser">
    <div class="browser-barra">
      <span class="browser-punto"></span>
      <span class="browser-punto"></span>
      <span class="browser-punto"></span>
      <span class="browser-url" id="sim-url">libertad.gestorconsorcios.app/gastos</span>
    </div>
    <div class="browser-cuerpo">
      <div class="app-topbar">
        <strong>Edificio Libertad</strong>
        <span class="app-chip">24 UF</span>
        <span class="app-rol" id="sim-rol">Administración</span>
      </div>
      <div class="app-cuerpo">
        <aside class="app-sidebar" id="sim-sidebar">
          <span class="app-sidebar-grupo">Finanzas</span>
          <button type="button" data-ir="1">Gastos</button>
          <button type="button" data-ir="2">Cierre de período</button>
          <button type="button" data-ir="3">Cuentas corrientes</button>
          <span class="app-sidebar-grupo">Portal</span>
          <button type="button" data-ir="4">Mi cuenta</button>
        </aside>
        <main class="app-main">
          <div class="sim-paso" data-paso="1"></div>
          <div class="sim-paso" data-paso="2" hidden></div>
          <div class="sim-paso" data-paso="3" hidden></div>
          <div class="sim-paso" data-paso="4" hidden></div>
        </main>
      </div>
    </div>
  </div>

  <div class="sim-pie">
    <p class="sim-nota" id="sim-nota">Empezá cargando la factura del mes.</p>
    <div class="sim-controles">
      <button type="button" class="btn btn-ghost" id="sim-reset">Reiniciar</button>
      <button type="button" class="btn btn-primario" id="sim-siguiente">Siguiente paso →</button>
    </div>
  </div>
</section>
```

- [ ] **Step 2: Escribir el CSS del shell**

Reemplazar la línea `/* ===== SIMULADOR ===== */` del `<style>` por:

```css
/* ===== SIMULADOR ===== */
.simulador { border-top: 1px solid var(--color-border); }

.sim-titulo { font-size: clamp(1.6rem, 5.5vw, 2.1rem); }

.sim-intro {
  max-width: 52ch;
  color: var(--color-text-muted-strong);
  margin-bottom: 1.75rem;
}

.sim-stepper {
  list-style: none;
  display: flex;
  gap: 0.5rem;
  padding: 0;
  margin: 0 0 1rem;
  overflow-x: auto;
  scrollbar-width: none;
}

.sim-stepper::-webkit-scrollbar { display: none; }

.sim-stepper button {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  white-space: nowrap;
  font-family: var(--font-sans);
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--color-text-muted-strong);
  background: transparent;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-pill);
  padding: 0.45rem 0.9rem;
  cursor: pointer;
}

.sim-stepper button span {
  display: grid;
  place-items: center;
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  background: var(--color-border);
  font-size: 0.72rem;
}

.sim-stepper button[aria-current="step"] {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.sim-stepper button[aria-current="step"] span {
  background: rgba(255, 255, 255, 0.25);
}

/* Frame de browser */
.browser {
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow-md);
  background: var(--color-surface);
}

.browser-barra {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.5rem 0.75rem;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}

.browser-punto {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 50%;
  background: var(--color-border-strong);
}

.browser-url {
  margin-left: 0.5rem;
  font-size: 0.68rem;
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.browser-cuerpo { display: flex; flex-direction: column; }

.app-topbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
  font-size: 0.75rem;
}

.app-chip {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 700;
  font-size: 0.66rem;
  padding: 0.1rem 0.4rem;
  border-radius: var(--radius-pill);
}

.app-rol {
  margin-left: auto;
  background: var(--color-success-bg);
  color: var(--color-success);
  font-weight: 700;
  font-size: 0.66rem;
  padding: 0.1rem 0.4rem;
  border-radius: var(--radius-pill);
}

.app-cuerpo { display: flex; min-height: 420px; }

.app-sidebar {
  display: none;
  width: 168px;
  flex-shrink: 0;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.75rem 0.5rem;
  background: var(--color-bg);
  border-right: 1px solid var(--color-border);
}

.app-sidebar-grupo {
  font-size: 0.6rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--color-text-muted);
  padding: 0.5rem 0.5rem 0.25rem;
}

.app-sidebar button {
  text-align: left;
  font-family: var(--font-sans);
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--color-text);
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  padding: 0.4rem 0.5rem;
  cursor: pointer;
}

.app-sidebar button:hover { background: var(--color-primary-soft); }

.app-sidebar button[aria-current="page"] {
  background: var(--color-primary);
  color: #fff;
}

.app-main {
  flex: 1;
  min-width: 0;
  padding: 1rem;
  overflow-x: auto;
}

.sim-pie {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1.25rem;
}

.sim-nota {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-radius: var(--radius-sm);
  padding: 0.75rem 1rem;
}

.sim-controles { display: flex; flex-direction: column; gap: 0.6rem; }

.btn-ghost {
  background: transparent;
  border-color: var(--color-border-strong);
  color: var(--color-text-muted-strong);
}

.btn-ghost:hover { border-color: var(--color-primary); color: var(--color-primary); }

@media (min-width: 600px) {
  .app-sidebar { display: flex; }
  .app-main { padding: 1.25rem; }
  .sim-pie { flex-direction: row; align-items: center; justify-content: space-between; }
  .sim-controles { flex-direction: row; }
}
```

- [ ] **Step 3: Escribir el estado y la navegación**

Reemplazar la línea `/* ===== SIMULADOR ===== */` del `<script>` por:

```js
/* ===== SIMULADOR ===== */
const sim = {
  paso: 1,
  gastoCargado: false,
  periodoCerrado: false,
  pagoAplicado: null,
};

const SIM_URLS = {
  1: "libertad.gestorconsorcios.app/gastos",
  2: "libertad.gestorconsorcios.app/cierre-de-periodo",
  3: "libertad.gestorconsorcios.app/departamentos/2A/cuenta",
  4: "libertad.gestorconsorcios.app/mi-cuenta",
};

const SIM_ROLES = { 1: "Administración", 2: "Administración", 3: "Administración", 4: "Propietario" };

const SIM_NOTAS_BASE = {
  1: "Empezá cargando la factura del mes.",
  2: "Mirá la vista previa antes de confirmar. Nada se emite hasta que lo confirmás vos.",
  3: "La unidad 2A arrastra tres expensas vencidas. Elegí cuánto paga.",
  4: "Esto es lo que ve el propietario cuando entra con su usuario.",
};

function money(n) {
  return "$ " + Math.round(n).toLocaleString("es-AR");
}

function nota(texto) {
  document.getElementById("sim-nota").textContent = texto;
}

function irAPaso(n) {
  sim.paso = n;

  document.querySelectorAll(".sim-paso").forEach((el) => {
    el.hidden = Number(el.dataset.paso) !== n;
  });

  document.querySelectorAll("#sim-stepper button").forEach((b) => {
    if (Number(b.dataset.ir) === n) b.setAttribute("aria-current", "step");
    else b.removeAttribute("aria-current");
  });

  document.querySelectorAll("#sim-sidebar button").forEach((b) => {
    if (Number(b.dataset.ir) === n) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });

  document.getElementById("sim-url").textContent = SIM_URLS[n];
  document.getElementById("sim-rol").textContent = SIM_ROLES[n];
  document.getElementById("sim-siguiente").hidden = n === 4;
  nota(SIM_NOTAS_BASE[n]);
  render();
}

function render() {
  /* Las Tasks 5-8 agregan acá su lógica de pintado. */
}

function resetSim() {
  sim.gastoCargado = false;
  sim.periodoCerrado = false;
  sim.pagoAplicado = null;
  irAPaso(1);
}

document.querySelectorAll("[data-ir]").forEach((b) => {
  b.addEventListener("click", () => irAPaso(Number(b.dataset.ir)));
});

document.getElementById("sim-reset").addEventListener("click", resetSim);

document.getElementById("sim-siguiente").addEventListener("click", () => {
  if (sim.paso < 4) irAPaso(sim.paso + 1);
});

irAPaso(1);
```

- [ ] **Step 4: Verificar en browser**

Observaciones esperadas a 1440x900:
- Frame de browser con tres puntos grises y la URL `libertad.gestorconsorcios.app/gastos`.
- Topbar con "Edificio Libertad", el chip "24 UF" y a la derecha el badge verde "Administración".
- Sidebar con el grupo "Finanzas" (Gastos, Cierre de período, Cuentas corrientes) y "Portal" (Mi cuenta). "Gastos" está resaltado en teal.
- El stepper tiene el paso 1 en teal y los otros tres en ghost.
- El área principal está vacía (las Tasks 5-8 la llenan).

Comprobación de la máquina de estados, click por click:
1. Click en "Siguiente paso →" → el stepper marca el 2, la URL cambia a `/cierre-de-periodo`, el sidebar resalta "Cierre de período".
2. Click de nuevo → paso 3, URL `/departamentos/2A/cuenta`.
3. Click de nuevo → paso 4, URL `/mi-cuenta`, el badge del rol dice **"Propietario"** y el botón "Siguiente paso" **desaparece**.
4. Click en "Reiniciar" → vuelve al paso 1 con el badge en "Administración" y el botón "Siguiente" visible otra vez.
5. Click en "Cuentas corrientes" del sidebar → salta directo al paso 3.

Observaciones esperadas a 375x812:
- El sidebar **desaparece** (`display: none` bajo 600px).
- El stepper scrollea horizontalmente **dentro de sí mismo**, sin generar scroll en `<body>`.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(landing): shell del simulador con frame de browser, stepper y estado"
```

---

### Task 5: Simulador paso 1 — cargar el gasto

**Files:**
- Modify: `index.html` (`<div class="sim-paso" data-paso="1">`, ancla `SIMULADOR` en `<style>` y función `render()`)

**Interfaces:**
- Consumes: `sim`, `render()`, `irAPaso(n)`, `money(n)`, `nota(texto)` de la Task 4.
- Produces: `sim.gastoCargado` pasa a `true` cuando el visitante guarda. La Task 6 lee ese flag para decidir el total del preview.

La pantalla replica `frontend/src/screens/Gastos.jsx`: **lista de tarjetas, no tabla**. Cada tarjeta tiene `h3` con `Rubro · Concepto` y líneas `meta` con monto, período, proveedor, clase y caja.

- [ ] **Step 1: Escribir el markup del paso 1**

Reemplazar `<div class="sim-paso" data-paso="1"></div>` por:

```html
<div class="sim-paso" data-paso="1">
  <div class="pantalla-head">
    <h3 class="pantalla-titulo">Gastos</h3>
    <span class="pantalla-meta">Período 2026-08 · total <strong id="g-total">$ 1.519.100</strong></span>
  </div>

  <form class="gasto-form" id="gasto-form">
    <div class="campo">
      <label for="g-rubro">Rubro</label>
      <select id="g-rubro">
        <option value="abonos_y_servicios" selected>Abonos y servicios</option>
        <option value="mantenimiento_partes_comunes">Mantenimiento partes comunes</option>
        <option value="servicios_publicos">Servicios públicos</option>
        <option value="seguros">Seguros</option>
      </select>
    </div>
    <div class="campo">
      <label for="g-concepto">Concepto</label>
      <input id="g-concepto" type="text" value="Abono mensual de ascensores" readonly>
    </div>
    <div class="campo">
      <label for="g-monto">Monto</label>
      <input id="g-monto" type="text" value="480000" readonly>
    </div>
    <div class="campo">
      <label for="g-clase">Clase de prorrateo</label>
      <select id="g-clase">
        <option selected>A — Expensas ordinarias</option>
        <option>B — Expensas extraordinarias</option>
        <option>C — Servicios diferenciados</option>
      </select>
    </div>
    <button type="submit" class="btn btn-primario btn-sm" id="g-guardar">Guardar gasto</button>
  </form>

  <p class="pantalla-tip">
    Fijate que no elegís a quién cobrarle: elegís la <strong>clase de prorrateo</strong>.
    El coeficiente de cada unidad hace el resto en el cierre.
  </p>

  <ul class="lista-gastos" id="lista-gastos">
    <li class="tarjeta tarjeta-nueva" id="g-nuevo" hidden>
      <h4>Abonos y servicios · Abono mensual de ascensores</h4>
      <p class="meta">$ 480.000 · 2026-08 · pagó 05/08/2026</p>
      <p class="meta">Proveedor: Ascensores Del Plata</p>
      <p class="meta">Clase A — Expensas ordinarias</p>
      <p class="meta">Caja: Banco Nación cta. cte.</p>
    </li>
    <li class="tarjeta">
      <h4>Sueldos y cargas sociales · Sueldo encargado agosto</h4>
      <p class="meta">$ 1.240.000 · 2026-08 · pagó 04/08/2026</p>
      <p class="meta">Clase A — Expensas ordinarias</p>
      <p class="meta">Caja: Banco Nación cta. cte.</p>
    </li>
    <li class="tarjeta">
      <h4>Servicios públicos · Luz de partes comunes</h4>
      <p class="meta">$ 186.400 · 2026-08 · pagó 03/08/2026</p>
      <p class="meta">Proveedor: Edenor</p>
      <p class="meta">Clase A — Expensas ordinarias</p>
      <p class="meta">Caja: Banco Nación cta. cte.</p>
    </li>
    <li class="tarjeta">
      <h4>Seguros · Póliza integral del consorcio</h4>
      <p class="meta">$ 92.700 · 2026-08 · pagó 02/08/2026</p>
      <p class="meta">Proveedor: Sancor Seguros</p>
      <p class="meta">Clase A — Expensas ordinarias</p>
      <p class="meta">Caja: Banco Nación cta. cte.</p>
    </li>
  </ul>
</div>
```

- [ ] **Step 2: Escribir el CSS de pantalla**

Agregar al final del bloque `/* ===== SIMULADOR ===== */` del `<style>` (antes del ancla siguiente):

```css
/* Pantallas del simulador */
.pantalla-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 0.85rem;
  margin-bottom: 1rem;
}

.pantalla-titulo { font-size: 1.05rem; margin: 0; }

.pantalla-meta { font-size: 0.78rem; color: var(--color-text-muted); }

.pantalla-tip {
  font-size: 0.8rem;
  color: var(--color-text-muted-strong);
  background: var(--color-warning-bg);
  border-left: 3px solid var(--color-warning);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  padding: 0.6rem 0.8rem;
  margin: 0 0 1rem;
}

.gasto-form {
  display: grid;
  gap: 0.7rem;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.9rem;
  margin-bottom: 1rem;
}

.campo { display: flex; flex-direction: column; gap: 0.2rem; }

.campo label {
  font-size: 0.66rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--color-text-muted);
}

.campo input, .campo select {
  font-family: var(--font-sans);
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 0.4rem 0.55rem;
  width: 100%;
}

.btn-sm { padding: 0.5rem 1rem; font-size: 0.82rem; width: fit-content; }

.lista-gastos { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.6rem; }

.tarjeta {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.75rem 0.9rem;
}

.tarjeta h4 {
  font-family: var(--font-display);
  font-size: 0.85rem;
  font-weight: 800;
  margin: 0 0 0.35rem;
}

.tarjeta .meta {
  font-size: 0.74rem;
  color: var(--color-text-muted);
  margin: 0 0 0.1rem;
}

.tarjeta-nueva {
  border-color: var(--color-success);
  background: var(--color-success-bg);
  animation: aparecer 0.4s ease;
}

@keyframes aparecer {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: none; }
}

@media (min-width: 600px) {
  .gasto-form { grid-template-columns: repeat(2, 1fr); }
  .gasto-form button { grid-column: 1 / -1; }
}
```

- [ ] **Step 3: Cablear la lógica del paso 1**

Reemplazar el cuerpo de `render()` por (conservando el comentario para las tareas siguientes):

```js
function render() {
  /* Paso 1 */
  document.getElementById("g-nuevo").hidden = !sim.gastoCargado;
  document.getElementById("g-total").textContent = money(sim.gastoCargado ? 1999100 : 1519100);
  document.getElementById("g-guardar").disabled = sim.gastoCargado;
  document.getElementById("g-guardar").textContent = sim.gastoCargado ? "Gasto guardado ✓" : "Guardar gasto";

  /* Las Tasks 6-8 agregan acá su lógica de pintado. */
}

document.getElementById("gasto-form").addEventListener("submit", (e) => {
  e.preventDefault();
  if (sim.gastoCargado) return;
  sim.gastoCargado = true;
  render();
  nota("El abono entró a la clase A. El total del período pasó de $ 1.519.100 a $ 1.999.100. Ahora cerrá el mes.");
});
```

- [ ] **Step 4: Verificar en browser**

Observaciones esperadas a 1440x900, en el paso 1:
- Encabezado "Gastos" con "Período 2026-08 · total **$ 1.519.100**".
- Formulario en dos columnas con Rubro / Concepto / Monto / Clase de prorrateo y el botón "Guardar gasto" abajo, con ancho de su contenido (no estirado).
- Cartel amarillo con el tip sobre la clase de prorrateo.
- Tres tarjetas: sueldo encargado, luz y seguro.

Al hacer click en "Guardar gasto":
- Aparece arriba de todo una cuarta tarjeta con fondo verde `#e3efe7`: "Abonos y servicios · Abono mensual de ascensores" con "$ 480.000 · 2026-08 · pagó 05/08/2026".
- El total del encabezado cambia a **$ 1.999.100**.
- El botón queda deshabilitado y dice "Gasto guardado ✓".
- El cartel de nota bajo el frame dice "El abono entró a la clase A. El total del período pasó de $ 1.519.100 a $ 1.999.100. Ahora cerrá el mes."

Al hacer click en "Reiniciar": el total vuelve a $ 1.519.100, la tarjeta verde desaparece y el botón se rehabilita.

Observaciones esperadas a 375x812: el formulario pasa a una sola columna y las tarjetas no desbordan.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(landing): paso 1 del simulador, carga de gasto con clase de prorrateo"
```

---

### Task 6: Simulador paso 2 — cerrar el período

**Files:**
- Modify: `index.html` (`<div class="sim-paso" data-paso="2">`, ancla `SIMULADOR` en `<style>` y función `render()`)

**Interfaces:**
- Consumes: `sim`, `render()`, `money(n)`, `nota(texto)` de la Task 4; `sim.gastoCargado` de la Task 5.
- Produces: `sim.periodoCerrado` pasa a `true` al confirmar. La Task 7 lo lee para mostrar (o no) la expensa de agosto en la cuenta corriente.

Replica `frontend/src/screens/CierreDePeriodo.jsx`, que es un flujo de **dos clicks**: lista de validaciones → "Generar preview" → vista previa con `Total a expensar · Boletas · Intereses` → "Confirmar cierre".

- [ ] **Step 1: Escribir el markup del paso 2**

Reemplazar `<div class="sim-paso" data-paso="2" hidden></div>` por:

```html
<div class="sim-paso" data-paso="2" hidden>
  <div class="pantalla-head">
    <h3 class="pantalla-titulo">Cierre de período</h3>
    <span class="pantalla-meta">Período 2026-08</span>
  </div>

  <div class="cierre-bloque" id="cierre-estado">
    <h4>Estado de 2026-08</h4>
    <ul class="lista-validaciones">
      <li class="val-ok">✓ Los 24 coeficientes suman 100 %.</li>
      <li class="val-ok">✓ Todos los gastos del período tienen clase o unidad asignada.</li>
      <li class="val-aviso" id="val-gasto">⚠ Hay un gasto del mes sin cargar.</li>
    </ul>
    <button type="button" class="btn btn-primario btn-sm" id="c-preview">Generar preview</button>
  </div>

  <div class="cierre-bloque" id="cierre-preview" hidden>
    <h4>Vista previa de cierre — 2026-08</h4>
    <div class="cierre-cifras">
      <span>Total a expensar <strong id="c-total">$ 1.999.100</strong></span>
      <span>Boletas <strong>24</strong></span>
      <span>Intereses <strong>$ 18.430</strong></span>
    </div>
    <div class="tabla-scroll">
      <table class="tabla">
        <thead>
          <tr><th>Unidad</th><th>Ubicación</th><th class="num">Coef.</th><th class="num">Monto</th></tr>
        </thead>
        <tbody>
          <tr><td class="col-unidad">1A</td><td>Piso 1, letra A</td><td class="num">3,90 %</td><td class="num">$ 77.965</td></tr>
          <tr><td class="col-unidad">1B</td><td>Piso 1, letra B</td><td class="num">3,90 %</td><td class="num">$ 77.965</td></tr>
          <tr class="fila-destacada"><td class="col-unidad">2A</td><td>Piso 2, letra A</td><td class="num">4,15 %</td><td class="num">$ 82.963</td></tr>
          <tr><td class="col-unidad">2B</td><td>Piso 2, letra B</td><td class="num">4,15 %</td><td class="num">$ 82.963</td></tr>
          <tr><td class="col-unidad">3A</td><td>Piso 3, letra A</td><td class="num">4,40 %</td><td class="num">$ 87.960</td></tr>
          <tr><td class="col-unidad">3B</td><td>Piso 3, letra B</td><td class="num">4,40 %</td><td class="num">$ 87.960</td></tr>
        </tbody>
      </table>
    </div>
    <p class="pantalla-meta">…y 18 unidades más.</p>
    <p class="pantalla-tip" id="c-trazo">
      Los $ 480.000 del abono de ascensores están repartidos acá adentro: a la 2A
      le tocaron $ 19.920 por su 4,15 %.
    </p>
    <button type="button" class="btn btn-primario btn-sm" id="c-confirmar">Confirmar cierre</button>
  </div>

  <div class="cierre-bloque cierre-ok" id="cierre-hecho" hidden>
    <h4>✓ Período 2026-08 cerrado</h4>
    <p class="meta">Se emitieron 24 expensas por $ 1.999.100. Cada propietario ya la tiene en su portal.</p>
  </div>
</div>
```

- [ ] **Step 2: Escribir el CSS**

Agregar al final del bloque `/* ===== SIMULADOR ===== */` del `<style>`:

```css
.cierre-bloque {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 1rem;
  margin-bottom: 1rem;
}

.cierre-bloque h4 {
  font-family: var(--font-display);
  font-size: 0.92rem;
  font-weight: 800;
  margin: 0 0 0.7rem;
}

.lista-validaciones {
  list-style: none;
  margin: 0 0 0.9rem;
  padding: 0;
  display: grid;
  gap: 0.3rem;
  font-size: 0.8rem;
}

.val-ok { color: var(--color-success); font-weight: 600; }
.val-aviso { color: var(--color-warning); font-weight: 600; }

.cierre-cifras {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 1.5rem;
  font-size: 0.78rem;
  color: var(--color-text-muted);
  margin-bottom: 0.9rem;
}

.cierre-cifras strong {
  display: block;
  font-family: var(--font-display);
  font-size: 1.05rem;
  color: var(--color-text);
}

.tabla-scroll { overflow-x: auto; margin-bottom: 0.5rem; }

.tabla {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
  white-space: nowrap;
}

.tabla th {
  text-align: left;
  font-size: 0.64rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--color-text-muted);
  border-bottom: 1px solid var(--color-border-strong);
  padding: 0.4rem 0.5rem;
}

.tabla td {
  border-bottom: 1px solid var(--color-border);
  padding: 0.45rem 0.5rem;
}

.tabla .num { text-align: right; }
.tabla .col-unidad { font-weight: 800; color: var(--color-primary); }

.fila-destacada { background: var(--color-primary-soft); }

.cierre-ok {
  border-color: var(--color-success);
  background: var(--color-success-bg);
}

.cierre-ok h4 { color: var(--color-success); }
.cierre-ok .meta { font-size: 0.8rem; color: var(--color-text-muted-strong); margin: 0; }
```

- [ ] **Step 3: Cablear la lógica del paso 2**

Dentro de `render()`, reemplazar el comentario `/* Las Tasks 6-8 agregan acá su lógica de pintado. */` por:

```js
  /* Paso 2 */
  document.getElementById("val-gasto").hidden = sim.gastoCargado;
  document.getElementById("c-total").textContent = money(sim.gastoCargado ? 1999100 : 1519100);
  document.getElementById("c-trazo").hidden = !sim.gastoCargado;
  document.getElementById("cierre-hecho").hidden = !sim.periodoCerrado;
  document.getElementById("c-confirmar").disabled = sim.periodoCerrado;

  /* Las Tasks 7-8 agregan acá su lógica de pintado. */
```

Y agregar, después del listener del formulario de gastos:

```js
document.getElementById("c-preview").addEventListener("click", () => {
  document.getElementById("cierre-estado").hidden = true;
  document.getElementById("cierre-preview").hidden = false;
  nota("Esto es solo una vista previa: todavía no se emitió nada. Revisá el total y confirmá.");
});

document.getElementById("c-confirmar").addEventListener("click", () => {
  sim.periodoCerrado = true;
  document.getElementById("cierre-preview").hidden = true;
  render();
  nota("24 expensas emitidas. Ahora mirá qué pasa cuando una unidad que debe hace un pago.");
});
```

Y en `resetSim()`, antes de `irAPaso(1)`, agregar el reseteo visual de los tres bloques:

```js
  document.getElementById("cierre-estado").hidden = false;
  document.getElementById("cierre-preview").hidden = true;
```

- [ ] **Step 4: Verificar en browser**

Recorrido esperado (arrancando desde "Reiniciar"):
1. Paso 1 → click "Guardar gasto" → click "Siguiente paso →".
2. En el paso 2 se ve "Estado de 2026-08" con dos validaciones verdes y **sin** el aviso amarillo (porque el gasto ya se cargó).
3. Click en "Generar preview" → el bloque de estado se oculta y aparece la vista previa con "Total a expensar **$ 1.999.100**", "Boletas **24**", "Intereses **$ 18.430**".
4. La tabla muestra 6 filas con la de **2A resaltada** en `--color-primary-soft`.
5. El cartel amarillo dice que los $ 480.000 del ascensor están repartidos ahí adentro. **Esta es la conexión con el paso 1 — si no se ve, la tarea está incompleta.**
6. Click en "Confirmar cierre" → aparece el bloque verde "✓ Período 2026-08 cerrado" y la nota dice "24 expensas emitidas…".

Recorrido alternativo (sin cargar el gasto):
1. "Reiniciar" → ir directo al paso 2 desde el stepper.
2. Se ve el aviso amarillo "⚠ Hay un gasto del mes sin cargar".
3. "Generar preview" muestra total **$ 1.519.100** y **sin** el cartel del ascensor.

A 375x812: la tabla scrollea horizontalmente **dentro de `.tabla-scroll`**, sin mover el `<body>`.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(landing): paso 2 del simulador, preview y confirmacion del cierre"
```

---

### Task 7: Simulador paso 3 — imputación FIFO del cobro

**Files:**
- Modify: `index.html` (`<div class="sim-paso" data-paso="3">`, ancla `SIMULADOR` en `<style>` y función `render()`)

**Interfaces:**
- Consumes: `sim`, `render()`, `money(n)`, `nota(texto)` de la Task 4; `sim.periodoCerrado` de la Task 6.
- Produces: `sim.pagoAplicado` (número o `null`). La Task 8 lo usa para calcular el saldo del portal.
- Produces: `function deudaUF2A()` → devuelve `{ filas, saldo }`, donde `filas` es un array de `{ periodo, monto, pagado, estado }` con `estado` en `"saldada" | "parcial" | "impaga"`, y `saldo` es el número total adeudado. La Task 8 la llama para el resumen del propietario.

- [ ] **Step 1: Escribir el markup del paso 3**

Reemplazar `<div class="sim-paso" data-paso="3" hidden></div>` por:

```html
<div class="sim-paso" data-paso="3" hidden>
  <div class="pantalla-head">
    <h3 class="pantalla-titulo">Cuenta corriente · 2A</h3>
    <span class="pantalla-meta">Piso 2, letra A · Carlos G.</span>
  </div>

  <div class="cc-saldo">
    <span>Saldo</span>
    <strong id="cc-saldo">$ 320.463</strong>
    <span class="estado-badge" id="cc-estado"><span class="estado-punto"></span>En mora</span>
  </div>

  <div class="tabla-scroll">
    <table class="tabla" id="cc-tabla">
      <thead>
        <tr><th>Período</th><th>Concepto</th><th class="num">Monto</th><th class="num">Imputado</th><th>Estado</th></tr>
      </thead>
      <tbody id="cc-filas"></tbody>
    </table>
  </div>

  <div class="cc-cobro">
    <span class="cc-cobro-label">Registrar un pago de</span>
    <div class="cc-montos">
      <button type="button" class="btn btn-ghost btn-sm" data-pago="74200">$ 74.200</button>
      <button type="button" class="btn btn-primario btn-sm" data-pago="120000">$ 120.000</button>
      <button type="button" class="btn btn-ghost btn-sm" data-pago="320463">$ 320.463</button>
    </div>
  </div>

  <p class="pantalla-tip">
    No elegís a qué expensa se imputa. El pago entra y salda la deuda más vieja
    primero — el resto queda a cuenta de la siguiente.
  </p>
</div>
```

- [ ] **Step 2: Escribir el CSS**

Agregar al final del bloque `/* ===== SIMULADOR ===== */` del `<style>`:

```css
.cc-saldo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.75rem 0.9rem;
  margin-bottom: 1rem;
  font-size: 0.78rem;
  color: var(--color-text-muted);
}

.cc-saldo strong {
  font-family: var(--font-display);
  font-size: 1.35rem;
  color: var(--color-danger);
  transition: color 0.3s;
}

.estado-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--color-text-muted-strong);
}

.estado-punto {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background: var(--color-danger);
}

.cc-cobro {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 1rem 0;
}

.cc-cobro-label {
  font-size: 0.66rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--color-text-muted);
}

.cc-montos { display: flex; flex-wrap: wrap; gap: 0.5rem; }

.fila-saldada { background: var(--color-success-bg); }
.fila-parcial { background: var(--color-warning-bg); }

.pill {
  font-size: 0.66rem;
  font-weight: 800;
  border-radius: var(--radius-pill);
  padding: 0.1rem 0.45rem;
}

.pill-saldada { background: var(--color-success); color: #fff; }
.pill-parcial { background: var(--color-warning); color: #fff; }
.pill-impaga { background: var(--color-danger-bg); color: var(--color-danger); }

@keyframes imputar {
  from { background: var(--color-primary-soft); }
}

.fila-animada { animation: imputar 0.9s ease; }
```

- [ ] **Step 3: Cablear la lógica FIFO**

Agregar, después de los listeners del paso 2:

```js
const EXPENSAS_2A = [
  { periodo: "2026-05", monto: 74200 },
  { periodo: "2026-06", monto: 79800 },
  { periodo: "2026-07", monto: 83500 },
  { periodo: "2026-08", monto: 82963, requiereCierre: true },
];

function deudaUF2A() {
  let restante = sim.pagoAplicado || 0;
  const filas = [];
  let saldo = 0;

  for (const e of EXPENSAS_2A) {
    if (e.requiereCierre && !sim.periodoCerrado) continue;
    const pagado = Math.min(restante, e.monto);
    restante -= pagado;
    saldo += e.monto - pagado;
    const estado = pagado >= e.monto ? "saldada" : pagado > 0 ? "parcial" : "impaga";
    filas.push({ periodo: e.periodo, monto: e.monto, pagado, estado });
  }
  return { filas, saldo };
}

const PILL_LABEL = { saldada: "Saldada", parcial: "Parcial", impaga: "Impaga" };

function pintarCuentaCorriente() {
  const { filas, saldo } = deudaUF2A();

  document.getElementById("cc-filas").innerHTML = filas
    .map((f) => {
      const clase = f.estado === "saldada" ? "fila-saldada" : f.estado === "parcial" ? "fila-parcial" : "";
      const animar = sim.pagoAplicado && f.estado !== "impaga" ? " fila-animada" : "";
      return (
        '<tr class="' + clase + animar + '">' +
        "<td>" + f.periodo + "</td>" +
        "<td>Expensa emitida</td>" +
        '<td class="num">' + money(f.monto) + "</td>" +
        '<td class="num">' + money(f.pagado) + "</td>" +
        '<td><span class="pill pill-' + f.estado + '">' + PILL_LABEL[f.estado] + "</span></td>" +
        "</tr>"
      );
    })
    .join("");

  const saldoEl = document.getElementById("cc-saldo");
  saldoEl.textContent = money(saldo);
  saldoEl.style.color = saldo > 0 ? "var(--color-danger)" : "var(--color-success)";

  const estadoEl = document.getElementById("cc-estado");
  estadoEl.innerHTML =
    '<span class="estado-punto" style="background:' +
    (saldo > 0 ? "var(--color-danger)" : "var(--color-success)") +
    '"></span>' + (saldo > 0 ? "En mora" : "Al día");

  document.querySelectorAll("[data-pago]").forEach((b) => {
    b.disabled = sim.pagoAplicado !== null;
  });
}

document.querySelectorAll("[data-pago]").forEach((b) => {
  b.addEventListener("click", () => {
    sim.pagoAplicado = Number(b.dataset.pago);
    render();
    const { saldo } = deudaUF2A();
    nota(
      "Se imputó " + money(sim.pagoAplicado) +
      " arrancando por la deuda más vieja. Saldo de la unidad: " + money(saldo) +
      ". Ahora mirá lo mismo desde el lado del propietario."
    );
  });
});
```

Dentro de `render()`, reemplazar el comentario `/* Las Tasks 7-8 agregan acá su lógica de pintado. */` por:

```js
  /* Paso 3 */
  pintarCuentaCorriente();

  /* La Task 8 agrega acá su lógica de pintado. */
```

- [ ] **Step 4: Verificar en browser**

Recorrido esperado completo (desde "Reiniciar"):
1. Guardar gasto → Siguiente → Generar preview → Confirmar cierre → Siguiente.
2. En el paso 3 la tabla tiene **4 filas**: 2026-05, 06, 07 y **2026-08 por $ 82.963** (esta última solo aparece porque cerraste el período — ese es el rastro del paso 2).
3. Saldo en rojo: **$ 320.463**, badge "En mora".
4. Click en **$ 120.000**:
   - Fila 2026-05 con fondo verde, Imputado `$ 74.200`, pill "Saldada".
   - Fila 2026-06 con fondo amarillo, Imputado `$ 45.800`, pill "Parcial".
   - Filas 2026-07 y 2026-08 sin fondo, Imputado `$ 0`, pill "Impaga".
   - Saldo pasa a **$ 200.463**.
   - Los tres botones de monto quedan deshabilitados.
   - La nota dice "Se imputó $ 120.000 arrancando por la deuda más vieja. Saldo de la unidad: $ 200.463…".
5. Click en **$ 320.463** tras un "Reiniciar" y rehacer el recorrido: las 4 filas quedan verdes, saldo **$ 0** en verde y el badge dice "Al día".

Recorrido alternativo: "Reiniciar" → ir al paso 3 desde el sidebar sin cerrar el período. La tabla tiene **3 filas** (no está agosto) y el saldo es **$ 237.500**.

A 375x812: la tabla scrollea dentro de su contenedor; los tres botones de monto se envuelven en varias líneas sin desbordar.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(landing): paso 3 del simulador, imputacion FIFO del cobro"
```

---

### Task 8: Simulador paso 4 (portal) y CTA de WhatsApp

**Files:**
- Modify: `index.html` (`<div class="sim-paso" data-paso="4">`, anclas `SIMULADOR` y `CTA-SIMULADOR` en `<body>`, `<style>` y `<script>`)

**Interfaces:**
- Consumes: `sim`, `render()`, `money(n)` de la Task 4; `deudaUF2A()` de la Task 7; `linkWhatsApp(mensaje)` y el SVG de WhatsApp de la Task 2.
- Produces: nada que consuman tareas posteriores.

Replica `frontend/src/screens/MiCuenta.jsx`: tabs `Resumen · Expensas · Comprobantes · Movimientos` (en el simulador solo "Resumen" está activo; los otros tres se ven pero no responden, porque el objetivo es mostrar el alcance sin abrir cuatro pantallas más).

- [ ] **Step 1: Escribir el markup del paso 4**

Reemplazar `<div class="sim-paso" data-paso="4" hidden></div>` por:

```html
<div class="sim-paso" data-paso="4" hidden>
  <div class="portal">
    <div class="portal-tabs">
      <span class="portal-tab activo">Resumen</span>
      <span class="portal-tab">Expensas</span>
      <span class="portal-tab">Comprobantes</span>
      <span class="portal-tab">Movimientos</span>
    </div>

    <div class="portal-saldo">
      <span>Tu saldo</span>
      <strong id="p-saldo">$ 200.463</strong>
      <span class="portal-nota" id="p-nota">Incluye la expensa de agosto recién emitida.</span>
    </div>

    <div class="portal-card">
      <h4>Expensa 2026-08</h4>
      <p class="meta" id="p-expensa">$ 82.963 · primer vencimiento 10/09/2026</p>
      <span class="pill pill-impaga">Impaga</span>
    </div>

    <div class="portal-card">
      <h4>En qué se fue la plata este mes</h4>
      <ul class="portal-gastos">
        <li><span>Sueldos y cargas sociales</span><span>$ 1.240.000</span></li>
        <li class="destacado"><span>Abono mensual de ascensores</span><span>$ 480.000</span></li>
        <li><span>Luz de partes comunes</span><span>$ 186.400</span></li>
        <li><span>Póliza integral del consorcio</span><span>$ 92.700</span></li>
      </ul>
      <p class="meta">Los mismos rubros que pide la 941, factura por factura.</p>
    </div>

    <div class="portal-card">
      <h4>SUM · sábado 12/09</h4>
      <p class="meta">Disponible · $ 25.000 por turno</p>
      <button type="button" class="btn btn-primario btn-sm" id="p-reservar">Reservar</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Escribir el CSS del portal**

Agregar al final del bloque `/* ===== SIMULADOR ===== */` del `<style>`:

```css
.portal {
  max-width: 380px;
  margin: 0 auto;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius);
  padding: 0.9rem;
  background: var(--color-bg);
}

.portal-tabs {
  display: flex;
  gap: 0.25rem;
  overflow-x: auto;
  scrollbar-width: none;
  margin-bottom: 0.9rem;
}

.portal-tabs::-webkit-scrollbar { display: none; }

.portal-tab {
  white-space: nowrap;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--color-text-muted);
  padding: 0.3rem 0.6rem;
  border-radius: var(--radius-pill);
}

.portal-tab.activo { background: var(--color-primary); color: #fff; }

.portal-saldo {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.75rem 0.9rem;
  margin-bottom: 0.7rem;
  font-size: 0.72rem;
  color: var(--color-text-muted);
}

.portal-saldo strong {
  font-family: var(--font-display);
  font-size: 1.5rem;
  color: var(--color-danger);
}

.portal-nota { font-size: 0.68rem; }

.portal-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.75rem 0.9rem;
  margin-bottom: 0.7rem;
}

.portal-card h4 {
  font-family: var(--font-display);
  font-size: 0.85rem;
  font-weight: 800;
  margin: 0 0 0.35rem;
}

.portal-card .meta { font-size: 0.72rem; color: var(--color-text-muted); margin: 0 0 0.5rem; }

.portal-gastos { list-style: none; margin: 0 0 0.5rem; padding: 0; font-size: 0.75rem; }

.portal-gastos li {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.3rem 0;
  border-bottom: 1px solid var(--color-border);
}

.portal-gastos .destacado {
  color: var(--color-success);
  font-weight: 700;
}
```

- [ ] **Step 3: Cablear el paso 4**

Dentro de `render()`, reemplazar el comentario `/* La Task 8 agrega acá su lógica de pintado. */` por:

```js
  /* Paso 4 */
  const cuenta = deudaUF2A();
  document.getElementById("p-saldo").textContent = money(cuenta.saldo);
  document.getElementById("p-nota").textContent = sim.periodoCerrado
    ? "Incluye la expensa de agosto recién emitida."
    : "Agosto todavía no fue emitida por la administración.";
  document.getElementById("p-expensa").textContent = sim.periodoCerrado
    ? "$ 82.963 · primer vencimiento 10/09/2026"
    : "Todavía no emitida.";
```

Y agregar, después de los listeners del paso 3:

```js
document.getElementById("p-reservar").addEventListener("click", (e) => {
  e.target.textContent = "Reservado ✓";
  e.target.disabled = true;
  nota("El propietario reservó el SUM solo, y el cargo de $ 25.000 le va a aparecer en su cuenta corriente. Ese llamado no lo atendiste vos.");
});
```

Y en `resetSim()`, agregar la restauración del botón:

```js
  const btnReservar = document.getElementById("p-reservar");
  btnReservar.textContent = "Reservar";
  btnReservar.disabled = false;
```

- [ ] **Step 4: Escribir el CTA de WhatsApp bajo el simulador**

Reemplazar la línea `<!-- ===== CTA-SIMULADOR ===== -->` del `<body>` por:

```html
<!-- ===== CTA-SIMULADOR ===== -->
<section class="cta-sim">
  <div class="cta-sim-inner">
    <div>
      <h2>¿Esto te sirve para tus edificios?</h2>
      <p>Contame cuántas unidades administrás y te digo en dos minutos si te conviene.</p>
    </div>
    <a class="btn btn-wa" id="wa-sim" href="#" target="_blank" rel="noopener">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm0 18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.18 8.18 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.25-8.24 2.2 0 4.27.86 5.83 2.42a8.19 8.19 0 0 1 2.41 5.83c0 4.54-3.7 8.23-8.24 8.23Zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.24-.64.8-.78.97-.15.16-.29.18-.54.06-.25-.13-1.05-.39-1.99-1.23-.74-.66-1.24-1.47-1.38-1.72-.15-.25-.02-.38.11-.5.11-.11.25-.29.37-.44.13-.15.17-.25.25-.41.08-.17.04-.31-.02-.44-.06-.12-.56-1.35-.77-1.85-.2-.48-.4-.42-.56-.43h-.47c-.17 0-.44.06-.66.31-.23.25-.87.85-.87 2.07s.89 2.4 1.02 2.57c.12.16 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.47-.07 1.47-.6 1.68-1.18.21-.58.21-1.08.14-1.18-.06-.11-.22-.17-.47-.29Z"/></svg>
      Escribinos por WhatsApp
    </a>
  </div>
</section>
```

Reemplazar la línea `/* ===== CTA-SIMULADOR ===== */` del `<style>` por:

```css
/* ===== CTA-SIMULADOR ===== */
.cta-sim { background: var(--color-mod-inicio); color: #fff; }

.cta-sim-inner {
  max-width: 1120px;
  margin: 0 auto;
  padding: 2.5rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.cta-sim h2 { font-size: 1.4rem; margin-bottom: 0.35rem; }

.cta-sim p {
  margin: 0;
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.95rem;
}

@media (min-width: 600px) {
  .cta-sim-inner {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding: 3rem 2rem;
  }
}
```

Y reemplazar la línea `/* ===== CTA-SIMULADOR ===== */` del `<script>` por:

```js
/* ===== CTA-SIMULADOR ===== */
document.getElementById("wa-sim").href = linkWhatsApp(
  "Hola! Probé el simulador de Gestor Consorcios. Administro  unidades y quiero saber si me sirve."
);
```

- [ ] **Step 5: Verificar en browser**

Recorrido completo desde "Reiniciar": guardar gasto → cerrar período → pagar $ 120.000 → Siguiente.

Observaciones esperadas en el paso 4:
- El badge de rol de la topbar dice **"Propietario"** y la URL es `/mi-cuenta`.
- Tarjeta angosta centrada (máx. 380px) — es la vista mobile del portal, **no** se estira a todo el ancho del frame.
- Cuatro tabs con "Resumen" en teal.
- "Tu saldo **$ 200.463**" — el mismo número del paso 3.
- Tarjeta "Expensa 2026-08" con "$ 82.963 · primer vencimiento 10/09/2026" — viene del paso 2.
- En "En qué se fue la plata este mes", la línea **"Abono mensual de ascensores · $ 480.000" en verde y negrita** — viene del paso 1. **Los tres rastros tienen que verse al mismo tiempo; si falta alguno, la tarea está incompleta.**
- Click en "Reservar" → pasa a "Reservado ✓", deshabilitado, y la nota cambia.
- Debajo del simulador, banda azul oscuro `#1b3a4b` con el titular "¿Esto te sirve para tus edificios?" y el botón verde de WhatsApp a la derecha.

Recorrido alternativo: "Reiniciar" → ir al paso 4 desde el sidebar. El saldo es **$ 237.500**, la nota dice "Agosto todavía no fue emitida por la administración." y la tarjeta de expensa dice "Todavía no emitida.".

A 375x812: la banda del CTA apila título y botón; el botón va a ancho completo.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat(landing): paso 4 del simulador (portal) y CTA de WhatsApp"
```

---

### Task 9: Sección del consorcio y catálogo de módulos

**Files:**
- Modify: `index.html` (anclas `CONSORCIO` y `MODULOS` en `<body>` y `<style>`)

**Interfaces:**
- Consumes: `.seccion`, `.eyebrow` de la Task 1.
- Produces: `id="modulos"` — destino del link de la nav creada en la Task 1.

Los ocho módulos y sus nombres comerciales salen de `backend/modulos.py`. **No agregar ni renombrar módulos.**

- [ ] **Step 1: Escribir la sección del consorcio**

Reemplazar la línea `<!-- ===== CONSORCIO ===== -->` del `<body>` por:

```html
<!-- ===== CONSORCIO ===== -->
<section class="seccion consorcio">
  <div class="consorcio-inner">
    <p class="eyebrow">Del otro lado del mostrador</p>
    <h2>La asamblea se va entera en discutir un número que nadie puede ver.</h2>
    <p>
      El consejo no tiene cómo auditar sin pedir carpetas. El vecino que
      administra lleva el fondo de reserva en un cuaderno. Y cada expensa que
      sube vuelve a abrir la misma discusión de siempre.
    </p>
    <p class="consorcio-remate">
      Cuando cada propietario entra y ve en qué se fue la plata —factura por
      factura, rubro por rubro, con los comprobantes adjuntos— la discusión se
      termina antes de empezar. La transparencia no es un favor al propietario:
      es lo que te saca la discusión de encima.
    </p>
  </div>
</section>
```

Y la línea `/* ===== CONSORCIO ===== */` del `<style>` por:

```css
/* ===== CONSORCIO ===== */
.consorcio {
  border-top: 1px solid var(--color-border);
}

.consorcio-inner { max-width: 62ch; }

.consorcio h2 { font-size: clamp(1.5rem, 5vw, 2rem); }

.consorcio p { color: var(--color-text-muted-strong); }

.consorcio-remate {
  font-weight: 600;
  color: var(--color-text);
  border-left: 3px solid var(--color-mod-cobranzas);
  padding-left: 1rem;
}
```

- [ ] **Step 2: Escribir el catálogo de módulos**

Reemplazar la línea `<!-- ===== MODULOS ===== -->` del `<body>` por:

```html
<!-- ===== MODULOS ===== -->
<section class="seccion modulos" id="modulos">
  <p class="eyebrow">Lo que incluye</p>
  <h2 class="modulos-titulo">Ocho módulos. Activás los que usás.</h2>

  <div class="modulos-grid">
    <article class="modulo" style="--acento: var(--color-mod-cobranzas);">
      <span class="modulo-plan">Base</span>
      <h3>Cobranzas y expensas</h3>
      <p>Emisión por coeficiente, cuenta corriente por unidad con imputación a la deuda más vieja, comprobantes de pago e intereses punitorios.</p>
    </article>

    <article class="modulo" style="--acento: var(--color-mod-gastos);">
      <span class="modulo-plan">Base</span>
      <h3>Gastos y proveedores</h3>
      <p>Facturas clasificadas por rubro, gastos habituales que se cargan solos cada mes, planes en cuotas y gastos particulares de una unidad.</p>
    </article>

    <article class="modulo" style="--acento: var(--color-mod-finanzas);">
      <span class="modulo-plan">Base</span>
      <h3>Tesorería</h3>
      <p>Cajas y cuentas bancarias, transferencias entre cajas y el fondo de reparación separado del giro del mes.</p>
    </article>

    <article class="modulo" style="--acento: var(--color-mod-inicio);">
      <span class="modulo-plan">Base</span>
      <h3>Comunicados</h3>
      <p>La cartelera del edificio, pero que llega. Publicás una vez y lo ven todas las unidades desde su portal.</p>
    </article>

    <article class="modulo" style="--acento: var(--color-mod-expensas);">
      <span class="modulo-plan">Base</span>
      <h3>Reportes</h3>
      <p>Lista de morosos, estado financiero, detalle de gastos del período y listado de proveedores. El consejo los mira sin pedirte nada.</p>
    </article>

    <article class="modulo modulo-opcional" style="--acento: var(--color-mod-operacion);">
      <span class="modulo-plan">Opcional</span>
      <h3>Mantenimiento</h3>
      <p>Peticiones de los vecinos, presupuestos de proveedores, trabajos aprobados y las tareas recurrentes del edificio.</p>
    </article>

    <article class="modulo modulo-opcional" style="--acento: var(--color-mod-operacion);">
      <span class="modulo-plan">Opcional</span>
      <h3>Espacios comunes</h3>
      <p>SUM, laundry, parrilla. Con reglas por amenity: precio del turno, anticipación, duración y tope de reservas por unidad.</p>
    </article>

    <article class="modulo modulo-opcional" style="--acento: var(--color-mod-finanzas);">
      <span class="modulo-plan">Opcional</span>
      <h3>Personal y sueldos</h3>
      <p>Legajo del encargado, haberes, descuentos y contribuciones. Cada liquidación genera sola los gastos del rubro sueldos.</p>
    </article>
  </div>
</section>
```

Y la línea `/* ===== MODULOS ===== */` del `<style>` por:

```css
/* ===== MODULOS ===== */
.modulos { border-top: 1px solid var(--color-border); }

.modulos-titulo { font-size: clamp(1.6rem, 5.5vw, 2.1rem); margin-bottom: 2rem; }

.modulos-grid { display: grid; gap: 1rem; }

.modulo {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-left: 4px solid var(--acento);
  border-radius: var(--radius-sm);
  padding: 1.1rem 1.25rem;
}

.modulo-plan {
  display: inline-block;
  font-size: 0.62rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--color-text-muted);
  background: var(--color-bg);
  border-radius: var(--radius-pill);
  padding: 0.15rem 0.55rem;
  margin-bottom: 0.6rem;
}

.modulo-opcional .modulo-plan {
  color: var(--acento);
  background: color-mix(in srgb, var(--acento) 12%, transparent);
}

.modulo h3 { font-size: 1rem; color: var(--acento); margin-bottom: 0.4rem; }

.modulo p {
  font-size: 0.88rem;
  color: var(--color-text-muted-strong);
  margin: 0;
}

@media (min-width: 700px) {
  .modulos-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1000px) {
  .modulos-grid { grid-template-columns: repeat(4, 1fr); }
}
```

- [ ] **Step 3: Verificar en browser**

Observaciones esperadas a 1440x900:
- Sección del consorcio con el texto en una columna angosta (máx. 62ch), **no estirada a todo el ancho**, y el remate con la barra verde a la izquierda.
- Grilla de módulos en **4 columnas × 2 filas**, con la franja izquierda de color por módulo.
- Los cinco primeros tienen el chip gris "Base"; los tres últimos, el chip "Opcional" en color.

Observaciones esperadas a 700-999px: la grilla pasa a 2 columnas.
Observaciones esperadas a 375x812: una sola columna, sin desborde.

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat(landing): seccion del consorcio y catalogo de los 8 modulos"
```

---

### Task 10: Sección de precios

**Files:**
- Modify: `index.html` (ancla `PRECIOS` en `<body>` y `<style>`)

**Interfaces:**
- Consumes: `.seccion`, `.eyebrow` de la Task 1.
- Produces: `id="precios"` — destino del link de la nav creada en la Task 1.

Los montos son los del spec y **no se cambian**: base USD 1,40 por unidad/mes, cada módulo opcional +USD 0,20, tope USD 2,00, mínimo mensual de 20 unidades.

- [ ] **Step 1: Escribir el markup**

Reemplazar la línea `<!-- ===== PRECIOS ===== -->` del `<body>` por:

```html
<!-- ===== PRECIOS ===== -->
<section class="seccion precios" id="precios">
  <p class="eyebrow">Cuánto sale</p>
  <h2 class="precios-titulo">Se paga por unidad, no por edificio.</h2>
  <p class="precios-intro">
    Si administrás tres edificios de 30 unidades, pagás por 90 unidades. Si un
    consorcio se va, deja de pagarse solo. Sin costo de alta ni permanencia.
  </p>

  <div class="precios-grid">
    <article class="plan plan-base">
      <span class="plan-tag">Base</span>
      <p class="plan-precio"><strong>USD 1,40</strong><span>por unidad / mes</span></p>
      <ul class="plan-lista">
        <li>Cobranzas y expensas</li>
        <li>Gastos y proveedores</li>
        <li>Tesorería</li>
        <li>Comunicados</li>
        <li>Reportes</li>
        <li>Portal para propietarios e inquilinos</li>
        <li>Todos tus consorcios en la misma cuenta</li>
      </ul>
    </article>

    <article class="plan plan-extra">
      <span class="plan-tag">Módulos opcionales</span>
      <p class="plan-precio"><strong>+USD 0,20</strong><span>por unidad / mes, cada uno</span></p>
      <ul class="plan-lista">
        <li>Mantenimiento — peticiones, presupuestos y trabajos</li>
        <li>Espacios comunes — reservas de SUM, laundry y parrilla</li>
        <li>Personal y sueldos — legajos y liquidaciones del encargado</li>
      </ul>
      <p class="plan-nota">
        Activás solo lo que el consorcio usa. No todo edificio tiene encargado
        propio ni SUM.
      </p>
    </article>

    <article class="plan plan-tope">
      <span class="plan-tag">Con todo activado</span>
      <p class="plan-precio"><strong>USD 2,00</strong><span>por unidad / mes</span></p>
      <p class="plan-nota">
        Es el techo. Un edificio de 30 unidades con absolutamente todo prendido
        sale USD 60 por mes.
      </p>
    </article>
  </div>

  <ul class="precios-letra">
    <li><strong>Mínimo mensual por consorcio:</strong> el equivalente a 20 unidades — USD 28 con el plan base.</li>
    <li><strong>Facturado en pesos</strong> al tipo de cambio del día.</li>
  </ul>
</section>
```

- [ ] **Step 2: Escribir el CSS**

Reemplazar la línea `/* ===== PRECIOS ===== */` del `<style>` por:

```css
/* ===== PRECIOS ===== */
.precios { border-top: 1px solid var(--color-border); }

.precios-titulo { font-size: clamp(1.6rem, 5.5vw, 2.1rem); }

.precios-intro {
  max-width: 52ch;
  color: var(--color-text-muted-strong);
  margin-bottom: 2rem;
}

.precios-grid { display: grid; gap: 1rem; align-items: start; }

.plan {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1.4rem;
}

.plan-base { border-color: var(--color-primary); box-shadow: var(--shadow-md); }

.plan-tag {
  display: inline-block;
  font-size: 0.64rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--color-primary);
  margin-bottom: 0.75rem;
}

.plan-precio { margin: 0 0 1rem; }

.plan-precio strong {
  display: block;
  font-family: var(--font-display);
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.plan-precio span { font-size: 0.8rem; color: var(--color-text-muted); }

.plan-lista {
  list-style: none;
  margin: 0 0 0.75rem;
  padding: 0;
  display: grid;
  gap: 0.4rem;
  font-size: 0.88rem;
  font-weight: 600;
}

.plan-lista li { padding-left: 1.25rem; position: relative; }

.plan-lista li::before {
  content: "✓";
  position: absolute;
  left: 0;
  color: var(--color-success);
  font-weight: 800;
}

.plan-nota {
  font-size: 0.82rem;
  color: var(--color-text-muted-strong);
  margin: 0;
}

.precios-letra {
  list-style: none;
  margin: 1.5rem 0 0;
  padding: 0;
  display: grid;
  gap: 0.35rem;
  font-size: 0.82rem;
  color: var(--color-text-muted);
}

@media (min-width: 900px) {
  .precios-grid { grid-template-columns: repeat(3, 1fr); gap: 1.25rem; }
}
```

- [ ] **Step 3: Verificar en browser**

Observaciones esperadas a 1440x900:
- Tres tarjetas en fila. La primera ("Base") tiene borde teal y sombra; las otras dos, borde gris.
- Los montos en Montserrat 800 a 2rem: **USD 1,40**, **+USD 0,20**, **USD 2,00**.
- La lista del plan base tiene siete ítems con tilde verde.
- Debajo, la letra chica con el mínimo de USD 28 y la facturación en pesos.
- **Ninguna mención a "Ley 941"** en esta sección.

A 375x812: las tres tarjetas apiladas, sin desborde.

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat(landing): seccion de precios por unidad con modulos activables"
```

---

### Task 11: Cierre, pasada responsive y verificación final

**Files:**
- Modify: `index.html` (ancla `CIERRE` en `<body>`, `<style>` y `<script>`)

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: nada.

- [ ] **Step 1: Escribir la sección de cierre**

Reemplazar la línea `<!-- ===== CIERRE ===== -->` del `<body>` por:

```html
<!-- ===== CIERRE ===== -->
<section class="cierre">
  <div class="cierre-inner">
    <h2>Lo que probaste recién, pero con un edificio entero.</h2>
    <p>
      El demo público tiene un consorcio cargado con seis meses de gastos,
      expensas emitidas, morosos de verdad y la liquidación del encargado.
      Entrás, elegís con qué rol mirarlo y tocás lo que quieras. No pedimos mail
      ni tarjeta.
    </p>
    <div class="cierre-acciones">
      <a class="btn btn-primario" href="https://consorciosdemo.vercel.app/" target="_blank" rel="noopener">Entrar al demo</a>
      <a class="btn btn-wa" id="wa-cierre" href="#" target="_blank" rel="noopener">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm0 18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.18 8.18 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.25-8.24 2.2 0 4.27.86 5.83 2.42a8.19 8.19 0 0 1 2.41 5.83c0 4.54-3.7 8.23-8.24 8.23Zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.24-.64.8-.78.97-.15.16-.29.18-.54.06-.25-.13-1.05-.39-1.99-1.23-.74-.66-1.24-1.47-1.38-1.72-.15-.25-.02-.38.11-.5.11-.11.25-.29.37-.44.13-.15.17-.25.25-.41.08-.17.04-.31-.02-.44-.06-.12-.56-1.35-.77-1.85-.2-.48-.4-.42-.56-.43h-.47c-.17 0-.44.06-.66.31-.23.25-.87.85-.87 2.07s.89 2.4 1.02 2.57c.12.16 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.47-.07 1.47-.6 1.68-1.18.21-.58.21-1.08.14-1.18-.06-.11-.22-.17-.47-.29Z"/></svg>
        Coordinar una demo por WhatsApp
      </a>
    </div>
  </div>
</section>
```

Reemplazar la línea `/* ===== CIERRE ===== */` del `<style>` por:

```css
/* ===== CIERRE ===== */
.cierre {
  background: var(--color-mod-inicio);
  color: #fff;
}

.cierre-inner {
  max-width: 62ch;
  margin: 0 auto;
  padding: 4rem 1.25rem;
  text-align: center;
}

.cierre h2 { font-size: clamp(1.6rem, 5.5vw, 2.2rem); }

.cierre p {
  color: rgba(255, 255, 255, 0.78);
  margin-bottom: 1.75rem;
}

.cierre-acciones {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

@media (min-width: 600px) {
  .cierre-inner { padding: 5rem 2rem; }
  .cierre-acciones { flex-direction: row; justify-content: center; }
}
```

Y la línea `/* ===== CIERRE ===== */` del `<script>` por:

```js
/* ===== CIERRE ===== */
document.getElementById("wa-cierre").href = linkWhatsApp(
  "Hola! Quiero coordinar una demo de Gestor Consorcios."
);
```

- [ ] **Step 2: Auditoría de la regla de copy**

Correr sobre el archivo terminado:

```bash
grep -niE "facilitamos la vida|facilitar la vida|potenci[aá]|optimiz|solución integral|Ley 941|941" index.html
```

Esperado: **una sola línea**, la del paso 4 del simulador que dice "Los mismos rubros que pide la 941, factura por factura." Cualquier otro resultado es una violación de las Global Constraints y hay que corregirlo.

- [ ] **Step 3: Auditoría del número de WhatsApp**

```bash
grep -c "5491178959108" index.html
```

Esperado: **1** (la constante). Si da más de 1, alguien hardcodeó el número en un `href` y hay que reemplazarlo por `linkWhatsApp(...)`.

```bash
grep -n "wa.me" index.html
```

Esperado: **1** línea, la de dentro de `linkWhatsApp`.

- [ ] **Step 4: Pasada responsive completa**

Recorrer la página entera a **375x812**, **768x1024** y **1440x900**, tomando screenshot de cada sección. Verificar en los tres:

- `document.body.scrollWidth <= window.innerWidth` (sin scroll horizontal). Comprobarlo en consola.
- Ningún bloque de texto ocupa el 100 % del ancho en desktop: `.consorcio-inner`, `.cierre-inner`, `.hero-bajada`, `.sim-intro` y `.precios-intro` tienen tope de ancho.
- A ≥600px los botones tienen ancho de contenido, no full-width — salvo los del CTA final, que están centrados a propósito.
- Las dos zonas de scroll horizontal permitidas (`.tabla-scroll` y `.sim-stepper`) scrollean **dentro de sí mismas**.

- [ ] **Step 5: Recorrido funcional de punta a punta**

Con la ventana en 1440x900, ejecutar y verificar en orden:

1. Click en "Ver cómo funciona" del hero → scrollea hasta el simulador.
2. "Guardar gasto" → total $ 1.999.100.
3. "Siguiente paso →" → "Generar preview" → total $ 1.999.100 y el cartel del ascensor visible.
4. "Confirmar cierre" → bloque verde.
5. "Siguiente paso →" → 4 filas en la cuenta corriente, saldo $ 320.463.
6. "$ 120.000" → saldo $ 200.463, mayo verde, junio amarillo.
7. "Siguiente paso →" → portal con saldo $ 200.463, expensa $ 82.963 y el ascensor de $ 480.000 en verde.
8. "Reservar" → "Reservado ✓".
9. "Reiniciar" → todo vuelve al estado inicial: paso 1, total $ 1.519.100, botón "Guardar gasto" habilitado, bloque de estado del cierre visible y el de preview oculto, botón "Reservar" habilitado.
10. Consola sin errores en todo el recorrido.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat(landing): seccion de cierre con demo real y contacto por WhatsApp"
```

---

## Self-Review

**Cobertura del spec:**

| Requisito del spec | Tarea |
|---|---|
| Público y regla de copy | Global Constraints + Tasks 2, 3, 9 |
| Hero con video y 2 CTAs | Task 2 |
| Tres dolores | Task 3 |
| Simulador de 4 pasos con rastro encadenado | Tasks 4-8 |
| CTA WhatsApp bajo el simulador | Task 8 |
| Sección del consorcio (dolor #4) | Task 9 |
| Catálogo de los 8 módulos | Task 9 |
| Precios base + módulos | Task 10 |
| Cierre con demo real + contacto | Task 11 |
| Tokens de la app | Task 1 + Global Constraints |
| Mobile-first, verificar a 375px | Task 11 Step 4 + cada tarea |
| WhatsApp como constante única | Task 1 + Task 11 Step 3 |
| No decir "Ley 941" | Task 11 Step 2 |
| `assets/` para el video | Task 1 |
| No tocar `demo-tutorial.html` ni `frontend/` | File Structure |

**Desviaciones respecto del spec, deliberadas:** el spec describía el paso 2 como "un click en *Cerrar período*" y la pantalla de Gastos como una tabla. `frontend/src/screens/CierreDePeriodo.jsx` usa un flujo de dos clicks (preview → confirmar) y `Gastos.jsx` es una lista de tarjetas. El spec exige fidelidad a las pantallas reales, así que el plan sigue el código. Además, la clase de prorrateo es "A — Expensas ordinarias" (de `backend/seed.py:118`) y el rubro del abono de ascensores es "Abonos y servicios" (de `backend/models.py:87`).

**Consistencia de nombres:** `sim`, `render()`, `irAPaso(n)`, `resetSim()`, `money(n)`, `nota(texto)`, `linkWhatsApp(mensaje)`, `deudaUF2A()` y `pintarCuentaCorriente()` se declaran una vez y se usan con la misma firma en todas las tareas. Los ids (`g-total`, `c-total`, `cc-saldo`, `p-saldo`, `wa-hero`, `wa-sim`, `wa-cierre`) son únicos en el documento.

# Landing page de venta — diseño

**Fecha:** 2026-08-03
**Estado:** aprobado, pendiente de plan de implementación

## Objetivo

Reemplazar la landing actual (`index.html` de la raíz) por una nueva, escrita de cero,
que venda el sistema a **administradores profesionales de consorcios** mostrando el
producto en funcionamiento en vez de describirlo.

La landing tiene dos trabajos: convencer con dolores concretos y dejar que el visitante
recorra la app sin registrarse.

## Público y mensaje

**Público primario:** estudios y administradores que manejan varios edificios. Compran
tiempo y compran dejar de descuadrar.

**Público secundario:** consorcios de copropietarios (consejos, autoadministrados). No es
a quien le vendemos la licencia, pero es quien empuja al administrador y quien aprueba el
gasto en asamblea. Tiene sección propia.

**Regla de copy (dura):** nunca decir "te facilitamos la vida", "potenciá tu gestión" ni
equivalentes. Cada sección nombra el problema en el idioma del administrador y la prueba
es la pantalla, no el adjetivo. Ejemplo del tono buscado: *"El 3 de cada mes ya sabés
quién no pagó."*

### Los cuatro dolores

1. **El descuadre.** Cobros a cuenta, pagos parciales y expensas viejas sin saldar. La
   planilla dice una cosa y la cuenta corriente otra. → lo prueba el paso 3 del simulador.
2. **El cierre de mes.** Días de prorratear a mano por coeficiente, rubro por rubro, y
   volver a empezar si entró una factura tarde. → lo prueban los pasos 1 y 2.
3. **El teléfono.** "¿Cuánto debo?", "¿en qué se fue la plata?", "¿está libre el SUM?".
   → lo prueba el paso 4.
4. **La sospecha** (sección del consorcio). El consejo que no puede auditar, el vecino que
   administra con un cuaderno, la asamblea que se va en discutir un número. Argumento:
   *la transparencia no es un favor al propietario, es lo que te saca la discusión de encima.*

### Decisiones de copy tomadas

- **No** decir "Liquidación Ley 941". El sistema clasifica gastos por `Rubro`
  (`backend/models.py:85`), que es lo que la 941 pide en CABA, pero no hay exportación ni
  formato oficial certificado. La landing dice **"gastos clasificados por rubro, como los
  pide la 941"**. Vende casi igual sin exponerse en la primera reunión.
- El carácter **multi-consorcio** (una administración maneja varios edificios) va en el
  hero: es argumento de venta directo para el público primario.

## Estructura de la página

| # | Sección | Contenido |
|---|---|---|
| 1 | **Hero** | Titular sobre el descuadre + bajada + 2 CTAs + video de impacto al costado. |
| 2 | **Los tres dolores** | Tres bloques: problema arriba, respuesta concreta abajo. Cada uno ancla al paso del simulador que lo prueba. |
| 3 | **Un mes en 4 pasos** | El simulador. Centro de la página. |
| 3b | **CTA WhatsApp** | Inmediatamente debajo del simulador. |
| 4 | **Para el consorcio** | Dolor #4: transparencia, portal del propietario, reportes que el consejo mira solo. |
| 5 | **Módulos** | Los 8 módulos reales de `backend/modulos.py`, con lo que hace cada uno. Doble función: catálogo y base de la grilla de precios. |
| 6 | **Precios** | Base + módulos activables. |
| 7 | **Cierre** | Demo real + contacto por WhatsApp. |

### Hero

Layout de dos columnas en desktop; en mobile el video va debajo del texto.

- Izquierda: titular, bajada corta, y los dos CTAs.
- Derecha: video 16:9.

**Los dos CTAs del hero** están pensados como una bifurcación por temperatura del visitante:

- **Primario — "Ver cómo funciona"**: para el indeciso. Hace scroll suave al simulador
  (sección 3). Es el camino principal de la página.
- **Secundario — WhatsApp**: para el que ya está caliente. Verde WhatsApp `#25D366` con el
  glifo oficial en SVG inline, para que se entienda a dónde va antes de clickearlo.

**Video:** bloque `<video>` maquetado con `poster` y controles nativos, apuntando a
`assets/demo.mp4`. El archivo todavía no existe; el bloque queda listo para que el usuario
lo suelte ahí. Sin autoplay, sin dependencias externas. Mientras falte el archivo, el
`poster` muestra un placeholder para que la sección no se vea rota.

## El simulador — "Un mes en 4 pasos"

Réplica en HTML/CSS de las pantallas reales, clicable, con datos fijos. Sin backend, sin
login, sin red.

**Principio de diseño (el que hace que funcione):** cada paso deja un rastro visible en el
siguiente. Ahí está el momento en que se entiende el producto.

Frame de browser con el chrome real de la app: header del consorcio y sidebar con las
categorías verdaderas de `frontend/src/navegacion.js` (Finanzas / Gestión / Personal /
Configuración). Arriba, una barra con los 4 pasos.

| Paso | Pantalla | Acción del visitante | Resultado visible |
|---|---|---|---|
| **1** | Gastos | Elige rubro y clickea *Guardar* | Factura de ascensores $480.000 entra a la clase de prorrateo "General". Micro-copy: *no elegís a quién cobrarle, elegís la clase — el coeficiente hace el resto.* |
| **2** | Cierre de período | Un click en *Cerrar período* | Se emiten las expensas por UF. **El ascensor del paso 1 aparece prorrateado en cada unidad.** |
| **3** | Cuenta corriente | Elige un monto ($15.000 / $30.000 / $53.000) y registra el pago | Imputación FIFO animada: la deuda más vieja se salda entera, la siguiente parcial, la tercera intacta. Saldo actualizado. |
| **4** | Portal del propietario | Cambia de rol | El frame pasa a vista mobile. Ve su expensa del paso 2, el pago del paso 3 ya imputado, el detalle con el ascensor del paso 1, y reserva el SUM. |

**Comportamiento:**

- Estado en un único objeto JS. Botón de reinicio.
- Los 4 pasos son clickeables en cualquier orden; el camino principal es el botón *Siguiente*.
- Cada paso muestra un cartel de una línea con "qué acaba de pasar".

**Fidelidad:** columnas, rótulos y colores se copian de las pantallas reales —
`frontend/src/screens/Gastos.jsx`, `CierreDePeriodo.jsx`, `CuentasCorrientes.jsx`
(columnas `Unidad · Ubicación · Saldo · Estado`) y `MiCuenta.jsx`. El que después entre al
demo real tiene que reconocer lo que vio acá.

### CTA debajo del simulador

Es el mejor momento de la página: el visitante acaba de entender el producto. Botón de
WhatsApp en tono de conversación, no de formulario:
*"¿Te sirve para tus edificios? Contame cuántas unidades manejás."*

## Precios

Modelo **base + módulos activables**, alineado a los feature flags reales de
`backend/modulos.py`. Precio **por unidad funcional, por mes**.

- **Base — USD 1,40 por unidad/mes:** Cobranzas y expensas · Gastos y proveedores ·
  Tesorería · Comunicados · Reportes.
- **Módulos opcionales — +USD 0,20 por unidad/mes cada uno:** Mantenimiento ·
  Espacios comunes · Personal y sueldos.
- **Tope con todo activado: USD 2,00 por unidad/mes.**

**Reportes va en la base** a propósito: cobrar aparte por la lista de morosos y el estado
financiero se lee como mezquindad, y es justo el módulo que sostiene el argumento de
transparencia de la sección 4. Los tres módulos pagos son genuinamente opcionales — no
todo consorcio tiene encargado propio ni SUM — así que se sienten como una elección y no
como un peaje.

**Dos aclaraciones que van en la página:**

- **Mínimo mensual por consorcio equivalente a 20 unidades** — con el plan base, USD 28
  por mes. Sin esto, un edificio de 8 UF no cubre ni el soporte.
- **"Facturado en pesos al tipo de cambio del día"**, que es lo que espera un
  administrador argentino y evita la pregunta incómoda.

### Mapa módulo → nombre comercial

| Key en `backend/modulos.py` | Nombre en la landing | Plan |
|---|---|---|
| `cobranzas` | Cobranzas y expensas | Base |
| `gastos` | Gastos y proveedores | Base |
| `finanzas` | Tesorería | Base |
| `comunicacion` | Comunicados | Base |
| `reportes` | Reportes | Base |
| `operacion` | Mantenimiento | +0,20 |
| `espacios_comunes` | Espacios comunes | +0,20 |
| `personal` | Personal y sueldos | +0,20 |

## Implementación

**Entrega:** un solo `index.html` en la raíz del repo, con CSS y JS inline. Sin build. Se
abre con doble click y se publica en cualquier hosting estático.

**Identidad visual:** misma que la app. Tokens copiados de `frontend/src/index.css` —
marfil `#f4f0e6`, teal `#2c6473`, texto `#121212`, Montserrat (display) + Plus Jakarta
Sans (body), radios de 12/16/20px. Se respetan los colores por módulo
(`--color-mod-*`) en la sección de módulos y en el simulador.

**Responsive:** mobile-first, con la densidad liviana en `≥600px` ya validada para este
proyecto (botones ghost/`fit-content`, nada de estirar contenedores al subir de
breakpoint). Verificar a 375px.

**WhatsApp:** número `5491178959108`. Definido como constante única al principio del
bloque `<script>` y usado para construir los tres links `wa.me`, cada uno con su mensaje
pre-cargado distinto según la sección (hero / post-simulador / cierre). Botón con verde
oficial `#25D366` y glifo SVG inline.

**Assets:** carpeta `assets/` en la raíz para `demo.mp4` y su `poster`.

**Qué pasa con lo viejo:**

- `index.html` se reemplaza sin copia de respaldo — la versión actual queda entera en el
  historial de git.
- `demo-tutorial.html` no se toca. Queda fuera del alcance decidir si se enlaza.

## Fuera de alcance

- Grabar o editar el video.
- Publicar la landing en un hosting.
- Formulario de contacto con backend (el contacto es WhatsApp).
- Tocar la app React o el demo público.

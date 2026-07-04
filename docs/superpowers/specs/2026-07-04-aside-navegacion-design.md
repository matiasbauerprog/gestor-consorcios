# Rediseño del aside de navegación

**Fecha:** 2026-07-04
**Estado:** Spec pendiente de revisión del usuario
**Rama sugerida:** `feature/aside-navegacion`

## 1. Problema

El sidebar actual muestra hasta **25 módulos directos** a un admin, distribuidos en 8 secciones planas con títulos como subrayado. El usuario reporta que "es una barbaridad" y no puede saber rápido dónde está parado ni a dónde va. En depto/representante hay menos módulos pero la misma estructura plana los alcanza.

Meta: reducir carga cognitiva sin romper permisos, rutas ni backend. Que el usuario **sepa dónde está parado** (pantalla actual → grupo resaltado) y **encuentre rápido a dónde va** (grupos temáticos evidentes).

## 2. Solución elegida

Acordeón reagrupado sobre `Sidebar.jsx`. De 8 secciones planas a **6 grupos colapsables**, con auto-expansión según la ruta activa y comportamiento acordeón estricto (abrir uno cierra el anterior).

### 2.1 Nueva agrupación

| Grupo | Módulos | Rutas | Antes |
|---|---|---|---|
| **Comunicaciones** | Comunicados, Reglamento (placeholder) | `/comunicados`, `/reglamento` | "General" |
| **Finanzas** | Mi cuenta (depto), Expensas, Comprobantes, Historial de cierres, Gastos, Estado financiero, Cajas, Transferencias | `/mi-cuenta`, `/expensas`, `/comprobantes`, `/periodos`, `/gastos`, `/estado-financiero`, `/cajas`, `/transferencias` | "Expensas y pagos" + "Tesorería" |
| **Operación** | Peticiones, Trabajos, Trabajos recurrentes, Reservas, Amenities | `/peticiones`, `/trabajos`, `/trabajos-recurrentes`, `/reservas`, `/amenities` | "Tareas y presupuestos" + "Espacios comunes" |
| **Reportes** | los 4 actuales | `/reportes/*` | igual |
| **Personal** | Liquidaciones, Haberes, Conceptos de liquidación | `/liquidaciones`, `/haberes`, `/conceptos-liquidacion` | "Sueldos" |
| **Configuración** | Datos del consorcio, Clases de prorrateo, Proveedores, Departamentos, Empleados | `/configuracion`, `/clases-prorrateo`, `/proveedores`, `/departamentos`, `/empleados` | igual |

Los `rolesPermitidos` de cada módulo se copian sin cambios desde la estructura actual. Un grupo cuyo array `modulos` filtrado queda vacío para el rol no se renderiza (comportamiento actual `.filter((s) => s.modulos.length > 0)`).

### 2.2 Comportamiento

- **Acordeón estricto:** solo un grupo abierto por vez. Abrir otro cierra el actual. El menú nunca supera ~13 líneas.
- **Auto-expansión por ruta:** al montar y al cambiar `useLocation().pathname`, se expande el grupo que contiene la ruta activa.
- **Título del grupo activo pintado en `--color-primary`** aunque esté colapsado (feedback visual persistente de "dónde estoy").
- **Sin persistencia en `localStorage`:** el estado se deriva de la ruta + toggles manuales de la sesión.
- **Mobile drawer:** mismo acordeón; el drawer sigue cerrándose al navegar (`onCerrar` en cada link).
- **Módulo Reglamento:** placeholder — link visible para todos los roles, ruta `/reglamento`, pantalla "En construcción". El módulo real (backend + carga de documento) queda fuera de scope y se diseña en un ciclo posterior.

### 2.3 Presentación visual

Tokens y patrones ya definidos en `index.css`:
- Título de grupo como `<button>` ghost, `--color-text-muted`, uppercase existente (`.sidebar-section-titulo`).
- Chevron `▸ / ▾` a la derecha (rota con `transform: rotate(90deg)`).
- Hover con el tinte delicado ya validado (`color-mix(in srgb, var(--color-primary-soft) 55%, transparent)`).
- Target táctil ≥44px.
- Transición de 150ms al expandir (`max-height` o `grid-template-rows`).
- Links internos preservan indent y highlight activo (`--color-primary-soft`).

## 3. Archivos afectados

### Modificar
- **`frontend/src/components/Sidebar.jsx`**
  - Reescribir constante `SECCIONES` con los 6 grupos nuevos.
  - Agregar estado `grupoAbierto` con `useState`, inicializado desde la ruta activa.
  - `useLocation()` de `react-router-dom` para derivar el grupo activo.
  - `useEffect` que actualiza `grupoAbierto` cuando cambia `pathname`.
  - Handler `toggleGrupo(titulo)` para clicks en el título del grupo.
  - Reemplazar `<h3 className="sidebar-section-titulo">` por `<button>` con `aria-expanded` y chevron.
  - Renderizar la `<ul>` de módulos solo si el grupo está abierto (o mediante CSS `max-height: 0` para animar).

- **`frontend/src/index.css`**
  - Agregar estilos para `.sidebar-section-titulo` como botón (padding, min-height, alineación, chevron, hover con `color-mix`).
  - Regla para el estado activo (`.sidebar-section-titulo.activo`).
  - Animación de expansión.
  - Sin cambios en tokens ni breakpoints.

- **`frontend/src/App.jsx`**
  - Agregar `<Route path="reglamento" element={<Reglamento />} />` dentro del layout autenticado.
  - Import de `Reglamento`.

### Crear
- **`frontend/src/screens/Reglamento.jsx`**
  - Pantalla placeholder: `<section>` con `<header className="cabecera-pantalla">`, `<h2>Reglamento</h2>`, y un `<Tarjeta>` con texto "En construcción — próximamente podrás consultar el reglamento del consorcio desde acá."

### No tocar
- Backend, rutas de API, contratos OpenAPI, tests de pytest.
- Otros componentes de la app.
- Documentación de reglas/negocio (`.claude/rules/business-rules.md` sigue vigente sin cambios).

## 4. Cómo lo prueba el usuario

- **Desktop (≥960px):**
  1. Loguearse como admin → confirmar 6 grupos, uno abierto según la ruta inicial (Comunicaciones porque cae en `/comunicados`).
  2. Clickear otros grupos → verificar acordeón estricto (se cierra el anterior).
  3. Navegar a `/gastos` desde otro grupo → Finanzas se auto-expande.
  4. Cerrar Finanzas a mano en `/gastos` → el título "Finanzas" queda igual en `--color-primary` (aunque colapsado).
  5. Ir a `/reglamento` → ver pantalla "En construcción".
- **Depto:** login con rol departamento → confirmar que solo aparecen los grupos con módulos permitidos. Toggle del flag `reportes_visibles_a_depto` sigue funcionando.
- **Representante:** login con rol representante → mismo chequeo.
- **Mobile (375px):** abrir drawer, verificar acordeón, verificar que al navegar el drawer se cierra.

## 5. Fuera de scope

- Módulo Reglamento real (backend, modelo, carga/edición de contenido) — proyecto separado.
- Command palette / búsqueda en el menú.
- Persistir estado de grupos en `localStorage`.
- Cambiar el header, la campanita, el layout general.
- Reagrupar reportes en subcategorías.

## 6. Riesgos y mitigación

- **Riesgo:** un rol podría perder el acceso visual a un módulo si el filtrado por rol cambia. **Mitigación:** copiar los arrays `rolesPermitidos` verbatim desde el `SECCIONES` actual; test manual con los 3 roles.
- **Riesgo:** la animación de expansión con `max-height` puede tener saltos si el contenido es alto. **Mitigación:** valor generoso (`max-height: 30rem`) o usar `grid-template-rows: 0fr → 1fr`.
- **Riesgo:** al montar la app con `/comunicados` como redirect por defecto, si `grupoAbierto` se calcula antes de que `pathname` esté disponible, arranca con todo cerrado. **Mitigación:** inicializar el `useState` con una función que ya lee `location.pathname`.

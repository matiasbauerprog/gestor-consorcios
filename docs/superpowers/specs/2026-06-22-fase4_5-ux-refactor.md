# Fase 4.5 — Refactor UX: acciones contextuales + sidebar más liviano

Fecha: 2026-06-22
Estado: spec acordado (post-merge Fase 4)

## Motivación

Al terminar Fase 4 el sidebar quedó con **17 items**. El usuario observó dos roces:
- Cierre de período es una acción que ocurre *justo después* de terminar de cargar gastos del mes → la separación de pantalla rompe el flujo natural.
- Para revisar pagos de una expensa el usuario tiene que navegar a `/comprobantes` y filtrar — la relación 1 expensa → N comprobantes vive en pantallas distintas.

**Principio rector:** acciones contextuales inline donde el usuario ya está; listas globales con sidebar propio.

## Alcance

- **Solo frontend.** El backend (modelos, endpoints, lógica) queda intacto. Los endpoints ya son suficientes.
- Sin tests nuevos (los smoke E2E manuales alcanzan; la lógica testeada no cambia).
- Sin breaking changes en URLs públicas: rutas `/cierre-de-periodo`, `/comprobantes` siguen existiendo y accesibles por URL directa. Solo se sacan del sidebar.

## Cambios

### 1. Cierre de período → acción inline en Gastos

- **Quitar** del sidebar el item "Cierre de período" (solo el item; la ruta `/cierre-de-periodo` queda).
- **Mantener** en sidebar el item "Historial de cierres" (`/periodos`) — sigue siendo vista global.
- **Agregar** en `/gastos`, cuando hay un filtro de período activo y el período NO está cerrado, un botón:
  ```
  [ 🔒 Cerrar período {YYYY-MM} ]
  ```
  ubicado en la cabecera de acciones (junto a "Nuevo gasto" y "Cargar habituales").
- Click → navega a `/cierre-de-periodo?periodo={YYYY-MM}` (la pantalla actual de cierre ya soporta seleccionar período; agregamos lectura del query param para pre-seleccionarlo).
- Si el período ya está cerrado (está en `cerrados` set), el botón se reemplaza por un badge inerte:
  ```
  ⚠ Período cerrado
  ```

### 2. Comprobantes → vista inline en Expensas (sin remover la pantalla global)

- **Mantener** `/comprobantes` en sidebar (admin sigue usándolo para revisar todos los pagos pendientes de aprobación).
- En `/expensas` (tanto vista admin como vista depto), agregar en cada tarjeta de expensa:
  - Un botón **"Ver comprobantes"** que abre un nuevo modal `ModalComprobantesExpensa.jsx`.
  - El modal lista los comprobantes asociados a esa expensa con su estado (pendiente / aprobado / rechazado), monto y fecha de pago. Si es admin, incluye los botones "Aprobar / Rechazar" inline. Si es depto, solo lectura.
- Para el depto, además, en `/mi-cuenta` el bloque "Próximo vencimiento" gana un botón **"Presentar pago"** que abre el form de comprobante con la expensa pre-seleccionada (hoy hay que ir a `/comprobantes` y elegir).

### 3. Sidebar — limpieza menor

Reducción neta: **-1 item del sidebar** (Cierre de período sale; Historial queda). Comprobantes se mantienen porque siguen siendo valiosos como vista global del admin.

Reorganización **opcional** dentro de "Expensas y pagos":
```
Expensas
Mi cuenta
Comprobantes
Historial de cierres   ← antes "Periodos", rebautizado para que el verbo coincida
Gastos
Sueldos (sub-sección)
```

## Tasks (estimadas)

| # | Task | Files |
|---|---|---|
| 1 | Aceptar `?periodo=YYYY-MM` en `CierreDePeriodo.jsx` | `frontend/src/screens/CierreDePeriodo.jsx` |
| 2 | Sacar item "Cierre de período" del Sidebar; renombrar "Periodos" → "Historial de cierres" si no lo está | `frontend/src/components/Sidebar.jsx` |
| 3 | Botón "Cerrar período" en `/gastos` (visible cuando filtros.periodo está seteado y período abierto) | `frontend/src/screens/Gastos.jsx` |
| 4 | Crear `ModalComprobantesExpensa.jsx` (lista + acciones admin) | `frontend/src/components/ModalComprobantesExpensa.jsx` |
| 5 | Botón "Ver comprobantes" en cada tarjeta de Expensas + render del modal | `frontend/src/screens/Expensas.jsx` |
| 6 | Botón "Presentar pago" en bloque "Próximo vencimiento" de MiCuenta | `frontend/src/screens/MiCuenta.jsx` |
| 7 | Smoke + commit final | — |

Estimado total: ~3-4 horas de trabajo, en 2-3 commits chicos.

## Smoke

1. Admin → `/gastos` → filtrar por período abierto → ver botón "Cerrar período" → click → llega a `/cierre-de-periodo` con período pre-seleccionado.
2. Admin → `/gastos` → filtrar por período cerrado → ver badge "Período cerrado" en lugar del botón.
3. Admin → `/expensas` → click "Ver comprobantes" en una tarjeta → modal lista los pagos → admin puede aprobar/rechazar.
4. Depto → `/mi-cuenta` → bloque "Próximo vencimiento" → click "Presentar pago" → form de comprobante con expensa pre-seleccionada.
5. URL directa: navegar a `/cierre-de-periodo` sin link de sidebar → la pantalla sigue funcionando.

## No-goals (explícito)

- No re-skinear la sidebar entera (sigue siendo lista vertical, no hay submenús nuevos).
- No mover ni renombrar otras secciones (Sueldos, Configuración, etc.).
- No agregar fixtures, tests unitarios ni cambios de API.
- No tocar la lógica de aprobación/rechazo de comprobantes — solo se mueve el acceso al modal.

## Historial

- 2026-06-22: spec inicial post-merge Fase 4, motivado por feedback del usuario sobre sidebar sobrecargado.

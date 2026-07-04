# Hub "Mi cuenta" para el rol departamento

**Fecha:** 2026-07-04
**Estado:** Spec pendiente de revisión del usuario
**Rama sugerida:** `feature/hub-mi-cuenta`

## 1. Problema

La experiencia del rol **departamento** tiene información repetida y navegación por módulos que no le corresponde:

- El botón "Presentar pago" aparece dos veces casi pegadas en Mi cuenta (header + tarjeta "Próximo vencimiento"), con dos modales distintos.
- La lista de expensas aparece duplicada: en Mi cuenta (versión pobre, solo PDF) y en Expensas (versión rica, con badges de estado).
- El aside le muestra tres módulos financieros (Mi cuenta, Expensas, Comprobantes) que se pisan entre sí; Expensas incluso tiene un aviso "para presentar un pago andá a Mi cuenta".

Principio de diseño: al admin le sirve navegación por módulos; al usuario final le sirve navegación por **tareas**. El depto necesita UN lugar donde está toda su plata.

Dato contable clave que habilita la simplificación: la imputación de pagos es **FIFO** (`backend/cuenta_corriente.py` — el crédito se acumula en un pool y se aplica a las expensas más viejas). Asociar un pago a una expensa específica no tiene ningún efecto contable, por lo que diferenciar "pago de tal expensa" vs "pago general" es cosmético y se elimina.

## 2. Solución

**Hub único `/mi-cuenta` con tabs** para el rol departamento. Cambio 100% frontend: cero endpoints nuevos, cero cambios en `openapi.yaml`, backend intocado.

### 2.1 Estructura del hub

`/mi-cuenta` con 4 tabs: **Resumen | Expensas | Comprobantes | Movimientos**

| Tab | Contenido | Origen actual |
|---|---|---|
| **Resumen** (default) | Tarjeta de saldo (con texto "estás al día / saldo pendiente / a favor") + tarjeta "Próximo vencimiento" **informativa** (montos y fechas 1°/2° vencimiento + botón Ver PDF, sin botón de pago) | `MiCuenta.jsx` actual |
| **Expensas** | Lista rica de expensas: badge de estado calculado, monto pendiente, Ver comprobantes, Ver PDF | `Expensas.jsx` (vista depto, vía `TarjetaExpensa`) |
| **Comprobantes** | Sus comprobantes con estado (pendiente_verificacion / aprobado / rechazado), solo lectura | `Comprobantes.jsx` (vista depto) |
| **Movimientos** | Tabla de cuenta corriente (fecha, tipo, descripción, monto con signo) | `MiCuenta.jsx` actual |

- El tab activo se sincroniza con la URL vía `useSearchParams`: `/mi-cuenta?tab=expensas`, `?tab=comprobantes`, `?tab=movimientos`. Sin parámetro (o valor inválido) → Resumen.
- Datos: cada tab consume los endpoints existentes ya documentados (`GET /movimientos` propios, `GET /expensas`, `GET /comprobantes`). La carga puede ser al montar el hub (como hoy hace MiCuenta con movimientos + expensas) más comprobantes.

### 2.2 Flujo de pago único

- **Un solo botón "Presentar pago"** en el header del hub, visible desde cualquier tab.
- **Un solo modal** (el actual `ModalPresentarPagoGenerico`, hoy interno a `MiCuenta.jsx`): fecha del pago, monto, archivo (imagen/PDF). El monto viene pre-cargado con el saldo pendiente del depto si `saldo_total > 0`.
- Se elimina el modal asociado a expensa (`frontend/src/components/ModalPresentarPago.jsx`) y el estado `modalPago` dual (`"sin-expensa"` | objeto expensa) se simplifica a booleano.
- El mensaje de éxito se mantiene: "Comprobante enviado. Va a quedar pendiente hasta que administración lo apruebe."

### 2.3 Aside y rutas

- `frontend/src/components/Sidebar.jsx`: en el grupo Finanzas, los módulos `/expensas` y `/comprobantes` pierden `"departamento"` de `rolesPermitidos` (quedan `["administracion"]`). `/mi-cuenta` no cambia.
- Aside resultante del depto: Comunicación (Comunicados, Reglamento), Finanzas (Mi cuenta), Operación (Peticiones, Reservas), Reportes (según flag `reportes_visibles_a_depto`).
- **Redirects**: en `Expensas.jsx` y `Comprobantes.jsx`, si `user.rol === "departamento"`, renderizar `<Navigate to="/mi-cuenta?tab=expensas" replace />` (respectivamente `?tab=comprobantes`) antes de cualquier otra cosa. Links guardados e historial siguen funcionando y dejan al usuario en el tab correcto.
- Admin y representante: cero cambios visibles ni de comportamiento.

### 2.4 Componentes y reuso

- **`TarjetaExpensa`** se extrae de `Expensas.jsx` a `frontend/src/components/TarjetaExpensa.jsx` (misma implementación, prop `esAdmin` existente). La usan `Expensas.jsx` (admin) y el tab Expensas del hub (con `esAdmin=false`).
- El tab Comprobantes reutiliza el markup de la vista depto de `Comprobantes.jsx` (lista con estado). Las acciones admin (aprobar/rechazar/eliminar) no entran al hub.
- Presentación de tabs: componente liviano dentro de `MiCuenta.jsx` (botones con `aria-selected` + panel), estilos con tokens existentes del design system. No se agrega librería de tabs.

## 3. Contrato OpenAPI y documentación

- **Cero endpoints nuevos. `openapi.yaml` no se modifica.** El hub compone endpoints existentes y documentados. Regla `openapi-first.md` cumplida por vacuidad.
- `business-rules.md` sigue siendo válido sin edición: "Departamentos: presentan comprobantes de pago y ven solo su propio historial" describe exactamente lo que hace el hub.
- Los permisos server-side no cambian: el frontend nunca fue la única barrera (defensa en profundidad ya existente).

## 4. Archivos afectados

### Modificar
- `frontend/src/screens/MiCuenta.jsx` — reorganizar en tabs, un solo botón/modal de pago, montar contenido de los 4 tabs, sincronización `?tab=`.
- `frontend/src/screens/Expensas.jsx` — redirect depto + extraer `TarjetaExpensa` (queda import).
- `frontend/src/screens/Comprobantes.jsx` — redirect depto.
- `frontend/src/components/Sidebar.jsx` — quitar `"departamento"` de Expensas y Comprobantes.
- `frontend/src/index.css` — estilos de tabs (tokens existentes, mobile-first).

### Crear
- `frontend/src/components/TarjetaExpensa.jsx` — extracción de la definida en `Expensas.jsx`.

### Eliminar
- `frontend/src/components/ModalPresentarPago.jsx` — modal de pago asociado a expensa (verificar antes que no tenga otros usos; hoy solo lo importa `MiCuenta.jsx`).

### No tocar
- Backend completo, `openapi.yaml`, tests de pytest, `.claude/rules/*`.

## 5. Cómo lo prueba el usuario

- **Depto:**
  1. Login → aside muestra solo Mi cuenta en Finanzas.
  2. `/mi-cuenta` → tab Resumen con saldo + próximo vencimiento (sin botón de pago en la tarjeta).
  3. Un solo "Presentar pago" en el header; el modal pre-carga el monto con el saldo pendiente.
  4. Tabs Expensas / Comprobantes / Movimientos muestran las listas completas; el badge de estado de expensas coincide con lo que mostraba la pantalla vieja.
  5. Navegar por URL a `/expensas` → redirect a `/mi-cuenta?tab=expensas`. Ídem `/comprobantes` → `?tab=comprobantes`.
  6. Presentar un pago → mensaje de éxito, y el comprobante aparece en el tab Comprobantes como pendiente.
- **Admin:** pantallas Expensas y Comprobantes idénticas a hoy (incluyendo aprobar con selección de caja); aside sin cambios.
- **Representante:** sin cambios.
- **Mobile 375px:** tabs usables con touch, sin overflow horizontal.
- **Regresión backend:** `pytest -q` → 632 passed.

## 6. Fuera de scope

- Cambios de backend o de contrato (`openapi.yaml`).
- Notificaciones o emails nuevos.
- Paginación de las listas (los endpoints actuales no la exponen; si algún día hace falta, es otro ciclo).
- Rediseño de la vista admin de Expensas/Comprobantes.
- Persistir el tab activo fuera de la URL.

## 7. Riesgos y mitigación

- **Riesgo:** eliminar `ModalPresentarPago.jsx` rompe otro import. **Mitigación:** grep de usos antes de borrar; hoy solo lo usa `MiCuenta.jsx`.
- **Riesgo:** el redirect en `Expensas.jsx` se evalúe después de disparar cargas de datos de admin. **Mitigación:** el `<Navigate>` se retorna al inicio del render, antes de cualquier efecto condicionado por rol (los `useEffect` ya cortan por `esAdmin`).
- **Riesgo:** `?tab=` inválido o ausente. **Mitigación:** fallback a Resumen definido explícitamente.
- **Riesgo:** el tab Comprobantes del hub divergiera del comportamiento de la pantalla vieja para depto. **Mitigación:** reutilizar el mismo fetch (`listarComprobantes`) y el mismo markup de ítem; la pantalla vieja queda solo-admin.

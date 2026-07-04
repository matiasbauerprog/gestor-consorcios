# Hubs financieros: "Mi cuenta" (departamento) y "Cobranzas" (admin)

**Fecha:** 2026-07-04
**Estado:** Spec pendiente de revisión del usuario
**Rama sugerida:** `feature/hub-mi-cuenta`

## 1. Problema

La experiencia del rol **departamento** tiene información repetida y navegación por módulos que no le corresponde:

- El botón "Presentar pago" aparece dos veces casi pegadas en Mi cuenta (header + tarjeta "Próximo vencimiento"), con dos modales distintos.
- La lista de expensas aparece duplicada: en Mi cuenta (versión pobre, solo PDF) y en Expensas (versión rica, con badges de estado).
- El aside le muestra tres módulos financieros (Mi cuenta, Expensas, Comprobantes) que se pisan entre sí; Expensas incluso tiene un aviso "para presentar un pago andá a Mi cuenta".

Del lado **admin**, Expensas y Comprobantes son dos pantallas separadas de un mismo flujo de cobranza (emitir expensas ↔ aprobar los pagos que las cubren), con saltos de contexto entre ambas.

Principio de diseño: al admin le sirve navegación por módulos, pero módulos de un mismo flujo pueden agruparse; al usuario final le sirve navegación por **tareas**. El depto necesita UN lugar donde está toda su plata; el admin necesita UN lugar de cobranzas.

Dato contable clave que habilita la simplificación del pago: la imputación es **FIFO** (`backend/cuenta_corriente.py` — el crédito se acumula en un pool y se aplica a las expensas más viejas). Asociar un pago a una expensa específica no tiene ningún efecto contable, por lo que diferenciar "pago de tal expensa" vs "pago general" es cosmético y se elimina.

## 2. Solución

Dos hubs con tabs, cambio 100% frontend: cero endpoints nuevos, cero cambios en `openapi.yaml`, backend intocado.

- **`/mi-cuenta`** (departamento): Resumen | Expensas | Comprobantes | Movimientos.
- **`/cobranzas`** (admin, nueva ruta): Expensas | Comprobantes.

### 2.1 Hub del depto: estructura

`/mi-cuenta` con 4 tabs: **Resumen | Expensas | Comprobantes | Movimientos**

| Tab | Contenido | Origen actual |
|---|---|---|
| **Resumen** (default) | Tarjeta de saldo (con texto "estás al día / saldo pendiente / a favor") + tarjeta "Próximo vencimiento" **informativa** (montos y fechas 1°/2° vencimiento + botón Ver PDF, sin botón de pago) | `MiCuenta.jsx` actual |
| **Expensas** | Lista rica de expensas: badge de estado calculado, monto pendiente, Ver comprobantes, Ver PDF | `Expensas.jsx` (vista depto, vía `TarjetaExpensa`) |
| **Comprobantes** | Sus comprobantes con estado (pendiente_verificacion / aprobado / rechazado), solo lectura | `Comprobantes.jsx` (vista depto) |
| **Movimientos** | Tabla de cuenta corriente (fecha, tipo, descripción, monto con signo) | `MiCuenta.jsx` actual |

- El tab activo se sincroniza con la URL vía `useSearchParams`: `/mi-cuenta?tab=expensas`, `?tab=comprobantes`, `?tab=movimientos`. Sin parámetro (o valor inválido) → Resumen.
- Datos: cada tab consume los endpoints existentes ya documentados (`GET /movimientos` propios, `GET /expensas`, `GET /comprobantes`).

### 2.2 Flujo de pago único (depto)

- **Un solo botón "Presentar pago"** en el header del hub, visible desde cualquier tab.
- **Un solo modal** (el actual `ModalPresentarPagoGenerico`, hoy interno a `MiCuenta.jsx`): fecha del pago, monto, archivo (imagen/PDF). El monto viene pre-cargado con el saldo pendiente del depto si `saldo_total > 0`.
- Se elimina el modal asociado a expensa (`frontend/src/components/ModalPresentarPago.jsx`) y el estado `modalPago` dual (`"sin-expensa"` | objeto expensa) se simplifica a booleano.
- El mensaje de éxito se mantiene: "Comprobante enviado. Va a quedar pendiente hasta que administración lo apruebe."

### 2.3 Hub admin: Cobranzas

Nueva pantalla `frontend/src/screens/Cobranzas.jsx` en ruta `/cobranzas` (admin-only) con 2 tabs: **Expensas | Comprobantes**.

- Cada tab monta el contenido actual de la pantalla correspondiente **intacto**: filtros (departamento, período, estado), crear expensa, envío de PDFs por email, aprobar con selección de caja, rechazar, eliminar.
- Para embeberse, `Expensas.jsx` y `Comprobantes.jsx` cambian su elemento raíz de `<main className="pantalla">` a `<section>`; el `<main>` lo aporta el hub (o el layout). Su lógica interna no cambia.
- Tab activo sincronizado con `?tab=` igual que el hub depto; default: Expensas.
- El deep-link `?departamento_id=` que hoy usa Comprobantes (link "Ver comprobantes" desde Expensas) se conserva: `/cobranzas?tab=comprobantes&departamento_id=N`.

### 2.4 Aside y rutas

- `frontend/src/components/Sidebar.jsx`, grupo Finanzas:
  - `/expensas` y `/comprobantes` **se eliminan** del menú (para todos los roles).
  - Se agrega `/cobranzas` "Cobranzas" con `rolesPermitidos: ["administracion"]`.
  - `/mi-cuenta` no cambia.
  - Finanzas resultante — admin: Cobranzas, Historial de cierres, Gastos, Estado financiero, Cajas, Transferencias (6). Depto: Mi cuenta (1).
- **Matriz de redirects** (rutas viejas siguen funcionando por URL/historial):

| Ruta vieja | Depto | Admin |
|---|---|---|
| `/expensas` | `/mi-cuenta?tab=expensas` | `/cobranzas?tab=expensas` |
| `/comprobantes` | `/mi-cuenta?tab=comprobantes` | `/cobranzas?tab=comprobantes` (+`departamento_id` si viene) |

  Implementación: componentes de redirect por rol en `App.jsx` (o al inicio del render de cada screen vieja) con `<Navigate replace>`.
- Representante: no tiene acceso a estas rutas hoy y sigue sin tenerlo. Cero cambios.

### 2.5 Componentes y reuso

- **`Tabs`**: componente liviano compartido en `frontend/src/components/Tabs.jsx` (botones con `aria-selected`, panel activo; estilos con tokens del design system, mobile-first). Lo usan los dos hubs — DRY justificado con dos consumidores reales. Sin librerías nuevas.
- **`TarjetaExpensa`** se extrae de `Expensas.jsx` a `frontend/src/components/TarjetaExpensa.jsx` (misma implementación, prop `esAdmin` existente). La usan `Expensas.jsx` (admin) y el tab Expensas del hub depto (con `esAdmin=false`).
- El tab Comprobantes del hub depto reutiliza el markup de la vista depto de `Comprobantes.jsx` (lista con estado). Las acciones admin (aprobar/rechazar/eliminar) no entran a ese hub.
- Presentación de tabs del hub depto y de Cobranzas: mismo componente `Tabs`.

## 3. Contrato OpenAPI y documentación

- **Cero endpoints nuevos. `openapi.yaml` no se modifica.** Los hubs componen endpoints existentes y documentados. Regla `openapi-first.md` cumplida por vacuidad.
- `business-rules.md` sigue siendo válido sin edición: "Administración: crea expensas y ve el historial general" y "Departamentos: presentan comprobantes de pago y ven solo su propio historial" describen exactamente lo que hacen los hubs.
- Los permisos server-side no cambian: el frontend nunca fue la única barrera (defensa en profundidad ya existente).

## 4. Archivos afectados

### Modificar
- `frontend/src/screens/MiCuenta.jsx` — reorganizar en tabs, un solo botón/modal de pago, montar contenido de los 4 tabs, sincronización `?tab=`.
- `frontend/src/screens/Expensas.jsx` — raíz `<main>`→`<section>`, extraer `TarjetaExpensa` (queda import), redirect por rol si se accede directo.
- `frontend/src/screens/Comprobantes.jsx` — raíz `<main>`→`<section>`, redirect por rol si se accede directo.
- `frontend/src/components/Sidebar.jsx` — quitar Expensas/Comprobantes del menú, agregar Cobranzas (admin).
- `frontend/src/App.jsx` — ruta `/cobranzas`, redirects de `/expensas` y `/comprobantes`.
- `frontend/src/index.css` — estilos del componente Tabs (tokens existentes, mobile-first).

### Crear
- `frontend/src/screens/Cobranzas.jsx` — hub admin con tabs Expensas | Comprobantes.
- `frontend/src/components/Tabs.jsx` — componente de tabs compartido.
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
  5. Navegar por URL a `/expensas` → redirect a `/mi-cuenta?tab=expensas`. Ídem `/comprobantes`.
  6. Presentar un pago → mensaje de éxito, y el comprobante aparece en el tab Comprobantes como pendiente.
- **Admin:**
  1. Aside Finanzas muestra "Cobranzas" (sin Expensas ni Comprobantes sueltos).
  2. `/cobranzas` → tab Expensas con filtros, crear, enviar PDFs; tab Comprobantes con aprobar (selección de caja), rechazar, eliminar — todo idéntico a las pantallas viejas.
  3. "Ver comprobantes" desde una expensa lleva al tab Comprobantes con el depto filtrado.
  4. `/expensas` y `/comprobantes` por URL → redirect a `/cobranzas` con el tab correcto.
- **Representante:** sin cambios.
- **Mobile 375px:** tabs usables con touch, sin overflow horizontal.
- **Regresión backend:** `pytest -q` → 632 passed.

## 6. Fuera de scope

- Cambios de backend o de contrato (`openapi.yaml`).
- Notificaciones o emails nuevos.
- Paginación de las listas (los endpoints actuales no la exponen; si algún día hace falta, es otro ciclo).
- Hub por departamento para admin (`/departamentos/:id/cuenta` con tabs) — posible ciclo futuro.
- Persistir el tab activo fuera de la URL.

## 7. Riesgos y mitigación

- **Riesgo:** eliminar `ModalPresentarPago.jsx` rompe otro import. **Mitigación:** grep de usos antes de borrar; hoy solo lo usa `MiCuenta.jsx`.
- **Riesgo:** embeber Expensas/Comprobantes en Cobranzas duplique `<main>` o headers. **Mitigación:** cambiar la raíz de ambas a `<section>` y validar la jerarquía de headings (el hub aporta `<h1>`/`<h2>`; las secciones bajan un nivel si hace falta).
- **Riesgo:** el redirect pierda `?departamento_id=`. **Mitigación:** el redirect de `/comprobantes` copia los searchParams entrantes al construir el destino.
- **Riesgo:** `?tab=` inválido o ausente. **Mitigación:** fallback explícito (Resumen en Mi cuenta, Expensas en Cobranzas).
- **Riesgo:** el tab Comprobantes del hub depto divergiera de la pantalla vieja. **Mitigación:** reutilizar el mismo fetch (`listarComprobantes`) y el mismo markup de ítem.

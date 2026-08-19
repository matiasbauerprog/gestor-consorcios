# 🏗️ Estructura de Sidebar

Estado: **implementado**.

## Estructura (vista Admin — mapa completo)

```
🏠 Inicio                          ← link suelto, fuera de categorías

💰 FINANZAS
   ├─ Cobranzas
   │   ├─ Expensas                 ← pestañas dentro de la pantalla
   │   ├─ Comprobantes
   │   ├─ Cuentas corrientes
   │   └─ Historial de cierres
   ├─ Gastos
   ├─ Tesorería
   │   ├─ Resumen                  ← pestañas dentro de la pantalla
   │   ├─ Cajas
   │   └─ Transferencias
   └─ 📊 Reportes
       ├─ Lista de morosos
       ├─ Estado financiero
       ├─ Detalle de gastos
       └─ Lista de proveedores

🏢 GESTIÓN
   ├─ 📢 Comunicación
   │   └─ Comunicados
   ├─ 🔧 Mantenimiento
   │   ├─ Peticiones
   │   ├─ Trabajos
   │   └─ Trabajos recurrentes
   └─ 🏊 Espacios
       ├─ Reservas
       └─ Amenities

👥 PERSONAL
   ├─ Empleados
   ├─ Haberes
   ├─ Liquidaciones
   └─ Conceptos de liquidación

⚙️ CONFIGURACIÓN
   ├─ Datos del consorcio
   ├─ Consorcios de la administración
   ├─ Clases de prorrateo
   ├─ Proveedores
   └─ Usuarios y coeficientes
```

Las pestañas de Cobranzas y Tesorería **no** aparecen en el sidebar: son
navegación interna de esas pantallas (`?tab=`). Se listan arriba sólo para
dejar claro dónde vive cada cosa.

---

## Comparación: Antes vs Después

| Aspecto | Antes | Después |
|---|---|---|
| Categorías de nivel 1 | 8 secciones | 4 categorías + Inicio |
| Niveles de profundidad | 2 (sección → item) | 3 (categoría → sub-grupo → item) |
| "Comunicación" | Sección con 1 solo item | Sub-grupo dentro de Gestión |
| Cobranzas + Gastos + Finanzas | 3 secciones separadas | 1 categoría "Finanzas" |
| Reportes | Sección independiente | Sub-grupo dentro de Finanzas |
| Espacios comunes | Sección independiente | Sub-grupo dentro de Gestión |
| Operación | Sección independiente | Sub-grupo "Mantenimiento" dentro de Gestión |
| Cuentas corrientes | Item suelto en Finanzas | Pestaña dentro de Cobranzas |

---

## Vista por rol

### 🔴 Admin (mapa completo)
Ve todo lo de arriba. Las 4 categorías expandibles.

### 🟢 Departamento (lista simplificada)
Lista plana (sin accordions), reordenada:
```
🏠 Mi cuenta
📢 Comunicados
🔧 Peticiones
🏊 Reservas
📊 Reportes (si están habilitados)
    ├─ Morosos
    ├─ Estado financiero
    ├─ Detalle de gastos
    └─ Proveedores
```

### 🔵 Representante
```
🏠 Inicio (→ Comunicados)

🏢 GESTIÓN
   ├─ 📢 Comunicación → Comunicados
   └─ 🔧 Mantenimiento
       ├─ Peticiones
       ├─ Trabajos
       └─ Trabajos recurrentes

📊 REPORTES
   ├─ Morosos
   ├─ Estado financiero
   ├─ Detalle de gastos
   └─ Proveedores
```

> [!NOTE]
> Para el representante, "Reportes" queda como categoría de nivel 1 (no dentro
> de Finanzas) porque no ve Cobranzas/Gastos/Tesorería. No tiene sentido meterlo
> bajo "Finanzas" si sólo ve reportes.

### ⚫ Super Admin
Sin cambios — sidebar plana de 3 items.

---

## Decisiones de diseño tomadas

1. **4 macro-categorías** nombradas desde la perspectiva del administrador.
2. **"Finanzas"** unifica Cobranzas + Gastos + Tesorería + Reportes.
3. **"Gestión"** unifica Comunicación + Operación + Espacios comunes, con 3
   sub-grupos internos.
4. **"Personal"** y **"Configuración"** se mantienen igual.
5. **"Inicio"** como link suelto arriba de todo.
6. **Reportes** como sub-grupo colapsable dentro de Finanzas (para admin), pero
   como categoría propia para representante.
7. **Departamento** mantiene su lista plana simplificada.
8. **Cuentas corrientes vive dentro de Cobranzas**, como tercera pestaña.
   Ver abajo.

---

## Cuentas corrientes → pestaña de Cobranzas

**Por qué.** Las pestañas de Cobranzas son el ciclo del cobro (emitir la
expensa → recibir comprobantes → cerrar el período) y la cuenta corriente es el
resultado acumulado de repetir ese ciclo. Misma materia: plata que deben los
departamentos.

Se evaluó y se descartó meterla en Tesorería: esa sección responde "la plata que
tengo" (efectivo y bancos, dinero cierto), y la cuenta corriente responde "la
plata que me deben" (crédito). Son cosas de distinta naturaleza contable.

El contraargumento — que Expensas/Comprobantes son del mes en curso y la cuenta
corriente es transversal — no se sostiene: "Historial de cierres" tampoco es del
mes en curso y convive bien.

**Efecto colateral bueno:** Finanzas baja de 5 items de primer nivel a 4.

**Orden de pestañas** (sigue el recorrido natural del cobro):
`Expensas · Comprobantes · Cuentas corrientes · Historial de cierres`

### Cambios aplicados

| Archivo | Cambio |
|---|---|
| `screens/CuentasCorrientes.jsx` | Acepta `embebida`: renderiza `<section>` en vez de `<main>` y oculta su `<h2>` (el contador de mora se mantiene, es dato útil) |
| `screens/Cobranzas.jsx` | Cuarta pestaña `cuentas`, tercera en el orden |
| `navegacion.js` | Se quita la hoja `/cuentas-corrientes` de Finanzas; se agrega a `rutasRelacionadas` de Cobranzas para que el sidebar marque la sección correcta |
| `App.jsx` | `/cuentas-corrientes` redirige a `/cobranzas?tab=cuentas` (mismo patrón que `/periodos`, `/cajas`, etc.) |
| `screens/DepartamentoCuenta.jsx` | El breadcrumb "← Volver" apunta a `/cobranzas?tab=cuentas`, no al lugar viejo |

`MODULO_POR_RUTA` queda intacto a propósito: el mapa de colores semánticos es un
invariante y la ruta vieja sigue resolviendo a `cobranzas` durante el redirect.

---

## Resuelto: "Estado financiero" ya no está duplicado

Convivían dos pantallas con ese nombre y contenidos distintos:

1. **Pestaña de Tesorería** — total de plata, una tarjeta por caja, últimos 20
   movimientos, botón de transferir. Es un panel de caja. Admin-only.
2. **Reporte** (`/reportes/estado-financiero`) — activo / pasivo / patrimonio
   neto a una fecha de corte, con PDF. Lo ven también representantes y
   departamentos si los reportes están habilitados.

El nombre le corresponde al reporte, que es el balance de verdad. **La primera
pestaña de Tesorería pasó a llamarse "Resumen".**

Tesorería queda: `Resumen · Cajas · Transferencias`

### Cambios aplicados

| Archivo | Cambio |
|---|---|
| `screens/EstadoFinanciero.jsx` → `screens/ResumenTesoreria.jsx` | Renombrado el archivo, el componente y su `<h2>` |
| `api/estadoFinanciero.js` → `api/tesoreria.js` | `obtenerEstadoFinanciero` → `obtenerResumenTesoreria`. El nombre viejo chocaba con la función homónima de `api/reportes.js`, que recibe otros argumentos y devuelve otra cosa |
| `screens/Tesoreria.jsx` | Pestaña `estado` → `resumen`, y el default también |
| `screens/Inicio.jsx` | Consume el resumen para el tablero; actualizado el import |
| `App.jsx` | La ruta vieja `/estado-financiero` redirige a `/tesoreria?tab=resumen` |

Un link viejo con `?tab=estado` ya no matchea ningún valor y cae al default, que
es esa misma pantalla: no se rompe nada.

### El endpoint también se renombró

El backend servía los dos en paths casi idénticos: `/estado-financiero` (el
resumen) y `/reportes/estado-financiero` (el balance). El primero pasó a
`/tesoreria`, así que ya no hay dos endpoints con el mismo nombre.

| Archivo | Cambio |
|---|---|
| `openapi.yaml` | `/estado-financiero` → `/tesoreria`; schema `EstadoFinancieroOut` → `ResumenTesoreriaOut`; tag `EstadoFinanciero` → `Tesoreria`. **Se documentó `/tesoreria/movimientos-pdf`, que existía en el router pero no estaba en el contrato** |
| `routers/estado_financiero.py` → `routers/tesoreria.py` | Prefix, tag y nombre de la función; docstring aclarando la diferencia con el reporte |
| `schemas.py` | `EstadoFinancieroOut` → `ResumenTesoreriaOut` (chocaba con `EstadoFinancieroReporteOut`) |
| `main.py` | Import e `include_router` |
| `export_demo.py` | La ruta exportada al dataset de la demo |
| `tests/test_estado_financiero.py` → `tests/test_tesoreria.py` | URLs actualizadas |
| `api/tesoreria.js` (frontend) | Las dos llamadas |
| `demo/recorrido.test.js` | La ruta en la red de contención |
| `demo/dataset.json` | Regenerado con `SEED_ENABLED=false python -m backend.seed_demo --solo-exportar` (la clave del dataset es el path) |

`/reportes/estado-financiero` **no se tocó**: ese sí es el estado financiero.

---

## El contrato ahora tiene red: `tests/test_contrato_openapi.py`

La regla del proyecto es OpenAPI-first, pero nada la hacía cumplir. Al escribir
el test aparecieron los olvidos acumulados:

| Encontrado | Qué era |
|---|---|
| `GET /tesoreria/movimientos-pdf` | Endpoint real sin documentar (el descargador de movimientos) |
| `DELETE /comprobantes/{comprobante_id}` | Endpoint real sin documentar (soft-delete de comprobante) |
| `GET /movimientos/cuentas` | Endpoint real sin documentar — **el que alimenta la pantalla de Cuentas corrientes** |
| `GET /` | La raíz de la API, sin documentar |
| `BearerAuth` en 5 operaciones | El scheme se llama `bearerAuth`: eran 5 referencias rotas que no fallaban en ningún lado |
| `Super-Admin` en 2 paths | El tag declarado es `SuperAdmin`; esas operaciones quedaban fuera de su grupo en la documentación generada |
| Tags `Salud` y `Archivos` | Usados en paths, nunca declarados |

Todo eso quedó corregido y el contrato pasó de 163 a **166 operaciones, exactamente
las que la app expone**.

### Qué chequea el test

1. Ningún endpoint de la app falta en `openapi.yaml`.
2. Ningún endpoint del contrato dejó de existir en la app.
3. Todo tag usado en un path está declarado en `tags:`.

Compara **paths y verbos, no schemas**: alcanza para atrapar el olvido —que es
el error real— sin volverse un espejo frágil de cada campo.

**Dos detalles que el test resuelve en vez de ensuciar el contrato:**

- `/archivos/{clave:path}` — el `:path` es sintaxis de Starlette, no de
  OpenAPI. El contrato escribe `{clave}` y el test normaliza.
- `/auth/demo-login` sólo se registra con `DEMO_MODE` encendido ("Candado 2" en
  `main.py`), así que fuera del modo demo la app no lo expone aunque esté en el
  contrato. El test lo lee **del router de verdad**, no de una lista de
  excepciones escrita a mano: si el endpoint se borra, la excepción no queda
  mintiendo.

`pyyaml` pasó a estar declarado en `requirements.txt` — venía instalado como
dependencia transitiva y ahora es directo.

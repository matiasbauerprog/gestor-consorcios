# Densidad en desktop, pendiente fehaciente y recurrentes automáticos

Fecha: 2026-08-04

## Problema

Tres familias de problemas, encontradas revisando la app en uso:

1. **Un bug de negocio crítico.** El monto pendiente de una expensa vencida no
   contempla el recargo del segundo vencimiento. El sistema sub-cobra.
2. **Desaprovechamiento del espacio en tablet y desktop.** Expensas, Comprobantes,
   Gastos, Reservas y Amenities renderizan listas de tarjetas apiladas a ancho
   completo en cualquier viewport. En mobile está bien; de 600px para arriba
   desperdicia el ancho y obliga a scrollear de más.
3. **Fricción en la interacción.** Un botón "Cargar recurrentes" que el admin
   tiene que acordarse de apretar todos los meses, un "+ Nueva expensa" que nace
   deshabilitado, filtros que ocupan una columna entera, tabs que parecen
   botones, y el nombre del consorcio ilegible en el header.

## Alcance

Siete bloques de trabajo. Los bloques 1 y 2 tocan backend; el resto es frontend.

---

## 1. Pendiente fehaciente (crítico)

### Diagnóstico

`backend/cuenta_corriente.py:59` inicializa el pendiente de toda expensa con
`monto_primer_vencimiento`, y `:104` reporta ese mismo valor como `monto_total`.
Ninguno de los dos mira la fecha. Consecuencia: una expensa en estado `vencida`
(`:98`) muestra el monto **sin recargo**, y si el departamento paga ese importe
queda marcada `pagada` (`:93-95`). El recargo se pierde.

Hoy `monto_segundo_vencimiento` sólo se usa como texto informativo en la tarjeta
(`frontend/src/components/TarjetaExpensa.jsx:45`) y como fecha de corte para el
cálculo de intereses del cierre (`backend/cierre.py:130`).

### Diseño

El pendiente pasa a ser **el monto exigible en la fecha de consulta**:

| Momento | Exigible |
|---|---|
| `hoy <= fecha_primer_vencimiento` | `monto_primer_vencimiento` |
| `fecha_primer_vencimiento < hoy <= fecha_segundo_vencimiento` | `monto_segundo_vencimiento` |
| `hoy > fecha_segundo_vencimiento` | `monto_segundo_vencimiento` + interés punitorio diario |

`EstadoExpensaCalculado` gana tres campos, para que la UI muestre el desglose y
no un número opaco:

- `monto_exigible: float` — base según fecha, **sin** interés.
- `interes_acumulado: float` — punitorio devengado y todavía no capitalizado.
- `monto_pendiente: float` — `monto_exigible + interes_acumulado - pagado`.

`monto_total` pasa a reportar `monto_exigible` en lugar del primer vencimiento.

`calcular_estado_cuenta` necesita la tasa (`Consorcio.tasa_interes_mensual_pct`),
que resuelve navegando `Departamento -> consorcio_id`. Mantiene su firma actual
(`db, departamento_id, hoy`) y sigue siendo una función pura sin side effects.

El FIFO no cambia de forma: el crédito disponible se sigue aplicando a las
expensas más viejas primero. Lo único que cambia es que el techo de cada expensa
(`pendientes[e.id]`) ahora es el exigible y no el primer vencimiento.

### Las dos trampas

Son la razón de separar `monto_exigible` de `interes_acumulado`.

**Doble cobro de interés.** El cierre ya capitaliza intereses como
`MovimientoCuenta.interes_punitorio`. El interés "en vivo" tiene que cubrir sólo
el tramo posterior al último movimiento de ese tipo — exactamente la lógica que
ya vive en `cierre.py:116-134`. Esa lógica se extrae a una función compartida en
`cuenta_corriente.py` y `cierre.py` pasa a consumirla, para que no existan dos
implementaciones que puedan divergir.

**Interés sobre interés.** `cierre.py:138` calcula el punitorio usando
`calc.monto_pendiente` como base. Si ese campo ahora trae interés adentro, el
cierre compone interés sobre interés en cada corrida. Cambia a `monto_exigible`.

### Blast radius

`saldo_total` no se toca: sale de los movimientos de cuenta, no de las expensas.
Por eso quedan intactos `reportes.py:106`, `movimientos.py:97` y `cierre.py:370`,
que son sus únicos consumidores.

Los cuatro valores de `EstadoExpensa` (`pendiente`, `parcial`, `pagada`,
`vencida`) se mantienen. El detalle del recargo y el interés se muestra en la
fila, no en un estado nuevo — un quinto estado obligaría a tocar `BadgeEstado`,
el enum, la migración y los tests, sin agregar información que la fila no dé.

### Schema

`ExpensaOut` (`backend/schemas.py:200-213`) suma `monto_exigible` e
`interes_acumulado`. `monto_pendiente` mantiene su nombre y su tipo: cambia el
valor, no el contrato.

### Tests

`tests/test_cuenta_corriente.py` ya parametriza `hoy=` en todos sus casos, así
que los nuevos entran sin refactor. Casos a cubrir:

- Pago exacto del primer vencimiento hecho **después** del primer vencimiento:
  la expensa **no** debe quedar `pagada`; queda `parcial` por el recargo.
- Expensa entre primer y segundo vencimiento: exigible = segundo vencimiento,
  interés = 0.
- Expensa pasado el segundo vencimiento: interés > 0 y proporcional a los días.
- Expensa con un `interes_punitorio` ya capitalizado: el interés en vivo arranca
  desde la fecha de ese movimiento, no desde el segundo vencimiento.
- El cierre corrido dos veces seguidas no compone interés sobre interés.

---

## 2. Recurrentes automáticos

### Por qué no alcanza con automatizar el botón

`POST /gastos` y `POST /gastos/cargar-habituales` crean un `MovimientoCaja` de
egreso por cada gasto (`backend/routers/gastos.py:118-128`, invocado en `:223` y
`:493`). Crear el gasto **es** pagarlo: son un solo evento indivisible.

Materializar las plantillas solas el día 1 con ese modelo descontaría plata de la
caja por facturas que todavía no llegaron. La caja miente todo el mes, y si nadie
corrige el monto a mano, el consorcio liquida el importe de la plantilla en vez
del real.

Se evaluó y descartó diferir el egreso al cierre del período: evita el descuadre
del día 1 pero lo invierte (la caja informa plata que ya no está), rompe la
conciliación bancaria porque el movimiento queda fechado en el mes siguiente,
genera dos comportamientos distintos para la misma entidad según su origen, y no
ataca el problema real, que es el monto y no la fecha.

### Diseño

Separar "el gasto existe" de "el gasto se pagó".

**Modelo.** `Gasto` gana `pagado: bool` y `fecha_pago` pasa a nullable.
`pagado` tiene default `True` para que los gastos existentes no cambien de
comportamiento. Migración con `ALTER TABLE` idempotente al arranque en
`backend/main.py`, siguiendo el patrón ya establecido ahí (`main.py:60-112`).

**Materialización automática.** `GET /gastos` materializa las plantillas activas
que falten antes de responder, reusando la lógica de `cargar_habituales`, que ya
es idempotente (`gastos.py:463-476`). Los gastos nacen con `pagado=False`,
`fecha_pago=NULL` y **sin** `MovimientoCaja`.

Materializa sólo si el período consultado cumple **las dos** condiciones:

- **No está cerrado.** Un período cerrado ya liquidó sus expensas; agregarle
  gastos después las dejaría inconsistentes.
- **No es futuro** (`periodo <= mes actual`). Sin esta condición, navegar con las
  flechas de la barra de período hasta marzo de 2027 devengaría los recurrentes
  de todos los meses intermedios de golpe.

Un GET con efecto de escritura es una concesión deliberada: la alternativa es un
scheduler, que este proyecto no tiene y que agregaría infraestructura para un
caso que se resuelve con una operación idempotente. Queda documentado en el
docstring del endpoint.

Consecuencia buscada: los recurrentes de un mes aparecen la primera vez que
alguien abre Gastos en ese mes o después, no exactamente el día 1 a medianoche.
Para el flujo de trabajo del admin es equivalente, y evita el scheduler.

**Confirmación.** `POST /gastos/{id}/pagar` recibe monto real, fecha real y caja.
Valida que el gasto no esté ya pagado (409 si lo está) y que el período no esté
cerrado. Crea el `MovimientoCaja` y marca `pagado=True`.

**Prorrateo.** Sin cambios. `cierre.py:310` ya recorre todos los gastos del
período sin mirar el estado de pago, que es el comportamiento deseado: el
consorcio liquida lo devengado.

**Cierre.** Nueva `Validacion` de tipo `warning` (no bloqueante) si el período
tiene gastos con `pagado=False`, con el conteo.

**Frontend.** Desaparece el botón "Cargar recurrentes" (`Gastos.jsx:210-212`) y
su handler (`:130-139`). La tabla de gastos gana una columna Pago que muestra
"Confirmar" en las filas sin pagar.

---

## 3. El patrón responsive

### Decisión

Componente nuevo `frontend/src/components/ListaResponsive.jsx` más un hook
`frontend/src/hooks/useBreakpoint.js` basado en `matchMedia` (no existe ninguno
en el proyecto). Recibe la definición de columnas y las filas; en `>=600px`
renderiza una `<table>`, por debajo delega en un render de tarjeta que le pasa
cada pantalla.

Se descartó el enfoque CSS-only (una sola `<table>` restilada a bloques en mobile
con `data-label` y pseudo-elementos): obligaría a rehacer las tarjetas de mobile,
que hoy están bien y son el formato correcto para ese viewport.

Se descartó también renderizar ambos árboles y ocultar uno por CSS: duplica el
DOM y le da contenido repetido a los lectores de pantalla.

Breakpoint `600px`, el de tablet según `.claude/rules/frontend.md`.

### Barra de filtros

Clase compartida `.filtros-barra` (ya existe en `index.css:1740-1761`, hoy sin
comportamiento de desktop): apila en mobile y pasa a fila con controles a ancho
de contenido en `>=600px`. Reemplaza a `.filtros` en Comprobantes y a
`.filtros-gastos` en Gastos (`index.css:2192`), y absorbe los filtros sueltos del
header de Expensas.

Los controles nunca se estiran al ancho del contenedor — respeta la preferencia
ya establecida en el proyecto de ghost / `fit-content` de tablet para arriba.

---

## 4. Aplicación por pantalla

**Expensas** (`screens/Expensas.jsx`). Columnas: Período · Departamento ·
1er venc · 2do venc · Estado · Pendiente · Acciones. La columna Pendiente muestra
el desglose del bloque 1 (exigible + interés cuando lo hay). El botón
"+ Nueva expensa" sale del header: hoy nace deshabilitado hasta que se elige
departamento (`:135-141`), que es lo que lo vuelve ineficiente. Queda como acción
contextual una vez que hay departamento seleccionado.

**Comprobantes** (`screens/Comprobantes.jsx`). Columnas: Fecha · Departamento ·
Monto · Estado · Comprobante · Acciones. La imagen inline de hasta 240px de alto
(`.comprobante-img`, `index.css:1786-1794`) pasa a miniatura en la celda, con el
link al archivo completo. Es lo que hoy hace la lista interminable.

**Gastos** (`screens/Gastos.jsx`). Columnas: Concepto · Rubro · Proveedor ·
Clase/Depto · Caja · Monto · Pago · Acciones. La barra de período
(`.barra-periodo`) se mantiene: no es un filtro, es el contexto de trabajo.

En los tres casos el render de tarjeta de mobile conserva el markup actual.

---

## 5. Reservas y Amenities en desktop

**Reservas** (`screens/Reservas.jsx`). Hoy son cinco secciones apiladas a ancho
completo: filtro de amenity, banner de políticas, formulario, próximas reservas y
mis reservas. Pasa a grid de dos columnas en `>=960px`: a la izquierda el
formulario de reserva con las políticas del amenity arriba, a la derecha las
listas. Debajo de 960px sigue apilando en el orden actual.

"Próximas reservas" y "Mis reservas" dejan de ser tarjetas y pasan a tabla:
Fecha · Horario · Depto · Estado (+ acción cancelar en "Mis reservas").

**Amenities** (`screens/Amenities.jsx`). Grid de tarjetas `auto-fit` en vez de
columna única. Se mantiene el formato tarjeta y **no** pasa a tabla: cada amenity
es una ficha de configuración con cinco políticas en un `<dl>` (`:58-64`), no una
fila comparable contra las demás.

---

## 6. Tabs de Cobranzas

Tres correcciones sobre `components/TabsPanel.jsx` e `index.css:2338-2380`:

1. **Título duplicado.** `Cobranzas.jsx:29` renderiza "Cobranzas", y abajo la
   pantalla hija renderiza su propio `<h2>` ("Expensas" en `Expensas.jsx:115`,
   "Comprobantes" en `Comprobantes.jsx:183`). Las hijas reciben una prop para
   omitir su header cuando van embebidas en una tab.
2. **Se ve como botón.** La tab activa hoy tiene fondo `--color-primary-soft`
   (`:2376-2380`) y lee como botón presionado. Pasa a subrayado inferior.
3. **Bloque pesado.** `.tabs-panel` pierde la caja contenedora (fondo, borde,
   padding, `:2345-2350`) y `.tab-panel` baja de `min-height: 44px` a una altura
   tipográfica normal. Con eso "Historial de cierres" deja de forzar el wrap a
   dos filas en mobile.

El área táctil se mantiene por encima de 44px vía padding vertical, para no
violar la regla de targets táctiles del proyecto.

---

## 7. Contraste del nombre del consorcio

`.selector-consorcio-boton` usa `color: var(--color-text)` y
`border-color: var(--color-border-strong)` (`index.css:2392-2404`), pensados para
fondo claro. Pero el botón vive dentro de `.app-header`, cuyo fondo es
`var(--color-modulo)`, un color saturado (`index.css:422-423`). De ahí el nombre
del edificio en negro sobre color, ilegible.

Pasa a blanco con borde translúcido, el mismo tratamiento que ya resuelven bien
`.hamburguesa` (`:469-480`) y `.avatar-boton` en ese header.

Sólo afecta a usuarios con más de un consorcio: el selector se oculta con uno
solo (`SelectorConsorcio.jsx:21`).

---

## Verificación

- `pytest -v` en verde, con los casos nuevos del bloque 1 y del bloque 2.
- Cada pantalla tocada, usable a 375px de ancho (regla del proyecto).
- Las mismas pantallas a 768px y 1280px, mostrando tabla.
- Contraste del header verificado en los seis colores de módulo de la paleta.

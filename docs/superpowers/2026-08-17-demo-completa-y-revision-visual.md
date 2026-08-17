# La demo muestra la aplicación entera — y lo que eso destapó

**Fecha:** 2026-08-17
**Rama:** `feature/demo-completa`
**Spec relacionado:** [`specs/2026-08-16-demo-sin-backend-design.md`](specs/2026-08-16-demo-sin-backend-design.md) (§2.2 actualizada)

## Por qué

La demo publicada dejaba tres módulos —Tesorería, Personal y Configuración—
detrás de una pantalla que explicaba qué hacía cada uno. La idea era mostrar la
amplitud del producto sin tener que llenarlos de datos.

Vista funcionando, esa demo se leía como **un producto a medio terminar**: el
visitante entra a tres secciones seguidas y encuentra un cartel en vez de un
sistema. Es lo contrario de lo que una demostración tiene que transmitir.

El costo de destaparlas resultó bajo: dos de las tres ya tenían casi todos sus
datos exportados. Sólo faltaba declararlos.

## Qué cambió el alcance

La demo muestra hoy **toda la aplicación**. Lo único que queda afuera es la
consola de la plataforma (`/super-admin/*`) — métricas del negocio, alta y
suspensión de administraciones, auditoría, impersonación. Es la consola de
quien *provee* el sistema, no de quien administra un consorcio.

Las escrituras siguen el criterio "mirar todo, editar donde ya funciona": los
dos circuitos de venta, comunicados, peticiones y reservas escriben de verdad;
en el resto, al guardar aparece una explicación en castellano de que es una
demostración. Nunca un error técnico.

## Lo que la revisión visual destapó

Recorrer la aplicación entera pantalla por pantalla encontró once defectos.
**Ocho son del producto, no de la demo**: le pasan a cualquier administrador con
el sistema real.

### Del producto

| Qué | Por qué pasaba |
|---|---|
| El historial de liquidaciones aparecía vacío | "Del mes" e "Historial" son el mismo componente en dos rutas: React lo reutiliza y el estado inicial no se re-evalúa, así que el historial heredaba el filtro del mes en curso. Se corrige durante el render, no en un efecto, para que no haya parpadeo |
| "Presup. aprobado" y "Gasto" siempre en guión | El listado de trabajos no devolvía `presupuesto_aprobado_id` ni `gasto_id`. El modelo los tiene desde siempre; la respuesta no. Dos columnas muertas. Contrato actualizado en `openapi.yaml` |
| "Actividad reciente" mostraba sólo reservas | Las reservas de amenities son a futuro, tienen las fechas más altas y copaban las seis posiciones, tapando pagos y peticiones |
| "Próximos vencimientos" listaba uno ya vencido | Ordenaba por fecha pero no descartaba las pasadas |
| "17 De Agosto De 2026" | `text-transform: capitalize` sobre una fecha en castellano. También rompía nombres como "Edificio del Sol" |
| "1 peticiones sin responder" | Sin concordancia, en la primera pantalla del sistema |
| El tablero dejaba medio pantallazo vacío | La fila del grid tomaba la altura de la columna más alta y la agenda arrancaba recién debajo |
| Las casillas de filtro flotaban sobre su texto | Heredaban `flex-direction: column` de la regla base de `label`. En cinco pantallas |

Las comparaciones de fecha del tablero usan `parseFecha` (`utils/fechas.js`),
que pasó de privada a exportada: `new Date("2026-08-17")` se parsea como UTC y
en Argentina cae el día anterior, lo que cambia de lado un vencimiento de hoy.

### De la demo

| Qué | Por qué pasaba |
|---|---|
| La casilla "excluir saldos a favor y al día" no hacía nada | El export pedía el reporte con el default del endpoint (`solo_deudores=True`), así que el dataset sólo tenía a los deudores: al destildarla no había de dónde sacar el resto. Ahora se exporta el padrón completo y el recorte lo hace el navegador, con el mismo umbral que `calcular_morosos` |
| "Consorcios de la administración" decía que no había ninguno | Faltaba `/consorcios` en el export |
| El detalle de un trabajo desbordaba | La tabla de presupuestos no entra en los 560px del modal y cortaba los botones. Nueva variante ancha |

## Datos de demostración

Lo que se agregó o corrigió en el generador, todo por el mismo motivo: se
notaba en cámara que eran datos inventados.

- **Segunda caja y transferencias.** Con una sola caja la pestaña
  Transferencias no tenía nada que mostrar. Hay una caja chica con reposiciones
  mensuales de monto y día variables, y una devolución al banco.
- **Trabajos recurrentes.** Cuatro tareas programadas con su proveedor. Van
  atadas a la razón social y no al rubro: no salen de `RUBROS_COMUNES`, así que
  el emparejador por rubro las habría mandado a las cuatro al mismo proveedor.
- **Los reclamos cuentan un problema distinto cada uno.** Antes el título salía
  por sorteo con repetición y los tres trabajos compartían la descripción
  "Trabajo generado a partir del reclamo del depto.".
- **El presupuesto lo gana el proveedor del rubro.** Antes se sorteaba entre
  todos: la empresa de limpieza ganaba el arreglo del ascensor.
- **Un trabajo recorre el circuito completo.** Hasta el gasto que lo cierra —
  `POST /completar` no completa nada pese al nombre, sólo devuelve el gasto
  pre-cargado; lo que cierra el trabajo es dar de alta ese gasto con
  `trabajo_id`.
- **El domicilio dejó de ser "Av. Siempreviva"**, el chiste que trae el
  banco de pruebas.

## El guardián del exportador

El exportador ahora **corta si una ruta declarada devuelve un error**.

Sin eso, una ruta mal escrita no rompe nada visible: el backend contesta 404 o
405, el cuerpo del error (`{"detail": ...}`) se guarda en el dataset como si
fueran datos, y la pantalla que lo consume aparece vacía sin que nadie se
entere. Pasó con dos rutas reales —`/coeficientes`, que no existe como listado,
y `/amenities/{id}/reservas`, que es sólo POST— y el guardián las encontró.

Las claves del dataset se guardan **sin query string**: el sustituto del
navegador busca por path limpio y aplica los filtros aparte, así que una clave
con el `?` adentro no se encontraría nunca.

## Decisiones tomadas

**Los seis reclamos quedan fechados el mismo día.** `fecha_creacion` de
peticiones la pone la base (`server_default=func.now()`), no la API.
Escalonarlos exigiría agregarle un campo de fecha al backend sólo para maquillar
la demo. Se dejó como está.

**El aviso de sólo lectura sale en el color de error.** No es un error, pero
comunica bien "la acción no se completó", y distinguirlo exigiría tocar todas
las pantallas o inventar un mecanismo global.

## Verificación

- 1070 pruebas de backend, 261 de frontend.
- Lint sin deuda agregada: 86, el mismo conteo que `master`.
- Con el modo demo apagado, el bundle de producción no cambia: el dataset no
  entra.
- Recorrido en el navegador con el backend detenido.

**Pendiente:** la revisión a 375px del tablero rediseñado. La ventana estaba
maximizada y no aceptaba redimensionarse. El cambio de acomodo vive dentro del
diseño de pantalla grande, así que móvil no debería haberse movido.

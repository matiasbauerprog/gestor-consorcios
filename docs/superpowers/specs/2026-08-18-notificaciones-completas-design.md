# Notificaciones completas — catálogo de eventos, pendientes y preferencias

Fecha: 2026-08-18
Estado: diseño aprobado, pendiente de plan de implementación

## Problema

El sistema de notificaciones de Fase 11 cubre cuatro eventos, todos dirigidos al
departamento. La administración no recibe nada: que entró una petición, que un
depto subió un comprobante, que hay algo esperando aprobación — todo eso hay que
salir a buscarlo pantalla por pantalla. Del lado del vecino faltan los avisos que
más importan: comunicado nuevo, expensa emitida, comprobante aprobado o rechazado.

Además, cada aviso existente está escrito a mano como una función propia. Sumar
ocho eventos por esa vía multiplica por doce la lógica de destinatarios, de canal
y de preferencias, y basta olvidarse en un lugar para que se escape un mail que
el usuario había apagado.

## Decisiones tomadas

| Pregunta | Decisión |
|---|---|
| ¿A quién notificamos? | Departamento **y** administración. Representantes quedan fuera de este alcance. |
| ¿Cómo evitamos el spam de mail? | Default por evento + interruptor por usuario que apaga **solo el mail**. |
| ¿Alcanza el panel de la campanita? | No: panel + pantalla completa con historial, filtro y buscador. |
| ¿Qué ve un admin con varios consorcios? | Lo del consorcio activo, más un contador de pendientes en los otros. |
| ¿Qué pasa con un pendiente ya resuelto? | Se apaga solo para todos los destinatarios cuando la acción se completa. |
| ¿Tiempo real? | No. Sigue el polling de 60 s que ya existe. |
| ¿Purga de avisos viejos? | No. Volumen bajo; la pantalla completa pagina. |

## Arquitectura

### El catálogo

`backend/notificaciones.py` pasa a ser el paquete `backend/notificaciones/`:

- `catalogo.py` — la definición declarativa de los doce eventos.
- `emisor.py` — `emitir()` y `resolver_pendiente()`.
- `destinatarios.py` — resolución de audiencias a listas de usuarios.
- `correo.py` — armado y encolado del mail diferido.
- `__init__.py` — reexporta `emitir` y `resolver_pendiente`; nada más es público.

Cada evento se declara una vez:

```python
@dataclass(frozen=True)
class EventoNotificacion:
    clave: str                                   # "peticion_nueva"
    audiencia: Audiencia                         # DEPARTAMENTO | ADMINISTRACION
    etiqueta: str                                # nombre humano, para la pantalla de preferencias
    mensaje: Callable[[dict], str]               # contexto -> texto de la campanita
    link: Callable[[dict], str | None]
    crea_campanita: bool = True                  # False = evento sólo-mail
    email_por_defecto: bool = False
    asunto: Callable[[dict], str] | None = None  # None ⇒ el evento nunca manda mail
    cuerpo: Callable[[dict], str] | None = None
    entidad_tipo: str | None = None              # no-None ⇒ es un pendiente
```

`entidad_tipo` es lo único que distingue un pendiente de un aviso informativo. Un
evento con `entidad_tipo="peticion"` guarda a qué petición se refiere y puede
apagarse solo; uno sin él sólo se apaga cuando el usuario lo lee.

### El emisor

```python
def emitir(
    db: Session,
    clave: str,
    *,
    consorcio_id: int,
    contexto: dict,
    actor_usuario_id: int | None,
    departamento_id: int | None = None,
    entidad_id: int | None = None,
    tareas: BackgroundTasks | None = None,
) -> None
```

Responsabilidades, en orden:

1. Busca el evento en el catálogo. Clave desconocida ⇒ `KeyError` (falla en tests,
   nunca en producción, porque las claves son constantes del módulo).
2. Resuelve destinatarios según la audiencia.
3. **Descarta a `actor_usuario_id`.** Nadie recibe su propio evento.
4. Si `crea_campanita`, agrega una fila `Notificacion` por destinatario, con
   `tipo=clave` y, si el evento es un pendiente, `entidad_tipo` + `entidad_id`.
   **No commitea** — el caller ya está dentro de la transacción de su operación.
5. Para cada destinatario con mail y con la preferencia en on, materializa el
   `(to, subject, body)` completo y lo encola en `tareas`. Si `tareas is None`
   (tests, scripts), envía en línea.

`resolver_pendiente(db, *, consorcio_id, entidad_tipo, entidad_id)` marca
`leida=True` todas las notificaciones no leídas que apunten a esa entidad, de
todos los usuarios. Tampoco commitea.

### Destinatarios

- `Audiencia.DEPARTAMENTO` — usuarios con `rol=departamento` y
  `departamento_id == departamento_id`. Requiere que el caller pase
  `departamento_id`; si no lo pasa, `ValueError`.
- `Audiencia.ADMINISTRACION` — usuarios con `rol=administracion` cuyo
  `administracion_id` sea el de la administración dueña de `consorcio_id`
  (`Consorcio.administracion_id`). Sólo usuarios con `activa=True`.

### Mail diferido

Hoy el correo se manda dentro de la operación. Un comunicado a 40 departamentos
son 40 handshakes SMTP con el request abierto. Pasa a `BackgroundTasks`:

- El endpoint declara `tareas: BackgroundTasks` y lo pasa al emisor.
- **El payload del mail se materializa antes de encolar.** La tarea de fondo
  corre después de que la sesión de request se cerró; no puede tocar `db`.
- Si el envío falla, la tarea abre **su propia sesión** (`SessionLocal`) y llama
  a `errores.registrar(...)` con `ruta="notificaciones/<clave>"`. La campanita ya
  quedó persistida por la transacción original, así que el aviso no se pierde.
- Un fallo de correo nunca puede propagarse a la respuesta del usuario: la tarea
  atrapa todo.

### Dos cambios sutiles de comportamiento

Los anoto porque son fáciles de romper sin querer al mudar los eventos:

- **`reserva_confirmada` hoy se emite después del `commit`**, no antes. Al
  mudarlo al emisor pasa a emitirse dentro de la transacción, como todos los
  demás. El mail sale igual (encolado, después de la respuesta), pero si la
  reserva falla al guardarse ya no se manda un correo de una reserva que no
  existe. Es una mejora, no un efecto colateral.
- **La petición borrada por el depto emite antes del `delete`.** El orden importa:
  resolver el pendiente y emitir el informativo, y recién entonces borrar.

## Modelo de datos

### `notificaciones` (tabla existente, tres columnas nuevas)

| Columna | Tipo | Nota |
|---|---|---|
| `tipo` | `String(60)`, NOT NULL, index | clave del catálogo |
| `entidad_tipo` | `String(40)`, nullable | `"peticion"`, `"comprobante"` |
| `entidad_id` | `Integer`, nullable | |

Índice compuesto `(consorcio_id, entidad_tipo, entidad_id, leida)` para que el
apagado de pendientes sea una sola query.

Migración: las filas existentes reciben `tipo` según su origen. Como no hay forma
de distinguirlas retroactivamente por el mensaje, se les asigna
`tipo="legacy"`; no rompe nada porque `tipo` sólo se usa para preferencias y para
el apagado, y las viejas no son pendientes.

### `preferencias_notificacion` (tabla nueva)

| Columna | Tipo |
|---|---|
| `id` | PK |
| `usuario_id` | FK `usuarios.id` ON DELETE CASCADE, index |
| `tipo` | `String(60)`, NOT NULL |
| `email_activo` | `Boolean`, NOT NULL |

Único `(usuario_id, tipo)`.

**Sólo se persisten las diferencias contra el default.** Si un usuario nunca tocó
un interruptor, no tiene fila y le vale `email_por_defecto` del catálogo. Cambiar
un default más adelante alcanza a todos los que no lo tocaron y respeta a los que
sí. Poner un interruptor en su valor por defecto borra la fila.

## El catálogo de eventos

Doce eventos. Los cuatro primeros ya existen y se mudan sin cambiar lo que el
usuario ve.

### Al departamento

| Clave | Se dispara en | Campanita | Mail default | Pendiente |
|---|---|---|---|---|
| `peticion_estado_cambiado` | `PATCH /peticiones/{id}` (rechazo), `POST /trabajos` (conversión), `POST /trabajos/{id}/cancelar` (cascada) | sí | sí | no |
| `trabajo_completado` | `POST /gastos` con `trabajo_id` | sí | no | no |
| `reserva_confirmada` | `POST /amenities/{id}/reservas` | **no** | sí | no |
| `reserva_cancelada_por_admin` | `DELETE /reservas/{id}` por admin | sí | sí | no |
| `comunicado_publicado` | `POST /comunicados` | sí | sí | no |
| `expensa_emitida` | `POST /periodos/{periodo}/cerrar` | sí | sí | no |
| `comprobante_aprobado` | `PATCH /comprobantes/{id}` → aprobado | sí | no | no |
| `comprobante_rechazado` | `PATCH /comprobantes/{id}` → rechazado | sí | sí | no |

`comprobante_rechazado` incluye el `motivo_rechazo` en el mensaje y en el cuerpo
del mail. `expensa_emitida` emite una notificación por departamento con expensa
generada en el cierre; el mail de la boleta con PDF adjunto sigue siendo el envío
manual que ya existe y **no** se toca.

### A la administración

| Clave | Se dispara en | Campanita | Mail default | Pendiente |
|---|---|---|---|---|
| `peticion_nueva` | `POST /peticiones` | sí | no | `peticion` |
| `comprobante_presentado` | `POST /comprobantes` | sí | no | `comprobante` |
| `peticion_borrada_por_depto` | `DELETE /peticiones/{id}` hecho por el propio depto | sí | no | no |
| `reserva_nueva_de_depto` | `POST /amenities/{id}/reservas` | sí | no | no |

### Resolución de pendientes

| Entidad | Se resuelve cuando |
|---|---|
| `peticion` | la petición deja de estar `abierta` (rechazo o conversión) **o** se borra, por quien sea |
| `comprobante` | `PATCH /comprobantes/{id}` lo lleva a aprobado o rechazado |

El borrado merece una aclaración. El departamento no "cancela" su petición: la
**borra**, y sólo si sigue abierta (`DELETE /peticiones/{id}`). Ese request tiene
que hacer dos cosas antes del `delete`: resolver el pendiente `peticion_nueva` —
si no, el administrador queda con un pendiente que apunta a una petición que ya
no existe — y emitir `peticion_borrada_por_depto`, que es informativo. El
administrador también puede borrar peticiones; en ese caso sólo se resuelve el
pendiente y no se emite nada, porque el filtro de actor descarta al único
destinatario posible que hay del otro lado.

`entidad_id` es un entero suelto, no una foreign key. Es a propósito: la
notificación tiene que sobrevivir al borrado de la cosa que la originó.

### Fuera de alcance, explícitamente

- **Vencimientos y mora.** Requieren un proceso programado diario que el proyecto
  no tiene. Cuando exista, son dos entradas más en el catálogo.
- **Representantes.** El catálogo soporta una tercera audiencia sin cambios
  estructurales; se agrega cuando se decida.
- **Presupuestos.** Los carga y los aprueba el mismo par de roles; no hay traspaso
  de responsabilidad que avisar.

## API

Contrato OpenAPI-first: todo esto va a `openapi.yaml` antes de implementarse.

### Modificados

**`GET /notificaciones`** — ahora filtra por consorcio activo. Parámetros nuevos:

| Param | Tipo | Default |
|---|---|---|
| `solo_no_leidas` | bool | `false` |
| `q` | string \| null | `null` — busca en `mensaje`, case-insensitive |
| `offset` | int ≥ 0 | `0` |
| `limit` | int 1..100 | `50` |

`NotificacionOut` suma `tipo`. `entidad_tipo` y `entidad_id` son de uso interno y
no se exponen: el frontend no los necesita para nada.

**`GET /notificaciones/no-leidas-count`** — `NotificacionesCountOut` suma
`otros_consorcios: int`: no leídas del usuario en consorcios distintos del activo
que igualmente le pertenecen. Para departamento y representante es siempre `0`.

**`POST /notificaciones/{notificacion_id}/marcar-leida`** y
**`POST /notificaciones/marcar-todas-leidas`** — pasan a depender del consorcio
activo; "todas" alcanza sólo al consorcio activo.

### Nuevos

**`GET /notificaciones/preferencias`** → `list[PreferenciaNotificacionOut]`

```
tipo: str
etiqueta: str
email_activo: bool   # efectivo: la fila del usuario, o el default del catálogo
editable: bool
motivo_no_editable: str | None
```

Devuelve sólo los eventos cuya audiencia corresponde al rol del usuario.

`editable=False` en dos casos, y en ambos el valor se muestra pero no se puede
tocar:

- el evento nunca manda mail (`asunto is None`) — no hay nada que apagar;
  `motivo_no_editable="Sólo aparece en la campanita."`
- el evento es sólo-mail (`crea_campanita=False`, hoy únicamente
  `reserva_confirmada`) — apagarlo dejaría al usuario sin ningún aviso, ni
  campanita ni correo; `motivo_no_editable="Sólo se envía por correo."`

**`PUT /notificaciones/preferencias`** → 204. Body: `list[{tipo, email_activo}]`.
Un `tipo` fuera del catálogo, ajeno al rol del usuario, o con `editable=False`
⇒ 400.

## Frontend

**Campanita.** El panel mantiene su forma actual (diez recientes, punto discreto,
punto por ítem con el gutter reservado). Suma:

- un engranaje en el encabezado, a `/notificaciones/preferencias`;
- un "Ver todas" al pie, a `/notificaciones`;
- cuando `otros_consorcios > 0`, una línea al pie: *"N sin leer en otros
  consorcios"*, que abre el selector de consorcio. Oculta para departamento y
  representante.

**Pantalla `/notificaciones`.** Lista cronológica del consorcio activo, con:
filtro leídas / no leídas, buscador por texto, carga progresiva por `offset`, y
"Marcar todas". Clic navega al `link` del aviso y lo marca leído, igual que en el
panel. Densidad según la regla del proyecto: fiel al mockup en mobile,
`fit-content` en tablet y desktop.

**Pantalla `/notificaciones/preferencias`.** Una fila por evento del rol, con la
etiqueta del catálogo y un interruptor de mail. Los eventos con
`email_disponible=false` se muestran deshabilitados con la leyenda "sólo en la
campanita". Guardado explícito con un botón, no al vuelo — evita un `PUT` por
cada toque.

**La campanita nunca se puede apagar.** No hay interruptor para eso en ningún
lado: apagarla es dejar de recibir trabajo sin saberlo.

## Modo demo

La demo resuelve lecturas por coincidencia exacta de path contra el dataset
exportado. Hace falta:

- exportar `/notificaciones/preferencias` en el dataset;
- que `escrituras.js` maneje el `PUT` de preferencias sobre el estado en memoria;
- que el contador exportado incluya `otros_consorcios: 0`;
- sumar las rutas nuevas a la lista de paths obligatorios de `recorrido.test.js`.

El correo en demo ya está forzado a modo consola; el mail diferido no cambia eso.

## Pruebas

Un archivo por área: `tests/test_notificaciones.py` (emisor, catálogo,
preferencias, endpoints) y las aserciones de emisión dentro del test del router
que dispara cada evento.

Por cada uno de los ocho eventos nuevos:

1. **Llega a quien tiene que llegar** — un destinatario por usuario de la
   audiencia, con el `tipo` correcto.
2. **No le llega al actor** — quien causó el evento no tiene fila.
3. **Aislamiento de consorcio** — un admin de otra administración no ve nada;
   un admin con dos consorcios no ve el ajeno en el listado del activo.

Transversales:

4. **El pendiente se apaga al resolverse**, incluido el caso de un segundo
   administrador que nunca lo leyó.
5. **El interruptor apagado no manda mail y la campanita igual llega.**
6. **Un fallo de SMTP no rompe la operación**: el endpoint devuelve 2xx, la
   notificación quedó, y se registró un error con código.
7. **`otros_consorcios`** cuenta lo de los otros consorcios y nunca lo del activo.
8. **Preferencias**: default sin fila; poner en no-default crea fila; volver al
   default borra la fila; `tipo` ajeno al rol ⇒ 400.

### Qué pasa con los tests actuales

Los que ejercitan un evento **a través de la API** no se tocan. Que sigan verdes
sin una sola línea modificada es la prueba de que la mudanza al catálogo no
cambió comportamiento. Están en `tests/test_peticiones.py`,
`tests/test_trabajos.py` y `tests/test_reservas.py`.

Dos de ellos imponen restricciones concretas sobre el catálogo, y hay que
respetarlas:

- `test_trabajos.py` filtra por `Notificacion.mensaje.contains("convertida_en_trabajo")`.
  El texto de `peticion_estado_cambiado` **tiene que seguir incluyendo el valor
  crudo del estado**, tal como hoy.
- `test_reservas.py::test_depto_cancela_su_reserva_no_genera_notificacion`
  cuenta filas totales antes y después. Que un depto cancele su propia reserva
  tiene que seguir sin generar **ninguna** notificación, ni a él ni al
  administrador.

Los tres tests de `tests/test_notificaciones.py` que llaman a los helpers viejos
(`crear_notificacion`, `notificar_cambio_estado_peticion`) sí se reescriben contra
`emitir`, en la misma tarea que borra esos helpers. No hay forma de conservarlos:
prueban funciones que dejan de existir.

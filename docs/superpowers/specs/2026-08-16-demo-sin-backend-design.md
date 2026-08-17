# Demo sin backend: la demo pública corre entera en el navegador

**Fecha:** 2026-08-16
**Estado:** Implementado. Alcance ampliado el 2026-08-17 — ver §2.2.
**Rama sugerida:** `feature/demo-sin-backend`

> **Actualización 2026-08-17.** El alcance original dejaba tres módulos fuera
> del recorrido, detrás de una pantalla explicativa. Al verlo funcionando, esa
> demo se leía como un producto a medio terminar. Hoy la demo muestra la
> aplicación entera y lo único que queda afuera es la consola de la
> plataforma. Las secciones §2.1, §2.2, §4.3, §5.2 y §9 están actualizadas a
> ese alcance; el resto del spec no cambió.

## 1. Problema

La demo pública de hoy depende de infraestructura que ya falló y que no hay
presupuesto para sostener hasta conseguir los primeros clientes:

- **El backend está caído.** Render devuelve `503` con `x-render-routing: suspend`
  ("This service has been suspended") tanto en `/auth/demo-login` como en
  `/health`. El frontend de Vercel carga, el visitante hace clic y recibe un
  error. El link que sale de la landing hoy no funciona.
- **Todos los visitantes comparten el mismo dataset y escriben sobre él.** En la
  última inspección había un gasto llamado `dasasd` de $213 cargado por alguien
  que pasó por ahí. Cualquiera puede dejarle basura —u obscenidades— al
  siguiente durante hasta 6 horas.
- **El reset depende de un cron cada 6 h** que, según el README, nunca corrió
  contra un Postgres real: su primera ejecución en producción es también su
  primera prueba.
- **Costos y vencimientos:** el plan gratuito de Render da 750 horas-instancia y
  mantener el servicio despierto 24/7 las consume casi enteras; el Postgres
  gratuito expira a los 90 días.

Además, el dataset actual tiene incoherencias que se ven en cámara y que hoy se
regeneran cada 6 h (ver §3.2).

Restricción dura del proyecto: **no hay presupuesto para infraestructura hasta
que haya clientes.**

## 2. Solución

La demo se sirve como **archivos estáticos** y corre entera en el navegador del
visitante. Un módulo sustituye al servidor: recibe los pedidos que hoy salen a
la red y los responde desde un estado en memoria, sembrado con datos generados
por el backend real.

Esto conserva la propiedad más valiosa del estándar de la industria (un sandbox
por visitante) sin pagar infraestructura: **los datos de cada visitante viven en
su propia máquina**, así que nadie puede ensuciar ni ver la demo de otro. No hay
servidor que se duerma, ni cron que fallar, ni reset que programar.

### 2.1 Alcance: el recorrido de venta

Dos circuitos funcionan de punta a punta, en vivo:

**Circuito 1 — la plata que entra.** El propietario presenta un pago con su
comprobante → se cambia a Administración → lo aprueba → el pago se imputa a la
deuda más vieja → baja el saldo de esa unidad → desaparece de la lista de
morosos.

**Circuito 2 — la plata que sale.** Administración carga un gasto → va a cerrar
el período → las validaciones avisan qué falta → confirma → el gasto aparece
repartido por coeficiente en las 18 expensas, con el importe de cada unidad
recalculado.

Pantallas del recorrido: Inicio, Gastos, Cobranzas (expensas y comprobantes),
Cierre de período, Mi cuenta del propietario, Comunicados, Reservas, Peticiones,
y los cuatro reportes.

Acciones sueltas incluidas porque salen casi gratis y dan textura: publicar un
comunicado (que el propietario ve al cambiar de rol), reservar el SUM (que
genera su cargo en la cuenta corriente) y crear una petición de arreglo.

### 2.2 Fuera de alcance: sólo la consola de la plataforma

**Decisión original (2026-08-16):** Tesorería, Personal y Configuración
quedaban fuera del recorrido, detrás de una pantalla que explicaba qué hace
cada módulo. La amplitud del producto es argumento de venta, así que seguían
apareciendo en el menú en vez de esconderse.

**Corregido el 2026-08-17:** tres secciones con un cartel en lugar de datos se
leen como un producto sin terminar, que es justo lo contrario de lo que la
demo tiene que transmitir. Y el costo de destaparlas resultó bajo: dos de las
tres ya tenían casi todos sus datos en el dataset, sólo faltaba declararlos en
el exportador.

Hoy la demo muestra **la aplicación entera**. Lo único fuera de alcance es la
**consola de la plataforma** (`/super-admin/*`): métricas del negocio, alta y
suspensión de administraciones, registro de auditoría e impersonación. Esa
consola es de quien *provee* el sistema, no de quien administra un consorcio;
no tiene sentido mostrarle al visitante por dónde se le suspende la cuenta.

No aparece en el menú de ningún rol de la demo. La pantalla explicativa
(`ModuloNoIncluido`, con su catálogo en `modulosNoIncluidos.js`) sigue
existiendo para quien llegue escribiendo la dirección a mano.

**Qué puede tocar el visitante.** Todas las pantallas se ven con datos reales.
Escriben de verdad los dos circuitos de venta (§2.1) más comunicados,
peticiones y reservas. En el resto, al guardar aparece una explicación en
castellano de que es una demostración, con la invitación a probar los
circuitos que sí impactan — nunca un error técnico (§4.3).

### 2.3 Persistencia: arranca limpio en cada visita

El estado vive en memoria. Los cambios del visitante persisten mientras navega y
se pierden al recargar, volviendo al edificio impecable del arranque.

Razón: la demo siempre luce igual de bien y nadie se encuentra con su propio
desorden de la visita anterior —ni se lo muestra a un socio al compartir
pantalla. Es también lo más simple y lo que menos puede fallar.

### 2.4 Cambio de rol instantáneo

Un control siempre visible permite saltar entre Administración y Propietario sin
perder el estado. No hay autenticación real: cambiar de perfil es cambiar quién
dice ser el pedido.

**Este control existe únicamente con la bandera de demo encendida.** En la
aplicación que usa un cliente no aparece: ahí la identidad la da el token y
cambiar de rol sin credenciales sería un agujero de seguridad, no una comodidad.

Razón: habilita el momento más vendedor del sistema —el propietario presenta el
pago, se cambia a administración, se aprueba y la deuda se actualiza— en veinte
segundos y sin cortes. Hoy ese hilo se corta obligando a volver al selector.

## 3. Los datos iniciales

### 3.1 Se generan, no se escriben

`backend/seed_demo.py` ya puebla seis meses de operación **llamando a la propia
API del sistema** con `TestClient` in-process: los saldos, la imputación FIFO y
los intereses los calcula el código de producción.

Se le agrega un paso final: recorrer la base recién generada y volcar un archivo
con los datos **ya en la forma en que los devuelve cada endpoint**. Ese archivo
se versiona en el repo y es el estado con el que arranca cada visitante.
Regenerarlo es correr un comando.

Consecuencia importante: los datos no pueden despegarse del contrato real,
porque salen de él.

**Historia incluida:** seis meses. Hacen que el edificio se sienta real —morosos
con antigüedad, cierres anteriores, un semestre de gastos— y el peso es de unos
pocos cientos de kilobytes comprimidos.

### 3.2 El dataset se cura una vez y queda congelado

Estos siete defectos existen hoy y se regeneran cada 6 h. Se corrigen en el
generador:

1. **Proveedores incoherentes con el rubro.** Hoy se asignan al azar: "Honorarios
   administración → Limpieza Total SRL", "Seguro integral consorcio → ElectroSur
   SRL", "Comisiones bancarias → Ascensores Vertirod SA". Un administrador lo
   nota en dos segundos. Mapear rubro → proveedor plausible.
2. **Todas las expensas emitidas el mismo día.** Los movimientos `expensa_emitida`
   llevan la fecha de generación del seed (las seis, el mismo día), mientras los
   recargos sí tienen fecha mensual correcta.

   **La causa está en el backend, no en el generador:** `routers/periodos.py:145`
   hace `hoy = date.today()` y con eso fecha los movimientos de emisión
   (línea 183). Como el generador cierra los seis períodos en un minuto, los seis
   quedan fechados hoy. No se puede corregir pasando un parámetro.

   La solución que respeta el "sin cambios en el backend": el generador **simula
   el paso del tiempo** al cerrar cada período, parcheando el reloj del módulo de
   períodos con `unittest.mock.patch` (stdlib, sin dependencias nuevas) al día de
   cierre que corresponde a ese período. Corrige de una vez las emisiones, los
   recargos y los intereses, y sirve igual para el demo público si se revive.
3. **Ningún comprobante pendiente.** Los 50 que devuelve la API están todos
   `aprobado`, así que el circuito 1 no tiene nada esperando. Dejar 2-3
   pendientes de aprobación.
4. ~~El mes en curso vacío.~~ **No es un defecto del dataset: es deliberado.**
   `meses_demo()` siembra los seis meses *completos anteriores* y deja el mes en
   curso abierto a propósito, para que el visitante tenga un período vivo donde
   cargar un gasto y cerrarlo — que es justamente el circuito 2. Hay un test que
   lo fija (`test_meses_demo_devuelve_los_6_meses_completos_anteriores`).

   Lo que sí falla es **cómo lo presenta la interfaz**: Inicio muestra el hero en
   `$0` con "0% cobrado" en vez de invitar a cargar el primer gasto del mes, y
   Gastos y Liquidaciones muestran un vacío seco. Eso es trabajo de interfaz, no
   de datos, y va al Plan B junto con el resto de los arreglos de pantalla.
5. **La caja en −$13.263.900.** El estado financiero muestra el consorcio con
   trece millones en rojo, que es imposible en un consorcio real. Cargar los
   ingresos que faltan o un saldo inicial.
6. **Comprobantes con imágenes de un píxel.** En la demo se ven. Incluir dos o
   tres capturas de transferencia genéricas.
7. **El "propietario al día" no está al día.** UF-01A, que los perfiles pinnean
   como pagador puntual y es el destino del botón "Propietario al día", tiene
   $242.357 de saldo, **un recargo por mora de $38.260 y $6.209 de intereses
   punitorios**. El selector promete una cosa y la pantalla muestra otra, en rojo.
   Verificado sobre los datos, no inferido.

### 3.3 Las fechas se corren al abrir la demo

El dataset se congela una vez, con fechas absolutas. Sin más, **la demo
envejece**: hoy el último vencimiento es reciente y el mes en curso está abierto
para cerrarlo, pero dentro de dos meses el sistema calculará el período actual
con el reloj del visitante, no encontrará expensas de ese mes, y volverá a
mostrar el hero en `$0` — el mismo síntoma que §3.2.4 explica. Además:

- las reservas de amenities (hoy futuras) pasan a ser pasadas;
- el "propietario al día" se lee como atrasado, porque su última boleta quedó
  con fecha vieja;
- la lista de morosos muestra antigüedades cada vez mayores.

No se rompe nada; se ve viejo, que para una demo de ventas es equivalente.

**Decisión: al arrancar, la demo desplaza todas las fechas del dataset** por la
diferencia entre la fecha en que se generó y el día de la visita, de modo que el
último período cerrado sea siempre el mes anterior y el vencimiento caiga siempre
a pocos días. El dataset guarda su fecha de generación para poder calcular ese
desplazamiento.

Se elige esto sobre la alternativa —regenerar el dataset cada tanto— porque
regenerar es mantenimiento que alguien tiene que acordarse de hacer, y cuando se
olvida la demo envejece en silencio. El desplazamiento se implementa una vez y no
requiere mantenimiento nunca más.

**Lo que cuesta, dicho de frente:** desplazar fechas tiene bordes. Los meses
tienen distinta cantidad de días, así que el desplazamiento se hace en meses
enteros para los períodos y en días para las fechas sueltas, no sumando una
cantidad fija de días a todo. Hay que decidir qué pasa con los intereses y
recargos ya calculados: la decisión es **no recalcularlos** —viajan tal cual,
como el resto de los importes (§5.2)—, porque recalcularlos exigiría portar esas
reglas al navegador, que §5.2 descarta explícitamente. La consecuencia aceptada
es que los intereses del dataset corresponden a la mora que existía al generarlo,
no a la que resultaría de las fechas desplazadas; en pantalla es indistinguible,
porque lo que se muestra es un importe, no una cuenta.

### 3.4 PDF

El generador produce además los PDF reales del último período, uno por unidad, y
quedan como archivos estáticos. Cuando el propietario toca "ver PDF" se abre el
suyo: el que generó el sistema, con su unidad y sus importes.

**Se sirven sueltos, fuera del paquete de la aplicación.** Dieciocho boletas
pesan más que toda la app junta; así se descarga sólo la que se abre y la
primera carga sigue liviana.

## 4. El sustituto del servidor

### 4.1 Punto de intercepción

`frontend/src/api/client.js` expone `apiFetch(path, {method, body, ...})`, por
donde pasan **las 142 llamadas del frontend** (32 recursos raíz). Es un único
punto de entrada y ya existe.

`apiFetch` consulta al arrancar si está en modo demo. Si lo está, en vez de
`fetch` le pasa el pedido al sustituto. **Ninguna pantalla se modifica.**

### 4.2 Forma del módulo

Recibe método, ruta y cuerpo; devuelve `{ok, status, data}` — la misma forma que
hoy devuelve `apiFetch`. Adentro:

- un **enrutador** que reconoce las rutas, incluidas las que llevan un
  identificador en el medio (`/gastos/:id`);
- un **estado en memoria**, copiado del archivo inicial en cada arranque.

Respeta los códigos del contrato (`200`/`201`/`204`/`400`/`403`/`404`/`409`), de
modo que las pantallas —que ya saben interpretarlos— muestren los mismos
mensajes que contra el servidor real.

**Es una función sobre un estado**: se le da un estado y un pedido, se comprueba
la respuesta. Eso permite cubrir el recorrido con pruebas automáticas sin
navegador, que es la defensa principal contra la desincronización.

**Dónde vive:** `frontend/src/demo/`, con el enrutador, los manejadores agrupados
por recurso, el estado inicial y las dos piezas de cálculo portadas (§5.1) en
archivos separados. Es la única carpeta nueva del proyecto y la única que
desaparece del bundle cuando la bandera está apagada.

**No simula demoras.** Las respuestas son inmediatas; la demo se siente más
rápida que el producto contra un servidor, lo que para vender juega a favor.

### 4.3 Lo que el sustituto no sabe hacer

Nunca lanza una excepción: siempre devuelve una respuesta que las pantallas ya
saben mostrar, así el visitante nunca ve una pantalla en blanco. Distingue dos
casos, porque tienen dos públicos distintos:

**Guardar en una sección de sólo lectura.** Es la situación normal para un
visitante, y lee el texto tal cual dentro del formulario. Explica en castellano
que es una demostración y lo invita a probar los circuitos que sí impactan. Sin
códigos, métodos ni rutas: un "501 no implementado" con un path adentro se lee
como un sistema roto.

**Una ruta de lectura que no está en el dataset.** Es un error de quien
programa, no del visitante: ahí sí el mensaje nombra la ruta, porque lo que
hace falta es poder arreglarlo. En desarrollo además va a la consola.

La red de contención real es la prueba de cobertura de rutas (§9), que hace
fallar la compilación antes de que eso llegue a producción.

## 5. Cálculo: qué está vivo y qué congelado

### 5.1 Se porta al navegador

Dos piezas, las más chicas y estables del sistema, y las que hacen que la demo
se sienta viva:

- **Reparto por coeficiente** (prorrateo): sumar los gastos del período por clase
  y repartirlos según el coeficiente de cada unidad.
- **Imputación de pagos por antigüedad** (FIFO): `backend/cuenta_corriente.py`,
  ~80 líneas, ya aislada como función pura y con pruebas propias.

**Verificación cruzada:** como el dataset lo genera el backend real, se puede
correr la imputación del navegador sobre los movimientos del dataset y comprobar
que llega a los mismos saldos que trae el archivo. Es una prueba que detecta al
instante si las dos implementaciones se separan.

También se calculan las **validaciones simples del cierre** —no hay gastos
cargados, una clase activa se quedó sin gastos, hay unidades con saldo vencido—
porque son consultas directas sobre el estado y son parte del momento en que el
sistema muestra criterio.

### 5.2 Se muestra tal como viene del dataset

Liquidaciones de sueldo, intereses punitorios con sus reglas finas, y las
validaciones más elaboradas del cierre. No se recalculan.

Desde el 2026-08-17 las liquidaciones **se ven** —con su empleado, sus haberes
y sus conceptos, seis meses de historia— pero siguen siendo un dato congelado:
la demo no calcula un sueldo nuevo. Es la diferencia entre mostrar el módulo y
reimplementarlo, y §10 mantiene lo segundo fuera de scope.

## 6. Lo que un navegador solo no puede hacer

| Qué | Cómo se resuelve |
|---|---|
| PDF de boleta | Archivos reales generados por el sistema (§3.4) |
| Envío de boletas por mail | El modal se abre y muestra a cuántas unidades se enviaría; al confirmar avisa que en la demo no sale ningún correo |
| Subir el comprobante de pago | **Funciona igual que en producción**: el navegador lee la imagen elegida y la muestra en el comprobante presentado |

## 7. Compilación y publicación

### 7.1 Dos compilaciones del mismo código

Ya existe `VITE_DEMO_MODE` en el proyecto; se reutiliza.

- **Bandera apagada:** la app habla con el servidor real. Es lo que se le instala
  a un cliente.
- **Bandera encendida:** se incluyen el sustituto y el archivo de datos.

**En la versión de los clientes el sustituto no existe.** La inclusión es
condicional: ni el módulo ni el dataset entran en el bundle de producción, así
que no engordan la aplicación del cliente ni pueden activarse por accidente.

### 7.2 Dos proyectos de Vercel, una sola rama

Dos proyectos apuntando al **mismo repositorio y la misma rama**, diferenciados
por sus variables de entorno. Cada push dispara dos compilaciones: la demo y
producción.

Razón: la demo queda sincronizada con producción sola, siempre. La alternativa
—una rama por proyecto— da control sobre cuándo se actualiza, a cambio de
mantener dos ramas y acordarse de pasar los cambios; en la práctica termina en
una demo que muestra un producto de hace meses.

**El riesgo que introduce compartir rama:** agregar una pantalla que consulte un
endpoint nuevo hace que producción ande y la demo se rompa, y se publica sola.
Dos defensas:

1. **Las pruebas del recorrido corren durante la compilación.** Concretamente: el
   comando de build del proyecto demo en Vercel pasa a ser `npm test && npm run
   build`, de modo que una prueba en rojo aborta el despliegue. Si el sustituto
   no sabe responder algo que las pantallas piden, no se publica. Una demo vieja
   online es mejor que una demo rota online.
2. **Respuesta controlada ante rutas desconocidas** (§4.3).

### 7.3 Advertencias operativas

- **No ponerle la bandera de demo al proyecto de producción.** Es el único error
  que convierte el producto en la demo de cara al cliente. Las variables son por
  proyecto; revisar al crear el segundo.
- **El plan gratuito de Vercel es para uso no comercial.** La demo cae cómoda
  ahí; el día que haya un cliente pagando sobre el proyecto de producción, ese
  proyecto debería pasar a un plan pago según sus términos.
- **Producción necesita un backend vivo para servir de algo**, y hoy no lo hay.
  Hasta el primer cliente conviene dejar ese dominio sin publicar o apuntando a
  la landing, y publicar sólo la demo.

### 7.4 Qué se apaga de lo actual

Se apagan el servicio web de Render, su Postgres y el cron de reset — que es lo
que cuesta plata y lo que se rompe.

**El generador se queda**: pasa a ser la pieza central del nuevo esquema. El modo
demo del backend queda en el repositorio sin tocar: no molesta y el día que haya
clientes y presupuesto, levantar el sandbox por visitante es volver a encenderlo.

## 8. Aviso al visitante

La banda superior hoy dice que los datos se reinician cada 6 horas. En el modelo
nuevo eso deja de ser cierto y **hay que cambiarlo**, por algo en la línea de:
"esta demo corre entera en tu navegador; nada de lo que hagas se guarda ni se
comparte", con un botón para reiniciarla en el acto.

Además de ser preciso, es argumento a favor: el visitante entiende que puede
tocar lo que quiera.

## 9. Pruebas

- **Recorrido completo del circuito 1 y del circuito 2** contra el sustituto, sin
  navegador: presentar pago → aprobar → verificar saldo y salida de la lista de
  morosos; cargar gasto → cerrar período → verificar el reparto en las 18
  expensas.
- **Verificación cruzada de la imputación** contra los saldos del dataset (§5.1).
- **Cobertura de rutas:** que toda ruta que las pantallas consultan al cargar
  esté implementada. Es la prueba que hace fallar la compilación cuando alguien
  agrega un endpoint nuevo. Desde que la demo muestra la aplicación entera
  (§2.2) la lista cubre todas las secciones, no sólo el circuito de venta.
- **El exportador corta si una ruta declarada devuelve un error.** Sin eso, una
  ruta mal escrita en las tablas del exportador no rompe nada visible: el
  backend contesta 404 o 405, el cuerpo del error se guarda en el dataset como
  si fueran datos, y la pantalla aparece vacía sin que nadie se entere. Pasó
  con dos rutas reales antes de existir esta verificación.
- Las pruebas corren en CI y durante la compilación de Vercel (§7.2).

## 10. Fuera de scope

- Cambios en el backend, en `openapi.yaml` o en el contrato.
- Sandbox por visitante con tenants efímeros (requiere infraestructura paga; es
  el camino cuando haya clientes).
- Las mini-demos jugables embebidas en la landing: son otra pieza, de marketing,
  y ahí sí corresponden datos fijos en el frontend.
- Reimplementar liquidaciones de personal, intereses punitorios o validaciones
  elaboradas de cierre.

## 11. Riesgos

| Riesgo | Mitigación |
|---|---|
| El sustituto se despega de la API real | Pruebas de cobertura de rutas + el dataset se regenera desde el backend real, así que un cambio de forma se nota al regenerarlo |
| Dos implementaciones del cálculo divergen | Verificación cruzada contra los saldos del dataset (§5.1); son las dos piezas más estables del sistema |
| Un cambio rompe la demo y se publica solo | Las pruebas corren en la compilación y la hacen fallar (§7.2) |
| El bundle de producción incluye el sustituto | Inclusión condicional por bandera; verificar en el build de producción que no aparece |
| La primera carga se vuelve pesada | Los PDF se sirven sueltos, fuera del paquete (§3.4) |

# Modo demo — dataset de 6 meses, selector de rol y deploy público

Fecha: 2026-07-30
Estado: **implementado y mergeado a master** (2026-07-31, 9 tasks, 927 tests).
Plan de implementación: `docs/superpowers/plans/2026-07-31-modo-demo.md`.
Demo en vivo: https://consorciosdemo.vercel.app/

> Las secciones de abajo son el diseño tal como se acordó, con correcciones
> marcadas donde la implementación reveló que una decisión no se sostenía. Ver
> especialmente "Reset automático", que cambió dos veces.

## Problema

El sistema necesita una versión demo pública, linkeable desde la web comercial, que
un administrador de consorcios pueda probar sin registrarse y sin que nadie le
cargue datos. Hoy no existe: lo más cercano son dos scripts de seed, y ninguno
sirve para eso.

**`backend/seed.py` (`seed_if_empty`, 545 líneas) es un fixture de smoke-test.**
Crea 1 consorcio con **2 departamentos**, catálogos completos (4 clases de
prorrateo, proveedores, cajas, 1 empleado, 6 haberes, 12 conceptos SUTERH,
2 amenities) y luego:

- gastos puntuales de **un solo período** (2026-06)
- **2 expensas de un solo período** (2026-05) + 4 movimientos de cuenta

Lo que no tiene, que es justamente lo que un administrador querría ver:

| Tabla | Registros |
|---|---|
| `PeriodoCerrado` | 0 — nunca se cerró un período |
| `LiquidacionEmpleado` | 0 — hay empleado, pero ninguna liquidación |
| `Comprobante` | 0 — ningún pago presentado |
| `Peticion` / `Trabajo` / `Presupuesto` | 0 — solo 2 plantillas recurrentes |
| `Reserva` | 0 — solo los amenities definidos |
| `Comunicado` | 0 |
| `Notificacion` | 0 |
| Transferencias / ajustes de caja | 0 |

El módulo estrella (cierre de período con desglose por rubro y clase) no tiene un
solo caso para mirar, y los reportes de morosos y estado financiero salen vacíos.
Además usa fechas absolutas (`date(2026, 7, 10)` en `seed.py:408`), así que
envejece: en tres meses muestra todo vencido.

**`backend/seed_e2e.py` (423 líneas) tiene la arquitectura correcta pero la escala
equivocada.** Puebla la app exclusivamente a través de la API con `TestClient`
in-process, así que pasa por todas las validaciones de negocio reales. Ya simula
6 meses de operación: gastos comunes y particulares → cierre de período →
comprobantes de los deptos → aprobación del admin, con perfiles de morosidad
(`seed_e2e.py:203`) y sobre-pagos del 5% (`:274`). Pero:

- `MESES` está hardcodeado a `["2026-01" … "2026-06"]` (`:35`) — misma bomba de
  tiempo que `seed.py`.
- Genera 2 consorcios de 60 y 120 deptos: es un test de carga, no un demo. El
  reset sería lento y el visitante se pierde.
- No genera **liquidaciones de empleado** ni **comunicados**: dos módulos quedan
  vacíos.
- No lo invoca nadie: es un script manual, no está conectado a ningún flujo.

## Alcance

**Incluye:** el flag `DEMO_MODE` y todo lo que cuelga de él (selector de rol,
emails a consola, banner), el generador `backend/seed_demo.py`, el reset
automático, el mirror al repo público, y el arreglo de los 12 tests podridos por
fecha.

**No incluye (va a un spec aparte, "hardening de producción"):**

- Uploads a S3 / almacenamiento persistente. **El demo no lo necesita**: el
  filesystem efímero del contenedor borra los comprobantes en cada restart, pero como
  el demo se resetea igual, es irrelevante — hasta deseable. Es un requisito
  exclusivo de producción.
- Migraciones (Alembic). El demo hace `drop_all` + `create_all` en cada reset, así
  que nunca migra nada.
- Backups y audit log (Fase 8 del roadmap).
- El default peligroso `SEED_ENABLED = True` en `backend/config.py:19`.
- Servir `/uploads` sin autenticación (`backend/main.py:210`).

## Decisiones tomadas

| Decisión | Elegido | Por qué |
|---|---|---|
| Relación del código demo con este repo | **Mismo repo + `DEMO_MODE`** | Un fork por copia se desincroniza en semanas: cada fix habría que portarlo a mano. Con un solo codebase, lo que se arregla acá está en el demo al siguiente deploy, y el hardening de producción beneficia al demo gratis. |
| Datos modificados por visitantes | **Instancia compartida + reset cada 6 h** | El visitante puede hacer de todo sin límites. Simple de operar: un script y un cron. Se acepta que dos visitantes simultáneos se pisen. |
| Perfil del consorcio | **Mediano realista, 18 UF** | Con 2 UF los reportes salen vacíos y parece un Excel. Con 40+ el visitante se pierde y el reset se vuelve lento. 18 UF luce prorrateo por coeficientes, morosos con intereses y obra en cuotas. |
| Hosting | **Render** (backend + Postgres) y **Vercel** (frontend) | El `Procfile` actual ya sirve, tienen cron nativo y Postgres administrado. Decidido como "Railway / Render" en el diseño; quedó en Render + Vercel. |
| Construcción del dataset | **Adaptar `seed_e2e.py`** | Ya tiene la arquitectura correcta. Un generador que escriba directo a la DB tendría que replicar a mano el cálculo de cierre, el FIFO de pagos y los intereses punitorios; cuando esa lógica cambie, el dataset queda silenciosamente inconsistente — el peor bug posible en un demo público. |
| Entrada del visitante | **Selector de rol (3 botones)** | Un click sin tipeo, y convierte el control de acceso por rol de invisible a lo primero que se prueba. Además, al emitir el token sin pasar por credenciales, que un visitante cambie la password del admin deja de romper el demo. |

## Arquitectura del modo demo

Flag `DEMO_MODE: bool = False` en `backend/config.py`. Mismo codebase, dos
servicios con distintas variables de entorno.

Comportamientos que cambia:

| Comportamiento | Razón |
|---|---|
| Banner permanente "Demo — los datos se reinician cada 6 h" | El visitante tiene que saber que puede romper todo sin culpa |
| Pantalla de entrada = selector de rol en lugar del login | Fricción cero |
| Emails forzados a modo consola | Nunca mandar mail real desde el demo, aunque haya SMTP configurado |
| Panel super-admin oculto | Con una sola administración no aporta nada y expone superficie innecesaria |

### El selector de rol

Router nuevo `backend/routers/demo.py` con `POST /auth/demo-login`. Recibe solo un
nombre de rol de una lista blanca fija, lo mapea a un usuario demo prefijado y
emite un JWT normal reusando el mismo código que el login real.

```
POST /auth/demo-login  {"rol": "administracion"}
                       {"rol": "propietario_al_dia"}
                       {"rol": "propietario_moroso"}
```

Un endpoint que emite tokens sin credenciales es, si `DEMO_MODE` se activa por
error en producción, un bypass total de autenticación. Tres candados en capas:

1. **La ruta no existe en producción.** En `backend/main.py`, el `include_router`
   va dentro de un `if get_settings().DEMO_MODE`. No es un 403 — el endpoint
   literalmente no está registrado, y un 404 no filtra información.
2. **La app no arranca mal configurada.** Validator en `Settings`: si
   `DEMO_MODE=true`, la `DATABASE_URL` debe contener la subcadena `demo`
   (ej. `sqlite:///./demo.db`, `postgresql://…/consorcio_demo`); si no, levanta
   excepción al bootear. Regla explícita y verificable, sin heurísticas. Un deploy
   que falla ruidoso es preferible a uno que sirve tokens de admin.
3. **Lista blanca cerrada.** El endpoint no acepta email ni id, solo uno de tres
   strings fijos. No hay forma de pedirle el token de otro usuario.

### Cómo se entera el frontend

Variable de build `VITE_DEMO_MODE=true` en el proyecto de Vercel del demo. El
frontend se compila igual desde el mismo repo; solo cambia el flag.

Para que frontend y backend no queden desincronizados (frontend con selector,
backend sin endpoint), el selector **degrada solo**: si `POST /auth/demo-login`
devuelve 404, cae al formulario de login normal. Es la misma respuesta que da
producción, donde la ruta no está registrada.

## El generador (`backend/seed_demo.py`)

Derivado de `seed_e2e.py`, conservando el wrapper `Api` sobre `TestClient`
in-process (no necesita servidor levantado) y el RNG con semilla fija.

**a) Escala.** Un consorcio, `pisos=3`. El padrón genera 6 unidades por piso
(letras A–F, `seed_e2e.py:121`), así que son **18 UF** exactas. De 180 deptos a
18: el reset pasa de minutos a segundos.

**b) Fechas relativas.** `MESES` se calcula desde la fecha de ejecución: los 6
meses calendario completos anteriores al mes en curso. Corriendo el 2026-07-30 da
`["2026-01" … "2026-06"]`; corriendo el 2026-11-02 da `["2026-05" … "2026-10"]`.
El mes en curso queda deliberadamente abierto (sin cerrar), para que el visitante
tenga un período vivo donde cargar gastos y probar el cierre él mismo.
`_fechas_del_periodo` y `_dia_del_periodo` (`:133`, `:144`) ya derivan del período,
así que se acomodan solas. Esto mata la bomba de tiempo.

**c) Perfiles de comportamiento deterministas.** `seed_e2e.py:204` mezcla los
deptos con `RNG.shuffle` antes de asignar perfiles. Para el demo eso no sirve: el
selector de rol apunta a emails fijos, así que **qué depto es moroso tiene que
estar pinneado, no sorteado**. Se asignan por posición: `UF-01A` siempre puntual,
`UF-03C` siempre moroso. El resto conserva la distribución 70/15/15 del código
actual, que sobre 18 UF da 12 puntuales, 3 irregulares y 3 morosos.

**d) Liquidaciones del encargado.** 6 liquidaciones mensuales, una por período.
Hoy el módulo Personal queda vacío pese a tener empleado, 6 haberes y 12 conceptos
SUTERH cargados. Cada liquidación genera además sus gastos del rubro
`sueldos_y_cargas_sociales`, así que el desglose de expensas gana realismo.

**e) Comunicados.** ~12 repartidos en los 6 meses (corte de agua, asamblea,
reglamento del SUM, aviso de expensas, etc.).

**f) Obra extraordinaria en cuotas.** Un plan de 6 cuotas sobre la clase B. Es lo
que justifica tener 4 clases de prorrateo: sin esto todo prorratea por clase A y
el sistema parece más simple de lo que es.

**g) Credenciales fijas.** `admin@demo.local`, `uf01a@demo.local` (al día) y
`uf03c@demo.local` (moroso), con password desde variable de entorno. Son los tres
destinos del selector de rol.

Lo que **no** se toca de `seed_e2e.py`: los perfiles 70/15/15, el sobre-pago del
5%, el padrón por CSV, los coeficientes que suman 100 exacto, las reservas de
amenities y el flujo peticiones → trabajos → presupuestos.

### Dataset objetivo

Consorcio "Edificio Libertador", 18 UF en 3 pisos, encargado propio:

- 6 períodos cerrados (M-6 a M-1 relativos a hoy), con desglose por rubro y clase
- 12 UF al día, 3 con atrasos salteados, 3 morosas con intereses acumulados
- ~40 gastos por período entre comunes (11 rubros) y particulares (1–3)
- 6 liquidaciones del encargado con sus gastos asociados
- 1 obra extraordinaria en 6 cuotas (clase B)
- SUM y Laundry con reservas y cobros a cuenta corriente
- ~12 comunicados
- Peticiones en los 4 estados, con presupuestos adjuntos

## Reset automático

> **Sección corregida el 2026-07-31 tras la implementación.** El diseño original
> proponía SQLite + cron + seed automático al bootear. Ninguna de esas tres cosas
> sobrevivió al contacto con la medición y con las restricciones reales del
> hosting. Lo que sigue es lo que efectivamente se construyó; el texto anterior
> quedó afirmando una arquitectura que contradecía al README.

Cron cada 6 h ejecutando `python -m backend.seed_demo --reset`, que hace
`_resetear_esquema` → `create_all` → puebla. Al correr in-process con
`TestClient`, no necesita que el servicio web esté arriba.

**Dos cosas cambiaron respecto del diseño original:**

**1. No hay seed-on-boot.** El runtime medido con 18 UF es **67 s** (66.6 s desde
base vacía, 68.1 s con `--reset`), por encima del umbral de 60 s que nos habíamos
puesto. Generar al arrancar haría fallar el healthcheck. El grueso del tiempo es
bcrypt hasheando contraseñas, y en un contenedor con menos CPU por core el margen
empeora. Como consecuencia, **la base arranca vacía y `/auth/demo-login` devuelve
503 hasta la primera corrida del cron** — hay que dispararlo a mano tras el primer
deploy.

**2. El demo usa Postgres, no SQLite con volumen.** Al descartar el seed-on-boot y
quedar solo el cron, apareció una restricción que el diseño no había anticipado:
los cron jobs corren en contenedores separados del servicio web, y los discos
persistentes se montan en un único servicio. Un cron externo no puede tocar el
archivo SQLite del web; y aunque pudiera, dos procesos haciendo drop/recreate
sobre SQLite mientras el web atiende tráfico es receta de bloqueos. Con Postgres
el cron se conecta por red: sin filesystem compartido y sin downtime.

Eso obligó a escribir una rama Postgres propia en `_resetear_esquema`:
`drop_all` tampoco sirve ahí, porque el modelo tiene un ciclo de FK
(`cajas → consorcios → presupuestos → trabajos`) que le impide ordenar las tablas.
Se usa `DROP SCHEMA public CASCADE`, que no depende del orden.

**Riesgo abierto que esto deja:** `DROP SCHEMA public CASCADE` exige que el rol de
conexión sea dueño del esquema `public`, cosa que en Render depende de la versión
de Postgres (en 15+ el dueño de la base puede; en 14 o anterior, no). Está
documentado con el chequeo concreto y la variante portable en la sección
"Deploy del demo" del `README.md`. **La rama Postgres nunca se ejecutó contra un
Postgres real** durante el desarrollo: está cubierta por un test que intercepta el
SQL emitido, no por una corrida.

## Infraestructura real (2026-07-31)

- **Frontend:** Vercel — https://consorciosdemo.vercel.app/
- **Backend + Postgres:** Render

El diseño original decía "Railway / Render"; quedó en Render para el backend y
Vercel para el frontend. Las restricciones que motivaron las decisiones de arriba
(cron en contenedor aparte, disco montado en un solo servicio) valen igual en los
dos proveedores.

## Repo público

GitHub Action que espeja a la cuenta pública en cada push a master.

**El mirror debe ser snapshot, no historial.** El historial de este repo tiene
`consorcio.db.corrupta` commiteado — una base SQLite con datos y hashes de
password (el `.gitignore` cubre `consorcio.db` y `*.db.bak`, pero no esa
extensión). Espejar el historial completo lo publicaría, y borrarlo después no
sirve: queda en los commits viejos.

El mirror empuja un único commit huérfano, force-pusheado en cada deploy. El repo
público muestra el estado actual del código y nada más. Para un repo de vitrina es
incluso preferible.

Aparte del mirror: sacar `consorcio.db.corrupta` del working tree y agregar
`*.corrupta` al `.gitignore`.

## Verificación

**El generador es el test end-to-end.** Usa `expect=` en cada llamada
(`seed_e2e.py:69`), así que si puebla 6 meses sin un status inesperado, el sistema
aguanta un semestre de operación real. Correrlo antes de cada deploy cubre
parcialmente el hueco de no tener CI.

**Arreglar los 12 tests podridos por fecha, en este mismo ciclo.** Son el mismo
bug que estamos matando en el seed: fechas absolutas donde van relativas. Hoy
fallan 12 de 893 (`test_amenities.py` ×8, `test_comprobantes.py` ×2,
`test_movimientos.py` ×2) porque reservan para `2026-07-15` (ya pasado → 400 por
anticipación mínima en vez de 409 por solape) y asumen que `2026-07-20` es futuro
(`test_movimientos.py:236` lo dice explícito: *"hoy es 2026-07-09"*). No son bugs
de producto — el código está bien. Pero si montamos CI con el suite en rojo, el CI
no sirve para nada.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| `DEMO_MODE=true` en producción → bypass de auth | Tres candados en capas (ruta ausente, validator de boot, lista blanca) |
| Seed-on-boot lento → healthcheck falla | ✅ Medido: 67 s → solo cron, sin seed-on-boot. Y al quedar solo el cron, el demo pasó de SQLite a Postgres (ver Reset automático) |
| Dos visitantes simultáneos se pisan | Aceptado explícitamente. El banner avisa que es un demo compartido |
| Mirror publica el historial con `consorcio.db.corrupta` | Snapshot huérfano force-pusheado, nunca historial |
| Un visitante deja el demo feo por hasta 6 h | Aceptado. Si molesta, bajar el intervalo del cron |

## Fuera de alcance

- Base aislada por visitante (se evaluó y se descartó por complejidad de infra).
- Bloquear escrituras destructivas en modo demo (se evaluó; el reset lo hace
  innecesario, y el selector de rol ya resuelve el único caso grave, que era
  vandalizar la password del admin).
- Multi-consorcio en el demo (se evaluó un segundo consorcio para lucir
  multi-tenancy; se descartó por costo de generación y riesgo de confundir al
  visitante).
- Todo el hardening de producción, enumerado arriba en Alcance.

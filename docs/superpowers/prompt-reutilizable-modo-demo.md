# Prompt reutilizable — construir un modo demo público

Copiá el bloque de abajo en una sesión nueva, en el proyecto donde quieras el demo.
Ajustá lo que está entre `<corchetes>`. Todo lo demás son decisiones ya validadas
en una implementación real; están redactadas como restricciones para que el
asistente no las re-litigue desde cero, pero **cada una dice por qué**, así que si
en tu proyecto una no aplica, va a poder discutirla con fundamento.

---

## El prompt

> Quiero construir una **versión demo pública** de este sistema, linkeable desde
> mi web comercial, donde un visitante pueda probar el producto de un click sin
> registrarse y sin que le carguen datos de prueba vacíos.
>
> Antes de escribir código quiero que hagamos brainstorming del diseño, después un
> spec, después un plan de implementación, y recién ahí implementar tarea por
> tarea con revisión entre cada una.
>
> **Contexto del proyecto:** `<stack, dónde está deployado hoy, si tiene tests y
> cuántos, si tiene multi-tenancy>`.
>
> ### Restricciones de arquitectura (no negociables, y por qué)
>
> 1. **El demo es un despliegue separado con su propia base de datos.** No una
>    ruta tipo `/demo` dentro de la app de producción, no un tenant especial, no
>    un subdirectorio. Un subdominio apuntando a otro servicio está bien. Razón: el
>    demo necesita un login sin credenciales, y eso solo es tolerable si el peor
>    caso es que vandalicen datos ficticios. En el mismo proceso que producción, un
>    flag mal puesto es un bypass de autenticación sobre datos de clientes reales.
>
> 2. **Mismo repositorio, activado por un flag de entorno.** Nada de forkear o
>    copiar carpetas a otro repo: se desincroniza en semanas y cada fix hay que
>    portarlo a mano. Un solo codebase, dos despliegues con distintas variables.
>
> 3. **El dataset se genera llamando a la propia API del sistema**, no escribiendo
>    directo a la base. Es más lento, pero: (a) los datos quedan consistentes por
>    construcción, porque los calcula el mismo código que corre en producción;
>    (b) el generador funciona como test end-to-end y encuentra bugs reales. En la
>    implementación de referencia encontró tres que ningún test cubría, incluido un
>    endpoint que descartaba silenciosamente la mitad de los campos que recibía.
>
> 4. **Todas las fechas del dataset son relativas al momento de generación**,
>    nunca absolutas. Un demo con fechas hardcodeadas muestra todo vencido a los
>    tres meses. Si el proyecto ya tiene tests con fechas absolutas, arreglalos
>    primero: son la misma bomba de tiempo y van a estorbar.
>
> ### Cómo entra el visitante
>
> Quiero un **selector de roles**: en lugar del formulario de login, dos o tres
> botones tipo "Probá como `<rol A>` / `<rol B>`". Un click, cero tipeo. Ventajas
> sobre las alternativas: comparado con mostrar credenciales para copiar, elimina
> fricción; comparado con un autologin ciego, muestra el control de acceso por rol
> como feature en vez de esconderlo, y deja que el visitante vea las dos caras del
> producto.
>
> Ese endpoint emite un token sin pedir credenciales, así que va con **tres
> candados en capas**:
>
> 1. **La ruta no se registra si el flag no está activo.** No un 403: el endpoint
>    literalmente no existe, y un 404 no filtra que exista.
> 2. **La app se niega a arrancar si está mal configurada.** Un validator que
>    exija, por ejemplo, que la URL de la base contenga la palabra `demo`. Prefiero
>    un deploy que falla ruidoso a uno que sirve tokens de admin en silencio.
> 3. **Lista blanca cerrada.** El endpoint acepta únicamente un nombre de rol de un
>    conjunto fijo, nunca un email ni un id. Y **valida que el usuario encontrado
>    tenga el rol esperado**, no solo que exista con ese email — si no, alguien que
>    logre mutar ese usuario escala privilegios sin credenciales.
>
> ### El dataset
>
> Quiero que simule **`<N>` meses de operación realista** de `<tipo de cliente>`,
> no un puñado de registros de ejemplo. Criterios:
>
> - **Ninguna pantalla del sistema puede quedar vacía.** Al terminar, recorré la
>   app y verificá una por una. Una pantalla vacía en un demo se lee como una
>   funcionalidad que no existe.
> - **Variedad de estados por diseño, no por azar.** Si una entidad tiene cuatro
>   estados posibles, el dataset tiene que alcanzarlos todos de forma
>   determinista. Con datos aleatorios es fácil que un estado nunca aparezca — o
>   peor, que el código directamente no pueda alcanzarlo y nadie lo note.
> - **Los usuarios del selector tienen que estar pinneados**, no salir de un
>   sorteo, y hay que verificar que puedan entrar de verdad de punta a punta
>   (no solo que existan: cosas como un flag de "cambiar contraseña obligatorio"
>   pueden dejar el botón roto).
> - **Los números tienen que ser creíbles para alguien del rubro.** Quien mira el
>   demo conoce los órdenes de magnitud. Si el ítem más caro aparece cuatro veces
>   más barato de lo normal, el sistema se lee como que no entiende el dominio.
> - **Nada de nombres de empresas reales con datos inventados.** Va a internet.
>   Organismos públicos genéricos está bien; marcas privadas, no.
>
> ### El reset
>
> Los visitantes van a crear, editar y borrar. Quiero una instancia compartida que
> **se regenere sola cada `<N>` horas**, con un cartel permanente avisándolo para
> que el visitante sepa que puede romper todo sin culpa.
>
> **Antes de elegir cómo se dispara el reset, medí cuánto tarda el generador.** Ese
> número decide la arquitectura, y es el tipo de cosa que no se puede estimar:
>
> - Si tarda poco, se puede regenerar al arrancar el servicio.
> - Si tarda más que el healthcheck del hosting, no: hay que ir a un cron, y ahí
>   aparece la pregunta de si el cron corre en el mismo contenedor que la app (en
>   la mayoría de los PaaS, no) y si puede compartir el almacenamiento (en la
>   mayoría, tampoco). Eso suele forzar una base gestionada por red en vez de un
>   archivo local.
>
> ### Otras cosas que el modo demo debe forzar
>
> - **Emails a consola, por código**, no por dejar la config de SMTP vacía. Un
>   demo público no puede mandar correo real ni por accidente.
> - **Ocultar cualquier panel administrativo** que no aporte a la demostración.
> - Si el frontend se compila aparte, que **degrade solo**: si el endpoint del
>   selector devuelve 404, que caiga al login normal. Así un frontend en modo demo
>   apuntando a un backend de producción no muestra botones muertos.
>
> ### Si además vas a publicar el código
>
> Si el repo va a espejarse a una cuenta pública: **espejá un snapshot, no el
> historial.** Un único commit huérfano force-pusheado. Razón: si alguna vez se
> commiteó una base de datos, un `.env` o un volcado, sigue estando en los commits
> viejos y borrarlo hoy no lo saca. Y antes de publicar, **barré los archivos
> trackeados** buscando bases, dumps, claves y backups — con criterio, no como
> trámite: una vez publicado no hay vuelta atrás.
>
> ### Cómo quiero que trabajemos
>
> Brainstorming primero, después spec, después plan, después implementación tarea
> por tarea. En cada tarea: escribir el test que falla, implementar lo mínimo,
> verificar, commitear. Y **revisión independiente después de cada tarea**, con
> dos veredictos separados: cumplimiento del spec y calidad del código.
>
> Tres cosas que quiero que hagas explícitamente durante todo el proceso:
>
> - **Si no podés verificar algo, decilo** en vez de afirmar que lo verificaste.
>   "No tengo Docker, esto quedó cubierto solo por test estático" es una respuesta
>   valiosa; inventar un resultado no.
> - **Ante cada test nuevo, preguntate si fallaría al borrar el código que
>   prueba.** Si no estás seguro, revertí el cambio y corré el test. En la
>   implementación de referencia aparecieron dos tests que pasaban con y sin el
>   arreglo.
> - **Si el plan resulta equivocado a mitad de camino, decilo y corregilo.** Es
>   esperable: las mediciones y las restricciones reales del hosting cambian
>   decisiones que en el papel parecían cerradas.

---

## Notas para vos, no para pegar

**Adaptá el número de roles al producto.** Acá fueron tres porque el sistema tiene
dos caras muy distintas (quien administra y quien recibe), y el tercero —el caso
problemático— resultó el más vendedor, porque muestra el dolor que el producto
resuelve. Si tu sistema tiene un solo tipo de usuario, un botón alcanza.

**Lo que más valor dio, en orden:**

1. Generar los datos por la API. Encontró tres bugs de producción que los tests no
   cubrían.
2. Medir el generador antes de decidir la arquitectura del reset. Cambió la
   decisión, y el número no era estimable.
3. La revisión independiente por tarea. Encontró una escalada de privilegios, un
   problema de integridad referencial y un rubro con valores irreales — ninguno de
   los cuales rompía ningún test.

**Lo que costó más de lo previsto:** el dataset realista. No la parte técnica, sino
acertarle a los órdenes de magnitud y a la variedad de estados. Presupuestá
iteraciones ahí.

**Referencia de esta implementación:**
- Spec: `docs/superpowers/specs/2026-07-30-modo-demo-design.md`
- Plan: `docs/superpowers/plans/2026-07-31-modo-demo.md`
- Deploy: sección "Deploy del demo" del `README.md`

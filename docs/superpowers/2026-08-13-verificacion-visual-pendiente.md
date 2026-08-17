# Verificación visual pendiente — rama `tablas-adaptativas`

Fecha: 2026-08-13

> **Cerrado el 2026-08-17.** La lista se ejecutó con browser. Encontró un
> defecto real: los siete anchos de columna fijos estaban derivados del ancho
> de carácter de la fuente normal, cuando las celdas van en negrita, así que
> pedían más espacio del que necesitaban y empujaban la columna de
> departamento fuera de la tabla en 1280 y 1440px. Corregido en
> `fix/ancho-columnas-ch-negrita`, ya integrado a `master`.
>
> Quedan tres puntos sin verificar, todos de bajo riesgo: la navegación entre
> meses en Gastos y las dos comprobaciones táctiles (campanita y cuentas
> corrientes), que necesitan un dispositivo real y no el emulador.

**Ningún agente tuvo browser disponible durante toda la implementación.** Los 41
commits de esta rama están verificados por tests (42), build, lint y lectura de
cascada CSS con aritmética escrita. Nada fue visto renderizado.

Eso no es una omisión: es la condición en la que se trabajó, y toda decisión de
ancho lleva su cuenta escrita en un comentario para que sea auditable. Pero
significa que **esta lista es la última línea de defensa**, y está ordenada por
riesgo real, no por prolijidad.

## Cómo medir el desborde

En la consola del browser, en cada pantalla y ancho:

```js
document.documentElement.scrollWidth === document.documentElement.clientWidth
```

`true` = no hay scroll horizontal. Es el invariante duro de toda la rama.

---

## Prioridad 1 — pantallas que NO se convirtieron

Estas trece tablas nunca se migraron. La rama les borró sin querer la contención
de scroll horizontal y después se la restauró (`index.css`, regla
`table:not(.tabla-datos)`). **Lo que hay que confirmar es que volvieron a estar
como estaban antes de la rama**, no que estén bien.

| # | Pantalla | Ancho | Qué mirar |
|---|---|---|---|
| 1 | `/padron` (pestaña Departamentos) | **375px** | El caso más apretado de todos: `.col-unidad` reserva 128px fijos de un contenedor de 343px. Medir el desborde. Si pasa, probar 320px. |
| 2 | `/liquidaciones`, con una liquidación abierta | **375px** | Dos tablas, la mayor cantidad de columnas de la app, y `.liquidacion-tabla` no tiene CSS propio. |
| 3 | `/trabajos` y `/trabajos-recurrentes` | **375px** | Seis columnas flexibles cada una. |
| 4 | `/mi-cuenta` y `/departamentos/:id/cuenta` | **375px** | Las dos pantallas que ve un inquilino, no un administrador. |
| 5 | Los cuatro `/reportes/*` | **375px** | Van dentro de una `Tarjeta`, que suma 28,8px de margen interno al apretón. |
| 6 | `/configuracion` (matriz de coeficientes) | 375 y 1440px | Es la única tabla que legítimamente necesita scroll horizontal. Confirmar que **sigue teniéndolo** y que no desborda la página. |

## Prioridad 2 — anchos donde la aritmética predice un problema

| # | Pantalla | Ancho | Qué mirar |
|---|---|---|---|
| 7 | `/gastos` | **1440px** | Leer la columna Rubro. "Mantenimiento partes comunes" era el peor caso; se le dio ancho propio y se bajó a prioridad 3. Confirmar que ya no se corta. |
| 8 | `/cobranzas` (Expensas) | **1280px** | La columna Departamento queda en ~85px útiles. Entra pero apretada — ver *Limitación conocida* abajo. |
| 9 | Cualquier tabla migrada | **exactamente 768px** | El contenedor da exactamente 720px y el escalón está en 720 inclusive. Confirmar que se ven las columnas de prioridad 2. **Margen: cero.** Si aparece una barra de scroll del sistema, puede caer al escalón mínimo. |
| 10 | Cualquier tabla migrada | 1024px | Contenedor 746px. Confirmar prioridad 2 visible, prioridad 3 en el desplegable. |

## Prioridad 3 — detalles visuales

| # | Dónde | Ancho | Qué mirar |
|---|---|---|---|
| 11 | Cualquier tabla migrada, scrolleando | 1440px | El encabezado queda fijo arriba y **con su línea inferior**. Se usó una sombra porque un borde común no sobrevive al encabezado pegajoso. |
| 12 | `/padron`, scrolleando | 1440px | Su encabezado **no** debe quedar pegajoso (es una tabla legacy). |
| 13 | Campanita, con no leídas | 375 y 1440px | El punto rojo sin número; el panel sube como hoja desde abajo en celular y es desplegable desde 600px. Probar el cruce exacto en 600px. |
| 14 | `/tesoreria` (Cajas), menú ⋯ de la **última** fila | 1440px | Que el desplegable no quede recortado por el borde de la celda. Es el argumento de cascada más intrincado de la rama. |
| 15 | `/cuentas-corrientes` | 375px | Tocar el código de unidad **con el dedo**, no con el mouse. |
| 16 | `/gastos` | 375 y 1440px | Navegar de "mayo" a "septiembre" con las flechas: el mes entero visible siempre. En celular el campo puede variar un poco de ancho entre meses (aceptado). |

---

## Limitaciones conocidas, ya decididas

- **Expensas a ~1280px:** la columna Departamento queda en ~85px útiles. El
  arreglo correcto es partir las columnas de vencimiento en dos (fecha y monto
  por separado); se descartó por ser más cambio del que esta rama debía
  absorber. Documentado en `frontend/src/utils/anchosColumnas.js`.
- **Escalón de 720px sin margen:** un viewport de 768px da un contenedor de
  exactamente 720px. Si alguna vez cambia el ancho del sidebar, el margen
  interno de `.app-content`, o aparece un canaletón de scrollbar, este número
  hay que **re-derivarlo, no ajustarlo a ojo**. La cuenta completa está en el
  docblock de `prioridadVisible` en `TablaResponsive.jsx`.
- **Gastos en celular:** el campo de mes puede cambiar de ancho entre meses
  cortos y largos. Se aceptó a cambio de no desbordar a 375px.
- **Targets táctiles de 36px** en los botones de las tarjetas, contra los 44px
  que pide `.claude/rules/frontend.md`. Es preexistente y sistémico en toda la
  app; cambiarlo a ciegas tenía más radio de impacto que el defecto.
- **13 tablas sin convertir.** La regla `table:not(.tabla-datos)` existe sólo
  para sostenerlas en su comportamiento previo. **Borrarla cuando se conviertan.**

## Ajeno a esta rama

`pytest` da 996 pasando y **1 fallando**: `test_amenities.py` tiene la fecha
`2026-08-11` escrita a mano y el reloj ya la pasó. El backend no se tocó en
ninguna de las 13 tareas. Es un test que se rompe solo con el paso del tiempo.

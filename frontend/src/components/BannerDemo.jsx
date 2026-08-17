/**
 * El módulo de la demo se importa DENTRO del handler, no arriba.
 *
 * Importarlo estáticamente arrastra el dataset (426 KB) al paquete principal y
 * anula la separación que hace que la demo no llegue al cliente: el build lo
 * avisa con `INEFFECTIVE_DYNAMIC_IMPORT`, y se comprobó que el dataset
 * terminaba dentro del bundle de producción.
 */

/**
 * Aviso permanente de que esto es una demo.
 *
 * El texto anterior prometía un reinicio cada 6 horas: era cierto cuando la
 * demo corría contra un servidor con un cron que la regeneraba. Ahora corre
 * entera en el navegador de quien mira, así que eso es falso — y decir la
 * verdad además juega a favor: el visitante entiende que puede tocar lo que
 * quiera porque nada de lo que haga sale de su máquina.
 */
export default function BannerDemo() {
  async function reiniciar() {
    // La condición no es defensiva: es lo que le permite al empaquetador
    // descartar esta rama en el build de producción y no emitir el módulo de
    // la demo ni su dataset. Sin ella los archivos se generan igual, aunque
    // nadie los descargue.
    if (import.meta.env.VITE_DEMO_MODE !== "true") return;
    const { reiniciarDemo } = await import("../demo/index.js");
    reiniciarDemo();
    // El estado vuelve al arranque, pero las pantallas ya montadas siguen
    // mostrando lo que leyeron antes: recargar es la forma más simple y
    // predecible de que todo quede como recién entrado.
    window.location.reload();
  }

  return (
    <aside className="banner-demo" role="status">
      <span>
        Esta demo corre entera <strong>en tu navegador</strong>. Nada de lo que hagas
        se guarda ni se comparte.
      </span>
      <button type="button" onClick={reiniciar}>
        Reiniciar demo
      </button>
    </aside>
  );
}

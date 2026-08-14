import { useEffect, useRef, useState } from "react";

/**
 * Menú "⋯" para la columna de acciones de una tabla. En una fila, tres botones
 * visibles se comen 200-250px de ancho — una columna de datos entera — y dejan
 * Eliminar a un click de Editar.
 *
 * Cada elemento de `acciones` es `{ label, onSelect, peligro?, disabled? }`.
 * `disabled` es la forma correcta de expresar "esta acción existe pero no se
 * puede ejecutar ahora" (p. ej. una operación en curso). NO es lo mismo que
 * omitir la acción del array: omitirla dice "esta acción no existe acá",
 * `disabled: true` dice "existe, todavía no". El `<button disabled>` nativo
 * ya se encarga de que ni el click ni el teclado disparen `onSelect` ni
 * cierren el menú — no hace falta lógica extra acá.
 *
 * Si `acciones` llega vacío no se renderiza ni el trigger `⋯`: un menú sin
 * ítems no tiene nada que ofrecer y confundiría más que su ausencia. Hoy
 * ningún llamador produce ese caso (todas las filas de las tres pantallas
 * que usan este componente conservan al menos una acción incondicional),
 * pero el guard vive acá para que la invariante sea estructural y no
 * dependa de que cada pantalla nueva la respete por las suyas.
 *
 * Borde de foco no alcanzado hoy: si TODAS las acciones llegaran deshabilitadas,
 * cada `<button disabled>` queda fuera del orden de tabulación, así que un
 * usuario de teclado que tabea desde el trigger saltaría directo afuera del
 * menú — y `alPerderFoco` (abajo) lo cerraría en el acto, antes de que hubiera
 * chance de ver ningún ítem. No es alcanzable con los `acciones` actuales de
 * ninguna pantalla (siempre queda al menos un ítem sin `disabled`), pero
 * queda anotado acá al lado de la feature que podría volverlo alcanzable.
 *
 * El estilo ya vive en index.css como `.menu-kebab*`.
 */
export default function MenuAcciones({ acciones, etiqueta = "Acciones" }) {
  const [abierto, setAbierto] = useState(false);
  const contenedorRef = useRef(null);
  const triggerRef = useRef(null);

  useEffect(() => {
    if (!abierto) return undefined;

    function alClickearAfuera(e) {
      if (!contenedorRef.current?.contains(e.target)) setAbierto(false);
    }
    function alApretarEscape(e) {
      if (e.key !== "Escape") return;
      setAbierto(false);
      // Sin esto el foco queda huérfano en el body y el teclado pierde el hilo.
      triggerRef.current?.focus();
    }

    document.addEventListener("mousedown", alClickearAfuera);
    document.addEventListener("keydown", alApretarEscape);
    return () => {
      document.removeEventListener("mousedown", alClickearAfuera);
      document.removeEventListener("keydown", alApretarEscape);
    };
  }, [abierto]);

  // Los hooks ya corrieron arriba, incondicionalmente — este early return
  // no los afecta. Sin ninguna acción disponible, ni el trigger tiene sentido.
  if (!acciones.length) return null;

  function ejecutar(accion) {
    setAbierto(false);
    accion.onSelect();
  }

  function alPerderFoco(e) {
    const siguienteFoco = e.relatedTarget;
    // `relatedTarget` es null cuando el foco sale del documento entero (p.ej.
    // a la barra del navegador): el usuario no se movió dentro de la página,
    // así que no corresponde cerrar el menú.
    if (siguienteFoco === null) return;
    // El foco se movió DENTRO del propio menú (trigger -> item, item -> item):
    // eso es justamente cómo se usa el menú con teclado, no una salida.
    if (contenedorRef.current?.contains(siguienteFoco)) return;
    setAbierto(false);
  }

  return (
    <div className="menu-kebab" ref={contenedorRef} onBlur={alPerderFoco}>
      <button
        type="button"
        ref={triggerRef}
        className="menu-kebab-trigger"
        aria-label={etiqueta}
        aria-haspopup="menu"
        aria-expanded={abierto}
        onClick={() => setAbierto((prev) => !prev)}
      >
        ⋯
      </button>

      {abierto && (
        <ul className="menu-kebab-lista" role="menu">
          {acciones.map((a) => (
            <li key={a.label} role="none">
              <button
                type="button"
                role="menuitem"
                className={`menu-kebab-item${a.peligro ? " peligro" : ""}`}
                disabled={a.disabled}
                onClick={() => ejecutar(a)}
              >
                {a.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

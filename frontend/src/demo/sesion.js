/** Clave con la que la app persiste el usuario (ver `auth/AuthContext.jsx`). */
const CLAVE_USUARIO = "consorcio_user";

/**
 * Con qué sesión arranca el sustituto.
 *
 * El backend real deduce quién pide de cada token; acá hay una sola sesión en
 * memoria, y el módulo se reinicia en cada recarga de página. Como la app sí
 * persiste el usuario para sobrevivir al refresh, el sustituto lee de ahí: sin
 * esto, quien recarga sigue viendo la aplicación como usuario logueado pero su
 * cuenta corriente aparece vacía, porque el sustituto ya no sabe quién es.
 *
 * Tolera que no haya nada guardado, que lo guardado no sea legible, o que no
 * haya almacenamiento: en cualquiera de esos casos arranca sin sesión, que es
 * lo mismo que pasaba antes de entrar.
 */
export function sesionInicial(storage) {
  try {
    const crudo = storage?.getItem(CLAVE_USUARIO);
    if (!crudo) return { departamento_id: null };
    return { departamento_id: JSON.parse(crudo).departamento_id ?? null };
  } catch {
    return { departamento_id: null };
  }
}

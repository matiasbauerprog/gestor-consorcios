import { useEffect, useState } from "react";

import { urlDeArchivo } from "../api/archivos";

/**
 * Enlace a un adjunto, que resuelve la URL firmada al montarse.
 *
 * Sin `children` muestra la miniatura de la imagen; con `children` los usa
 * como contenido del enlace (por ejemplo un "Ver" para un PDF).
 *
 * Mientras resuelve muestra un marcador de posición en vez de un `img` sin
 * `src`: un src vacío dispara un pedido al documento actual y ensucia la
 * consola. El marcador ocupa el mismo alto que la miniatura para que la fila
 * no salte cuando la imagen aparece.
 */
export default function ArchivoAdjunto({
  ruta,
  alt,
  className = "comprobante-thumb",
  children,
}) {
  const [url, setUrl] = useState(null);
  const [fallo, setFallo] = useState(false);

  useEffect(() => {
    let vigente = true;
    setUrl(null);
    setFallo(false);

    urlDeArchivo(ruta).then((u) => {
      // La respuesta puede llegar después de que el componente se desmontó
      // (una fila que se va de pantalla al filtrar): sin esta guarda, React
      // avisa por un setState sobre algo que ya no existe.
      if (!vigente) return;
      if (u) setUrl(u);
      else setFallo(true);
    });

    return () => {
      vigente = false;
    };
  }, [ruta]);

  if (fallo) return <span className="adjunto-estado adjunto-error">No disponible</span>;
  if (!url) {
    return (
      <span className="adjunto-estado adjunto-cargando" aria-busy="true" aria-label="Cargando adjunto">
        …
      </span>
    );
  }

  return (
    <a href={url} target="_blank" rel="noopener noreferrer">
      {children ?? <img src={url} alt={alt} className={className} />}
    </a>
  );
}

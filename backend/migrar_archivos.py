"""Sube al almacén externo los archivos que hoy viven en el disco local.

Se corre una sola vez, al mover un entorno de `STORAGE_BACKEND=local` a `s3`.
Es idempotente en el sentido que importa: subir dos veces el mismo objeto lo
sobrescribe con contenido idéntico.

La clave con la que se sube es la **ruta relativa al directorio de subidas**,
que es exactamente lo que quedó guardado en `archivo_path` de cada fila. Por eso
la base no necesita ningún cambio: las filas siguen resolviendo.

Uso:
    STORAGE_BACKEND=s3 S3_BUCKET=... python -m backend.migrar_archivos
"""
import io
import sys
from pathlib import Path

from .config import get_settings


def migrar(directorio: Path) -> dict:
    """Sube todos los archivos bajo `directorio`, usando su ruta relativa como
    clave. Devuelve `{"subidos": int, "fallados": list[str]}`."""
    from . import storage_s3

    subidos = 0
    fallados: list[str] = []

    for ruta in sorted(directorio.rglob("*")):
        if not ruta.is_file():
            continue
        clave = ruta.relative_to(directorio).as_posix()
        try:
            storage_s3._cliente().put_object(
                Bucket=storage_s3._bucket(),
                Key=clave,
                Body=io.BytesIO(ruta.read_bytes()),
            )
            subidos += 1
            print(f"[migrar] {clave}")
        except Exception as e:  # noqa: BLE001 — se reporta y se sigue con el resto
            fallados.append(f"{clave}: {e}")

    return {"subidos": subidos, "fallados": fallados}


def main() -> int:
    settings = get_settings()
    if settings.STORAGE_BACKEND != "s3":
        print(
            "STORAGE_BACKEND debe ser 's3' para migrar: este script sube al "
            "almacen externo lo que hay en disco.",
            file=sys.stderr,
        )
        return 1

    directorio = Path(settings.UPLOAD_DIR)
    if not directorio.is_dir():
        print(f"No existe {directorio}: nada que migrar.")
        return 0

    resultado = migrar(directorio)
    print(f"\n[migrar] subidos: {resultado['subidos']}")
    for f in resultado["fallados"]:
        print(f"[migrar] FALLO {f}", file=sys.stderr)
    return 1 if resultado["fallados"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

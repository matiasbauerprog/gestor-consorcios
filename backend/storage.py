"""Almacenamiento de archivos subidos.

Una sola interfaz con dos implementaciones detrás:

- **local** — escribe en `UPLOAD_DIR`. Es el default, es lo que corre en los
  tests y en CI, y no toca la red.
- **s3** — cualquier almacén S3-compatible (Supabase Storage, Cloudflare R2,
  AWS S3). Ver `backend/storage_s3.py`.

Ningún router sabe cuál está activo: piden `guardar_archivo` y `abrir_archivo`
y listo.

La validación de tipo y de tamaño vive acá y sólo acá. Antes estaba duplicada
entre este módulo y `routers/presupuestos.py`, con dos criterios distintos
(content_type contra extensión del filename) y dos límites que podían
desincronizarse.
"""
import hashlib
import hmac
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from .config import get_settings

# content_type -> extensión con la que se persiste. La extensión del filename
# que manda el cliente no se usa nunca: es atacante-controlada.
EXTENSIONES_PERMITIDAS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}

_TIPOS_POR_EXTENSION = {v: k for k, v in EXTENSIONES_PERMITIDAS.items()}

_TAMANO_CHUNK = 64 * 1024


def _directorio_base() -> Path:
    """Raíz del almacenamiento local. Función y no constante para que los
    tests la puedan sustituir por un tmp_path."""
    return Path(get_settings().UPLOAD_DIR)


def _max_bytes() -> int:
    return get_settings().MAX_UPLOAD_SIZE_BYTES


def _extension_valida(archivo: UploadFile) -> str:
    ext = EXTENSIONES_PERMITIDAS.get(archivo.content_type or "")
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser una imagen JPG/PNG/WebP o un PDF.",
        )
    return ext


def guardar_archivo(archivo: UploadFile, carpeta: str) -> str:
    """Persiste `archivo` bajo `carpeta` y devuelve la clave relativa.

    La clave (p. ej. `comprobantes/9f3a....jpg`) es lo que se guarda en la
    base; nunca una ruta absoluta ni una URL, para que mover el almacén no
    obligue a reescribir filas.

    Eleva `HTTPException` 400 si el tipo no está permitido y 413 si supera el
    tamaño máximo.
    """
    ext = _extension_valida(archivo)
    nombre = f"{uuid.uuid4().hex}{ext}"
    clave = f"{carpeta}/{nombre}"

    if get_settings().STORAGE_BACKEND == "s3":
        from . import storage_s3

        storage_s3.subir(archivo, clave, _max_bytes())
        return clave

    destino = _directorio_base() / carpeta
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / nombre

    leidos = 0
    try:
        with ruta.open("wb") as out:
            while True:
                chunk = archivo.file.read(_TAMANO_CHUNK)
                if not chunk:
                    break
                leidos += len(chunk)
                if leidos > _max_bytes():
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=(
                            "El archivo supera el máximo permitido "
                            f"({_max_bytes() // (1024 * 1024)} MB)."
                        ),
                    )
                out.write(chunk)
    except Exception:
        # Un parcial en disco es peor que nada: ocupa lugar y ninguna fila lo
        # referencia, así que nadie lo va a limpiar nunca.
        ruta.unlink(missing_ok=True)
        raise

    return clave


def _ruta_local(clave: str) -> Path:
    """Resuelve la clave dentro del directorio base, rechazando cualquier
    intento de salirse (`..`, rutas absolutas)."""
    base = _directorio_base().resolve()
    ruta = (base / clave).resolve()
    if not ruta.is_relative_to(base):
        raise FileNotFoundError(clave)
    return ruta


def abrir_archivo(clave: str) -> tuple[Iterator[bytes], str]:
    """Devuelve `(chunks, content_type)` para servir el archivo.

    Eleva `FileNotFoundError` si no existe o si la clave intenta salirse del
    directorio base.
    """
    if get_settings().STORAGE_BACKEND == "s3":
        from . import storage_s3

        return storage_s3.abrir(clave)

    ruta = _ruta_local(clave)
    if not ruta.is_file():
        raise FileNotFoundError(clave)

    content_type = _TIPOS_POR_EXTENSION.get(
        ruta.suffix.lower(), "application/octet-stream"
    )

    def _chunks() -> Iterator[bytes]:
        with ruta.open("rb") as f:
            while True:
                chunk = f.read(_TAMANO_CHUNK)
                if not chunk:
                    break
                yield chunk

    return _chunks(), content_type


def firmar_clave(clave: str, segundos: int | None = None) -> str:
    """Devuelve una ruta de descarga con firma y vencimiento.

    Se firma `clave:exp` juntos: firmar sólo la clave permitiría estirar el
    vencimiento, y firmar sólo el exp permitiría reusar la firma para otro
    archivo.
    """
    settings = get_settings()
    if segundos is None:
        segundos = settings.URL_FIRMADA_SEGUNDOS
    exp = int(time.time()) + segundos
    firma = hmac.new(
        settings.SECRET_KEY.encode(),
        f"{clave}:{exp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"/archivos/{clave}?exp={exp}&firma={firma}"


def verificar_firma(clave: str, exp: str, firma: str) -> bool:
    """True si la firma corresponde a esa clave y todavía no venció."""
    try:
        vencimiento = int(exp)
    except (TypeError, ValueError):
        return False
    if vencimiento < time.time():
        return False

    esperada = hmac.new(
        get_settings().SECRET_KEY.encode(),
        f"{clave}:{vencimiento}".encode(),
        hashlib.sha256,
    ).hexdigest()
    # compare_digest y no ==: la comparación normal corta en el primer byte
    # distinto y filtra la firma correcta byte a byte por tiempo de respuesta.
    return hmac.compare_digest(esperada, firma or "")

"""Almacenamiento en un servicio S3-compatible.

Sirve igual para Supabase Storage, Cloudflare R2 y AWS S3: los tres hablan el
mismo protocolo. Lo único que cambia es `S3_ENDPOINT_URL`.

Este módulo no tiene lógica de negocio: valida tamaño y mueve bytes. La
validación de tipo, la generación de la clave y la firma viven en
`backend/storage.py`, que es la interfaz que ven los routers.

**El bucket tiene que ser privado.** Si queda público, la firma no protege
nada: el objeto es accesible por su URL directa.
"""
import io
from collections.abc import Iterator
from functools import lru_cache

from fastapi import HTTPException, UploadFile, status

from .config import get_settings

_TAMANO_CHUNK = 64 * 1024


@lru_cache(maxsize=1)
def _cliente():
    """Cliente boto3, cacheado: crearlo en cada request agrega latencia por la
    resolución de credenciales."""
    import boto3

    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.S3_ENDPOINT_URL or None,
        region_name=s.S3_REGION,
        aws_access_key_id=s.S3_ACCESS_KEY_ID,
        aws_secret_access_key=s.S3_SECRET_ACCESS_KEY,
    )


def _bucket() -> str:
    return get_settings().S3_BUCKET


def subir(archivo: UploadFile, clave: str, max_bytes: int) -> None:
    """Sube el archivo bajo `clave`.

    Se lee entero en memoria antes de subir para poder cortar por tamaño sin
    dejar un objeto parcial arriba. Con el límite en 5 MB es aceptable; si
    algún día sube, hay que pasar a subida multiparte con corte por chunk.
    """
    contenido = archivo.file.read(max_bytes + 1)
    if len(contenido) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                "El archivo supera el máximo permitido "
                f"({max_bytes // (1024 * 1024)} MB)."
            ),
        )

    _cliente().put_object(
        Bucket=_bucket(),
        Key=clave,
        Body=io.BytesIO(contenido),
        ContentType=archivo.content_type or "application/octet-stream",
    )


def abrir(clave: str) -> tuple[Iterator[bytes], str]:
    """Devuelve `(chunks, content_type)`. Eleva `FileNotFoundError` si no está."""
    from botocore.exceptions import ClientError

    try:
        respuesta = _cliente().get_object(Bucket=_bucket(), Key=clave)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404", "NotFound"):
            raise FileNotFoundError(clave) from e
        raise

    cuerpo = respuesta["Body"]
    content_type = respuesta.get("ContentType", "application/octet-stream")
    return cuerpo.iter_chunks(chunk_size=_TAMANO_CHUNK), content_type

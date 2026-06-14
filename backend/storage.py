import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from .config import get_settings


_ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def guardar_imagen_comprobante(archivo: UploadFile) -> str:
    """Persiste una imagen de comprobante en `UPLOAD_DIR/comprobantes/`.

    Devuelve el path relativo al `UPLOAD_DIR` (p. ej. `comprobantes/abc123.jpg`).

    Eleva `HTTPException`:
      - 400 si el `content_type` no es una imagen soportada.
      - 413 si el archivo supera `MAX_UPLOAD_SIZE_BYTES`.
    """
    ext = _ALLOWED_IMAGE_TYPES.get(archivo.content_type or "")
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser una imagen JPG, PNG o WebP.",
        )

    settings = get_settings()
    max_bytes = settings.MAX_UPLOAD_SIZE_BYTES
    upload_dir = Path(settings.UPLOAD_DIR) / "comprobantes"
    upload_dir.mkdir(parents=True, exist_ok=True)

    nombre = f"{uuid.uuid4().hex}{ext}"
    destino = upload_dir / nombre

    leidos = 0
    with destino.open("wb") as out:
        while True:
            chunk = archivo.file.read(64 * 1024)
            if not chunk:
                break
            leidos += len(chunk)
            if leidos > max_bytes:
                out.close()
                destino.unlink(missing_ok=True)
                mb = max_bytes // (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"El archivo supera el máximo permitido ({mb} MB).",
                )
            out.write(chunk)

    return f"comprobantes/{nombre}"

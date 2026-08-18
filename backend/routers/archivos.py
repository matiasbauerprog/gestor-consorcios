"""Entrega de archivos subidos contra una URL firmada.

Este router es **público a propósito**: no puede exigir `Authorization` porque
lo consumen `<img src>` y `<a href>`, que no mandan headers. La autorización ya
ocurrió antes, cuando el usuario pidió la URL a un endpoint autenticado que
verificó que el archivo le correspondía; acá sólo se comprueba que la firma sea
auténtica y que no haya vencido.
"""
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ..storage import abrir_archivo, verificar_firma

router = APIRouter(prefix="/archivos", tags=["Archivos"])


@router.get(
    "/{clave:path}",
    summary="Descargar un archivo con URL firmada",
    response_class=StreamingResponse,
)
def descargar_archivo(
    clave: str,
    exp: str = Query(default=""),
    firma: str = Query(default=""),
) -> StreamingResponse:
    if not verificar_firma(clave, exp, firma):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enlace invalido o vencido.",
        )

    try:
        chunks, content_type = abrir_archivo(clave)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado."
        )

    return StreamingResponse(
        chunks,
        media_type=content_type,
        # private: es de un solo usuario, ningun proxy compartido debe cachearlo.
        headers={"Cache-Control": "private, max-age=60"},
    )

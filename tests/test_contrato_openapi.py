"""El contrato (`openapi.yaml`) y la app tienen que exponer lo mismo.

La regla del proyecto es OpenAPI-first: el endpoint se documenta antes de
implementarse. Sin un test, esa regla depende de que nadie se olvide — y ya se
olvidó al menos dos veces (`/tesoreria/movimientos-pdf` y
`DELETE /comprobantes/{comprobante_id}` vivían en el router y no en el
contrato).

Este test compara **paths y verbos**, no schemas: alcanza para atrapar el
olvido, que es el error real, sin volverse un espejo frágil de cada campo.
"""
import re
from pathlib import Path

import yaml

from backend.main import app

VERBOS = {"get", "post", "put", "patch", "delete"}

#: Rutas que FastAPI monta solo: no son endpoints del sistema y no van al
#: contrato.
RUTAS_DE_FASTAPI = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}

RAIZ = Path(__file__).resolve().parents[1]


def _normalizar(path: str) -> str:
    """`/archivos/{clave:path}` -> `/archivos/{clave}`.

    El `:path` es el conversor de Starlette (deja que el valor tenga barras).
    OpenAPI no tiene esa sintaxis, así que el contrato escribe `{clave}` y la
    diferencia se salda acá y no en el yaml.
    """
    return re.sub(r"\{(\w+):[a-z]+\}", r"{\1}", path)


def _operaciones_documentadas() -> set[tuple[str, str]]:
    spec = yaml.safe_load((RAIZ / "openapi.yaml").read_text(encoding="utf-8"))
    return {
        (_normalizar(path), verbo.lower())
        for path, operaciones in spec["paths"].items()
        for verbo in operaciones
        if verbo.lower() in VERBOS
    }


def _operaciones_de(rutas) -> set[tuple[str, str]]:
    return {
        (_normalizar(ruta.path), metodo.lower())
        for ruta in rutas
        if getattr(ruta, "methods", None) and ruta.path not in RUTAS_DE_FASTAPI
        for metodo in ruta.methods
        if metodo.lower() in VERBOS
    }


def _operaciones_de_la_app() -> set[tuple[str, str]]:
    """La app montada + los routers que sólo se montan bajo bandera.

    `/auth/demo-login` se registra únicamente con `DEMO_MODE` (ver "Candado 2"
    en backend/main.py): fuera del modo demo el endpoint no existe, y eso es a
    propósito. Pero está en el contrato, así que hay que contarlo — leyéndolo
    del router de verdad, no como una excepción escrita a mano que puede
    quedar mintiendo si el endpoint se borra.
    """
    from backend.routers import demo as demo_router

    return _operaciones_de(app.routes) | _operaciones_de(demo_router.router.routes)


def _formatear(operaciones: set[tuple[str, str]]) -> str:
    return "\n".join(f"  {verbo.upper():6} {path}" for path, verbo in sorted(operaciones))


def test_no_hay_endpoints_sin_documentar():
    faltan = _operaciones_de_la_app() - _operaciones_documentadas()
    assert not faltan, (
        "Estos endpoints existen en la app pero no están en openapi.yaml.\n"
        "El contrato va primero: documentalos ahí antes de dejarlos en el router.\n"
        + _formatear(faltan)
    )


def test_no_hay_contrato_sin_implementar():
    sobran = _operaciones_documentadas() - _operaciones_de_la_app()
    assert not sobran, (
        "Estos endpoints están en openapi.yaml pero la app no los expone.\n"
        "O falta implementarlos, o quedaron en el contrato después de borrarse.\n"
        + _formatear(sobran)
    )


def test_todos_los_tags_usados_estan_declarados():
    """Un tag mal escrito en un path deja la operación fuera de su grupo en la
    documentación generada, y no falla en ningún lado. Pasó con `Super-Admin`
    contra el declarado `SuperAdmin`."""
    spec = yaml.safe_load((RAIZ / "openapi.yaml").read_text(encoding="utf-8"))
    declarados = {t["name"] for t in spec["tags"]}
    usados = {
        tag
        for operaciones in spec["paths"].values()
        for operacion in operaciones.values()
        if isinstance(operacion, dict)
        for tag in operacion.get("tags", [])
    }
    assert not usados - declarados, (
        f"Tags usados en paths pero no declarados en `tags:`: {sorted(usados - declarados)}"
    )

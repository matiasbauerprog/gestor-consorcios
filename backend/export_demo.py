"""Vuelca el dataset demo a un JSON con la forma que devuelve cada endpoint.

No arma los datos a mano: los pide a la propia API con el mismo TestClient
in-process que usa el generador. Por eso la forma del export no puede
divergir del contrato — si un endpoint cambia su respuesta, el export cambia
con él en la siguiente corrida.
"""
import json
from pathlib import Path

#: (rol, path). El rol decide con qué token se pide: "admin" o "depto".
#: Las 16 rutas quedan como "admin": se relevó cada router y ninguna necesita
#: el token de un departamento para devolver datos útiles para la demo — son
#: admin-only (gastos, proveedores, periodos, clases-prorrateo, cajas,
#: estado-financiero, configuración, departamentos) o de lectura abierta a
#: cualquier rol autenticado donde el admin ve el conjunto más amplio, no uno
#: recortado por depto (expensas, comprobantes, comunicados, peticiones,
#: reservas, reportes/morosos).
RUTAS_EXPORTADAS: list[tuple[str, str]] = [
    ("admin", "/departamentos"),
    ("admin", "/expensas"),
    ("admin", "/gastos"),
    ("admin", "/comprobantes"),
    ("admin", "/comunicados"),
    ("admin", "/amenities"),
    ("admin", "/reservas"),
    ("admin", "/peticiones"),
    ("admin", "/trabajos"),
    ("admin", "/proveedores"),
    ("admin", "/periodos"),
    ("admin", "/clases-prorrateo"),
    ("admin", "/cajas"),
    ("admin", "/estado-financiero"),
    ("admin", "/reportes/morosos"),
    ("admin", "/configuracion"),
]


def exportar(api, admin_token: str, tokens_depto: dict[int, str], cid: int) -> dict:
    """Pide cada ruta declarada y devuelve {path: cuerpo}."""
    datos: dict = {}
    for rol, path in RUTAS_EXPORTADAS:
        token = admin_token if rol == "admin" else next(iter(tokens_depto.values()))
        r = api.req("GET", path, token=token, cid=cid)
        datos[path] = r.json()
    return datos


def escribir(datos: dict, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(datos, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

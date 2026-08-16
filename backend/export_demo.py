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


#: Rutas cuyo endpoint pagina con `limit`/`offset` y en el dataset real supera
#: el `limit` default (50): sin pedir todas las páginas, el export queda
#: truncado a la mitad de un período (108 expensas → 50, 82 comprobantes →
#: 50). El resto de las rutas exportadas no tiene ese riesgo: o no acepta
#: `limit`/`offset` (lo ignora si igual se lo mandamos) o el volumen real
#: nunca se acerca al default.
_RUTAS_PAGINADAS = {"/expensas", "/gastos", "/comprobantes"}

#: Tamaño de página al paginar: el máximo que aceptan esos tres endpoints
#: (`limit: int = Query(default=50, ge=1, le=200)`). Pedir de a 200 en vez
#: de agotar con el default de 50 minimiza la cantidad de vueltas.
_TAMANO_PAGINA = 200


def _pedir_paginado(api, path: str, token: str, cid: int) -> list:
    """Junta todas las páginas de un endpoint `limit`/`offset` hasta agotarlo.

    Una página con menos registros que `_TAMANO_PAGINA` es, por construcción
    (el backend nunca devuelve una página parcial salvo que sea la última),
    la señal de que no queda nada más por pedir — no hace falta que el
    endpoint informe un total aparte.
    """
    resultado: list = []
    offset = 0
    while True:
        r = api.req("GET", path, token=token, cid=cid,
                     params={"limit": _TAMANO_PAGINA, "offset": offset})
        pagina = r.json()
        resultado.extend(pagina)
        if len(pagina) < _TAMANO_PAGINA:
            return resultado
        offset += _TAMANO_PAGINA


def exportar(api, admin_token: str, tokens_depto: dict[int, str], cid: int) -> dict:
    """Pide cada ruta declarada y devuelve {path: cuerpo}.

    Las rutas de `_RUTAS_PAGINADAS` se piden página por página hasta
    agotarlas — ver `_pedir_paginado`. El resto se pide de una sola vez,
    como devuelve el endpoint.
    """
    datos: dict = {}
    for rol, path in RUTAS_EXPORTADAS:
        token = admin_token if rol == "admin" else next(iter(tokens_depto.values()))
        if path in _RUTAS_PAGINADAS:
            datos[path] = _pedir_paginado(api, path, token, cid)
        else:
            r = api.req("GET", path, token=token, cid=cid)
            datos[path] = r.json()
    return datos


def exportar_pdfs(api, admin_token: str, cid: int, expensas: list[dict],
                  destino: Path) -> dict[int, str]:
    """Baja el PDF de cada expensa y lo escribe en `destino`.

    Devuelve {expensa_id: nombre de archivo} para que la demo sepa qué abrir.
    El nombre lleva sólo el id de la expensa: viaja en una URL pública y no
    tiene por qué exponer la unidad ni el propietario.
    """
    destino.mkdir(parents=True, exist_ok=True)
    mapa: dict[int, str] = {}
    for expensa in expensas:
        expensa_id = expensa["id"]
        r = api.req("GET", f"/expensas/{expensa_id}/pdf", token=admin_token, cid=cid)
        nombre = f"expensa-{expensa_id}.pdf"
        (destino / nombre).write_bytes(r.content)
        mapa[expensa_id] = nombre
    return mapa


def escribir(datos: dict, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(datos, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

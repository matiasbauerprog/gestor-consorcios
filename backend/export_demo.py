"""Vuelca el dataset demo a un JSON con la forma que devuelve cada endpoint.

No arma los datos a mano: los pide a la propia API con el mismo TestClient
in-process que usa el generador. Por eso la forma del export no puede
divergir del contrato — si un endpoint cambia su respuesta, el export cambia
con él en la siguiente corrida.
"""
import hashlib
import json
from datetime import date
from pathlib import Path

#: (rol, path). El rol decide con qué token se pide: "admin" o "depto".
#: La mayoría queda como "admin": se relevó cada router y no necesita el
#: token de un departamento para devolver datos útiles para la demo — son
#: admin-only (gastos, proveedores, periodos, clases-prorrateo, cajas,
#: tesorería, configuración, departamentos, movimientos/cuentas,
#: gastos-habituales, reportes) o de lectura abierta a cualquier rol
#: autenticado donde el admin ve el conjunto más amplio, no uno recortado por
#: depto (expensas, comprobantes, comunicados, peticiones, reservas,
#: reportes/morosos, notificaciones). La única excepción es
#: `/movimientos/mi-cuenta`: ese endpoint exige Rol.departamento (401 con
#: token de admin) y además devuelve la cuenta del departamento *dueño* del
#: token, así que "admin" no sirve ni por permisos ni por resultado — ver
#: `_token_mi_cuenta`.
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
    ("admin", "/tesoreria"),
    # Sin filtrar: el padrón entero, deudores y al día. El default del
    # endpoint es `solo_deudores=True`, y con ese recorte la casilla "excluir
    # saldos al día y a favor" de la pantalla queda muerta — no tiene de dónde
    # sacar las unidades que faltan. El recorte lo hace el sustituto del
    # navegador (`solo_deudores` en frontend/src/demo/rutas.js).
    ("admin", "/reportes/morosos?solo_deudores=false"),
    ("admin", "/configuracion"),
    ("admin", "/me/consorcios"),
    ("depto", "/movimientos/mi-cuenta"),
    ("admin", "/movimientos/cuentas"),
    ("admin", "/gastos-habituales"),
    ("admin", "/reportes/estado-financiero"),
    ("admin", "/reportes/proveedores"),
    ("admin", "/notificaciones"),
    ("admin", "/notificaciones/no-leidas-count"),
    # Preferencias de aviso de ADMINISTRACIÓN. La versión de depto no entra acá
    # -- ver el bloque dedicado al final de `exportar()`, porque comparte path
    # con ésta y en este dict plano la segunda pisaría a la primera.
    ("admin", "/notificaciones/preferencias"),
    # Módulo Personal. El generador ya crea el legajo del encargado, el
    # catálogo de haberes, los conceptos de liquidación y las liquidaciones
    # mensuales (`crear_catalogo_personal` en backend/seed_demo.py); sin
    # estas cuatro rutas esos datos existen pero no llegan a la demo.
    ("admin", "/empleados"),
    ("admin", "/haberes"),
    ("admin", "/conceptos-liquidacion"),
    ("admin", "/liquidaciones"),
    # Lo que le faltaba a Tesorería y a Configuración para verse enteras.
    ("admin", "/transferencias-caja"),
    ("admin", "/usuarios"),
    ("admin", "/trabajos-recurrentes"),
    # La administración y sus consorcios. Sin esto, "Consorcios de la
    # administración" muestra el estado vacío de una cuenta recién creada
    # arriba de un consorcio con seis meses cargados.
    ("admin", "/consorcios"),
]

#: Rutas que se piden una vez por departamento. La clave en el JSON lleva el
#: id resuelto (`/departamentos/7/cuenta`), para que el sustituto del
#: navegador las encuentre por el mismo path que pide la pantalla.
RUTAS_POR_DEPARTAMENTO: list[str] = [
    "/departamentos/{id}/cuenta",
    "/departamentos/{id}/coeficientes",
]

#: Ídem por período cerrado.
RUTAS_POR_PERIODO: list[str] = [
    "/periodos/{periodo}/estado",
    "/reportes/gastos/{periodo}",
]

#: Ídem por trabajo: el detalle de un trabajo pide sus presupuestos al
#: abrirse (ModalDetalleTrabajo), y comparar presupuestos para aprobar uno es
#: media pantalla del argumento de mantenimiento.
RUTAS_POR_TRABAJO: list[str] = [
    "/trabajos/{id}/presupuestos",
]

#: Ídem por caja: el detalle de una caja lista sus movimientos aparte del
#: saldo que ya viene en `/cajas`.
RUTAS_POR_CAJA: list[str] = [
    "/cajas/{id}/movimientos",
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


#: Código del departamento pinneado como "propietario al día"
#: (`CODIGO_PUNTUAL_FIJO` en `backend/seed_demo.py`): el destino del botón
#: del selector de rol en /auth/demo-login. `/movimientos/mi-cuenta`
#: devuelve la cuenta de quien sea *dueño* del token con el que se pida, así
#: que hay que fijar cuál — a diferencia del resto de las rutas "admin",
#: donde cualquier token del rol alcanza para el mismo resultado.
_CODIGO_DEPTO_MI_CUENTA = "UF-01A"

#: Códigos de los DOS perfiles de depto del selector de demo-login
#: (`PERFILES_DEMO` en frontend/src/demo/rutas.js: "UF-01A" y "UF-03C").
#: A diferencia de `_CODIGO_DEPTO_MI_CUENTA` (alcanza con fijar UNO porque
#: `/movimientos/mi-cuenta` da lo mismo con cualquier token de depto salvo
#: por de quién es la cuenta), acá hacen falta los DOS: `/notificaciones` es
#: historia personal de la unidad, no un catálogo compartido por rol como
#: preferencias, así que una sola variante le mostraría a un perfil la
#: bandeja de la unidad ajena — ver el bloque dedicado en `exportar()`.
_CODIGOS_DEPTOS_NOTIFICACIONES = ("UF-01A", "UF-03C")


def _token_mi_cuenta(datos: dict, tokens_depto: dict[int, str]) -> str:
    """Token del depto pinneado para `/movimientos/mi-cuenta`.

    Busca el id del depto con código `_CODIGO_DEPTO_MI_CUENTA` en
    `datos["/departamentos"]` (ya resuelto en este punto del export) y
    devuelve su token. Si por lo que sea no aparece —dataset de test con
    cuerpos falsos, o el depto pinneado no tiene login— cae a cualquier
    token disponible en vez de romper el export entero por una ruta.
    """
    for depto in datos.get("/departamentos", []):
        if depto.get("codigo") == _CODIGO_DEPTO_MI_CUENTA:
            token = tokens_depto.get(depto.get("id"))
            if token is not None:
                return token
            break
    return next(iter(tokens_depto.values()))


def _verificar(path: str, respuesta) -> None:
    """Corta el export si una ruta declarada no contestó con datos.

    Sin esto, una ruta mal escrita en las tablas de arriba no rompe nada
    visible: el backend contesta 404/405, el cuerpo del error (`{"detail":
    ...}`) se guarda en el dataset como si fueran datos, y la pantalla que
    lo consume aparece vacía en la demo sin que nadie se entere. Pasó con
    `/coeficientes`, que no existe como listado.
    """
    if respuesta.status_code >= 400:
        raise RuntimeError(
            f"El export pidió {path} y el backend contestó "
            f"{respuesta.status_code}. Revisá la ruta en las tablas de "
            f"export_demo.py: tal como está, el dataset guardaría el error."
        )


def exportar(api, admin_token: str, tokens_depto: dict[int, str], cid: int) -> dict:
    """Pide cada ruta declarada y devuelve {path: cuerpo}.

    Las rutas de `_RUTAS_PAGINADAS` se piden página por página hasta
    agotarlas — ver `_pedir_paginado`. El resto se pide de una sola vez,
    como devuelve el endpoint. Después de las rutas sueltas, repite las
    plantillas de `RUTAS_POR_DEPARTAMENTO` y `RUTAS_POR_PERIODO` una vez por
    cada departamento/período ya exportado, y deja `_generado` con la fecha
    de hoy (§3.3 del spec: sin eso no se puede calcular el desplazamiento de
    fechas al abrir la demo).
    """
    datos: dict = {}
    for rol, path in RUTAS_EXPORTADAS:
        if rol == "admin":
            token = admin_token
        else:
            token = _token_mi_cuenta(datos, tokens_depto)
        # La clave va sin query: el sustituto del navegador busca por path
        # limpio y aplica los filtros aparte (frontend/src/demo/rutas.js).
        # Al backend sí se le pide con el query, que es lo que decide qué
        # datos trae.
        clave = path.split("?")[0]
        if path in _RUTAS_PAGINADAS:
            datos[clave] = _pedir_paginado(api, path, token, cid)
        else:
            r = api.req("GET", path, token=token, cid=cid)
            _verificar(path, r)
            datos[clave] = r.json()

    # Preferencias de aviso de DEPARTAMENTO. `eventos_para_rol` (backend/
    # notificaciones/catalogo.py) devuelve catálogos disjuntos por rol -- no
    # hay ítems en común entre administración y depto -- así que la lista de
    # depto no puede guardarse bajo el mismo path limpio que la de admin sin
    # pisarla en este dict plano. Va aparte, bajo una clave auxiliar (mismo
    # criterio que `_pdfs`) que `frontend/src/demo/servidor.js` sabe elegir
    # según quién entró. Cualquier token de depto sirve: a diferencia de
    # `/movimientos/mi-cuenta`, acá el resultado no depende de qué unidad es
    # -- es el mismo catálogo para todo el rol, y el dataset no siembra
    # preferencias personalizadas por usuario.
    token_depto = next(iter(tokens_depto.values()))
    r = api.req("GET", "/notificaciones/preferencias", token=token_depto, cid=cid)
    _verificar("/notificaciones/preferencias", r)
    datos["_preferencias_depto"] = r.json()

    # Notificaciones y contador de DEPARTAMENTO. A diferencia del bloque de
    # arriba, acá el contenido SÍ depende de qué unidad es: son avisos en
    # segunda persona atados a la cuenta de cada usuario ("tu comprobante fue
    # aprobado"), no un catálogo compartido por rol. Con una sola variante,
    # el perfil que no coincidiera vería la bandeja de la unidad ajena — así
    # que se piden las DOS, una por cada código de _CODIGOS_DEPTOS_NOTIFICACIONES,
    # y se guardan bajo una clave auxiliar {departamento_id: datos} que
    # `frontend/src/demo/servidor.js` indexa por `sesion.departamento_id`
    # (mismo criterio que `_pdfs`: dict por id bajo una clave aparte).
    notifs_por_depto: dict[int, list] = {}
    count_por_depto: dict[int, dict] = {}
    for depto in datos.get("/departamentos", []):
        if depto.get("codigo") not in _CODIGOS_DEPTOS_NOTIFICACIONES:
            continue
        token = tokens_depto.get(depto["id"])
        if token is None:
            continue
        r = api.req("GET", "/notificaciones", token=token, cid=cid)
        _verificar("/notificaciones", r)
        notifs_por_depto[depto["id"]] = r.json()

        r = api.req("GET", "/notificaciones/no-leidas-count", token=token, cid=cid)
        _verificar("/notificaciones/no-leidas-count", r)
        count_por_depto[depto["id"]] = r.json()
    datos["_notificaciones_depto"] = notifs_por_depto
    datos["_notificaciones_no_leidas_depto"] = count_por_depto

    for depto in datos.get("/departamentos", []):
        for plantilla in RUTAS_POR_DEPARTAMENTO:
            path = plantilla.format(id=depto["id"])
            r = api.req("GET", path, token=admin_token, cid=cid)
            _verificar(path, r)
            datos[path] = r.json()

    for periodo in datos.get("/periodos", []):
        for plantilla in RUTAS_POR_PERIODO:
            path = plantilla.format(periodo=periodo["periodo"])
            r = api.req("GET", path, token=admin_token, cid=cid)
            _verificar(path, r)
            datos[path] = r.json()

    for coleccion, plantillas in (
        ("/cajas", RUTAS_POR_CAJA),
        ("/trabajos", RUTAS_POR_TRABAJO),
    ):
        for item in datos.get(coleccion, []):
            for plantilla in plantillas:
                path = plantilla.format(id=item["id"])
                r = api.req("GET", path, token=admin_token, cid=cid)
                _verificar(path, r)
                datos[path] = r.json()

    datos["_generado"] = date.today().isoformat()
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


def exportar_comprobantes(datos: dict, origen_uploads: Path, origen_assets: Path,
                          destino: Path) -> dict[int, str]:
    """Copia las imágenes de comprobante a un directorio estático y reescribe
    `archivo_path` en `datos["/comprobantes"]` para que apunten ahí.

    En la demo sin backend, `archivo_path` como lo devuelve la API
    ("comprobantes/<hash>.png") no sirve: es una clave de almacenamiento que
    sólo se puede resolver pidiendo una URL firmada a un servidor que en la
    demo no existe. `imagen_comprobante` (backend/seed_demo.py) rota entre sólo
    TRES imágenes reales para los 82 comprobantes del dataset, así que se
    copian esas tres una única vez desde `origen_assets` —no una por
    comprobante— y se identifica cuál le tocó a cada uno por el hash del
    contenido real que subió al backend (`origen_uploads`), sin depender del
    orden de creación del generador.

    Devuelve {comprobante_id: nombre de archivo} a título informativo; el
    efecto que importa es la reescritura in-place de `datos`.
    """
    destino.mkdir(parents=True, exist_ok=True)
    hash_a_nombre: dict[str, str] = {}
    for archivo in sorted(origen_assets.glob("comprobante_*.png")):
        contenido = archivo.read_bytes()
        (destino / archivo.name).write_bytes(contenido)
        hash_a_nombre[hashlib.sha256(contenido).hexdigest()] = archivo.name

    mapa: dict[int, str] = {}
    for c in datos.get("/comprobantes", []):
        ruta = c.get("archivo_path")
        if not ruta:
            continue
        # `ruta` es la clave de almacenamiento relativa a UPLOAD_DIR
        # (`comprobantes/<hash>.png`), que es como se persiste en la base.
        origen = origen_uploads / ruta
        if not origen.exists():
            continue
        contenido = origen.read_bytes()
        nombre = hash_a_nombre.get(hashlib.sha256(contenido).hexdigest())
        if nombre is None:
            continue
        c["archivo_path"] = f"/demo-comprobantes/{nombre}"
        mapa[c["id"]] = nombre
    return mapa


def escribir(datos: dict, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(datos, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

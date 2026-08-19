import pytest

from backend.export_demo import (
    RUTAS_EXPORTADAS,
    RUTAS_POR_CAJA,
    RUTAS_POR_DEPARTAMENTO,
    RUTAS_POR_PERIODO,
    RUTAS_POR_TRABAJO,
    exportar,
    exportar_comprobantes,
    exportar_pdfs,
)


class _ApiFalsa:
    """Registra qué se pidió y devuelve un cuerpo reconocible por path.

    Cada elemento lleva `id` y `periodo` además del path que lo originó: el
    exportador recorre `/departamentos` y `/periodos` para resolver las
    plantillas de `RUTAS_POR_DEPARTAMENTO` y `RUTAS_POR_PERIODO`, así que un
    doble que devolviera sólo `path_pedido` no representaría ninguna respuesta
    que el backend real pueda dar.
    """

    def __init__(self):
        self.pedidos = []

    def req(self, metodo, path, **kwargs):
        self.pedidos.append((metodo, path))

        class _R:
            status_code = 200

            @staticmethod
            def json():
                return [{"path_pedido": path, "id": 1, "periodo": "2026-01"}]

        return _R()


def test_exporta_todas_las_rutas_declaradas():
    api = _ApiFalsa()
    datos = exportar(api, "tok-admin", {1: "tok-depto"}, cid=1)
    paths_pedidos = [p for _, p in api.pedidos]
    for _rol, path in RUTAS_EXPORTADAS:
        assert path in paths_pedidos, path


def test_el_export_indexa_por_path():
    api = _ApiFalsa()
    datos = exportar(api, "tok-admin", {1: "tok-depto"}, cid=1)
    assert "/departamentos" in datos
    assert datos["/departamentos"][0]["path_pedido"] == "/departamentos"


def test_incluye_las_rutas_del_recorrido_de_venta():
    # Si alguien saca una de estas del export, la demo del navegador queda
    # sin datos en una pantalla del recorrido.
    paths = {p.split("?")[0] for _rol, p in RUTAS_EXPORTADAS}
    for imprescindible in [
        "/departamentos", "/expensas", "/gastos", "/comprobantes",
        "/comunicados", "/amenities", "/reservas", "/peticiones",
        "/proveedores", "/periodos", "/reportes/morosos",
    ]:
        assert imprescindible in paths


class _ApiFalsaPaginada:
    """Simula un endpoint con más registros que el tamaño de una página.

    Cada ruta pedida se pagina de forma independiente: `TOTAL` registros
    servidos de a `limit` (leído de `params`), respetando `offset`. Sin
    `params` (rutas no paginadas) devuelve una sola página fija, como
    `_ApiFalsa`.
    """

    TOTAL = 220

    def __init__(self):
        self.pedidos = []

    def req(self, metodo, path, **kwargs):
        params = kwargs.get("params") or {}
        self.pedidos.append((metodo, path, dict(params)))
        limit = params.get("limit")
        offset = params.get("offset", 0)
        total = self.TOTAL

        class _R:
            status_code = 200

            @staticmethod
            def json():
                if limit is None:
                    # Ruta no paginada: mismo cuerpo mínimo que `_ApiFalsa`,
                    # con `id` y `periodo` porque el exportador recorre
                    # `/departamentos` y `/periodos` para resolver plantillas.
                    return [{"path_pedido": path, "id": 1, "periodo": "2026-01"}]
                restantes = max(total - offset, 0)
                cantidad = min(limit, restantes)
                return [{"id": offset + i} for i in range(cantidad)]

        return _R()


def test_pagina_hasta_agotar_cuando_hay_mas_registros_que_el_tamano_de_pagina():
    # Si el exportador se quedara con la primera página, la demo del
    # navegador mostraría un dataset truncado a la mitad de un período.
    api = _ApiFalsaPaginada()
    datos = exportar(api, "tok-admin", {1: "tok-depto"}, cid=1)

    assert len(datos["/expensas"]) == _ApiFalsaPaginada.TOTAL
    assert len(datos["/gastos"]) == _ApiFalsaPaginada.TOTAL
    assert len(datos["/comprobantes"]) == _ApiFalsaPaginada.TOTAL

    # No se quedó con la primera página: pidió más de una.
    pedidos_expensas = [p for _, p, _ in api.pedidos if p == "/expensas"]
    assert len(pedidos_expensas) >= 2

    # Sin huecos ni duplicados: los ids cubren el rango completo.
    ids = sorted(item["id"] for item in datos["/expensas"])
    assert ids == list(range(_ApiFalsaPaginada.TOTAL))


class _ApiPdf:
    """Devuelve bytes de PDF para cualquier path que termine en /pdf."""

    def req(self, metodo, path, **kwargs):
        class _R:
            status_code = 200
            content = b"%PDF-1.4 contenido de prueba"

        return _R()


def test_exporta_un_pdf_por_expensa(tmp_path):
    expensas = [{"id": 7, "departamento_id": 1}, {"id": 8, "departamento_id": 2}]
    mapa = exportar_pdfs(_ApiPdf(), "tok", 1, expensas, tmp_path)
    assert set(mapa) == {7, 8}
    for expensa_id, nombre in mapa.items():
        assert (tmp_path / nombre).exists()
        assert (tmp_path / nombre).read_bytes().startswith(b"%PDF")


def test_el_nombre_del_pdf_no_expone_datos_del_vecino(tmp_path):
    # El nombre viaja en una URL pública: sólo el id de la expensa.
    expensas = [{"id": 7, "departamento_id": 1}]
    mapa = exportar_pdfs(_ApiPdf(), "tok", 1, expensas, tmp_path)
    assert mapa[7] == "expensa-7.pdf"


def test_exporta_las_tres_imagenes_unicas_y_reescribe_el_path(tmp_path):
    # 82 comprobantes reales rotan sobre sólo 3 imágenes (imagen_comprobante
    # en backend/seed_demo.py): copiar los 3 archivos de origen una vez, no
    # 82 veces el mismo contenido.
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "comprobante_1.png").write_bytes(b"contenido-uno")
    (assets / "comprobante_2.png").write_bytes(b"contenido-dos")
    (assets / "comprobante_3.png").write_bytes(b"contenido-tres")

    uploads = tmp_path / "uploads"
    # exist_ok=True: el fixture autouse `_temp_upload_dir` (tests/conftest.py)
    # ya crea `tmp_path/"uploads"/"comprobantes"` para redirigir
    # Settings.UPLOAD_DIR en toda la suite.
    (uploads / "comprobantes").mkdir(parents=True, exist_ok=True)
    (uploads / "comprobantes" / "aaa.png").write_bytes(b"contenido-dos")
    (uploads / "comprobantes" / "bbb.png").write_bytes(b"contenido-uno")

    destino = tmp_path / "public" / "demo-comprobantes"
    datos = {"/comprobantes": [
        {"id": 1, "archivo_path": "comprobantes/aaa.png"},
        {"id": 2, "archivo_path": "comprobantes/bbb.png"},
    ]}

    mapa = exportar_comprobantes(datos, uploads, assets, destino)

    # Sólo los 3 archivos de origen, no uno por comprobante.
    assert sorted(p.name for p in destino.iterdir()) == [
        "comprobante_1.png", "comprobante_2.png", "comprobante_3.png",
    ]
    assert mapa == {1: "comprobante_2.png", 2: "comprobante_1.png"}
    assert datos["/comprobantes"][0]["archivo_path"] == "/demo-comprobantes/comprobante_2.png"
    assert datos["/comprobantes"][1]["archivo_path"] == "/demo-comprobantes/comprobante_1.png"
    # Ya no apunta al backend.
    for c in datos["/comprobantes"]:
        assert not c["archivo_path"].startswith("/uploads/")


def test_exportar_comprobantes_ignora_los_que_no_tienen_archivo(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "comprobante_1.png").write_bytes(b"contenido-uno")

    # exist_ok=True: ver el comentario del test anterior sobre el fixture
    # autouse `_temp_upload_dir`.
    uploads = tmp_path / "uploads"
    uploads.mkdir(exist_ok=True)

    destino = tmp_path / "public" / "demo-comprobantes"
    datos = {"/comprobantes": [{"id": 1, "archivo_path": None}]}

    mapa = exportar_comprobantes(datos, uploads, assets, destino)

    assert mapa == {}
    assert datos["/comprobantes"][0]["archivo_path"] is None


def test_exporta_la_cuenta_corriente_de_cada_departamento():
    # Es la base de "Mi cuenta" del propietario: sin esto la pantalla más
    # importante del circuito de cobranza queda vacía en la demo.
    assert "/departamentos/{id}/cuenta" in RUTAS_POR_DEPARTAMENTO


def test_exporta_el_estado_de_cada_periodo():
    assert "/periodos/{periodo}/estado" in RUTAS_POR_PERIODO


def test_exporta_las_rutas_que_el_recorrido_necesita():
    paths = {p.split("?")[0] for _rol, p in RUTAS_EXPORTADAS}
    for imprescindible in [
        "/me/consorcios",
        "/movimientos/mi-cuenta",
        "/movimientos/cuentas",
        "/gastos-habituales",
        "/reportes/estado-financiero",
        "/reportes/proveedores",
        "/notificaciones",
        "/notificaciones/no-leidas-count",
    ]:
        assert imprescindible in paths


def test_exporta_el_modulo_personal_completo():
    # El generador ya crea empleado, haberes, conceptos y liquidaciones
    # (crear_catalogo_personal en backend/seed_demo.py). Si el export no se
    # los lleva, la sección Personal de la demo queda vacía aunque los datos
    # existan.
    paths = {p.split("?")[0] for _rol, p in RUTAS_EXPORTADAS}
    for imprescindible in [
        "/empleados", "/haberes", "/conceptos-liquidacion", "/liquidaciones",
    ]:
        assert imprescindible in paths


def test_exporta_lo_que_falta_de_tesoreria_y_configuracion():
    paths = {p.split("?")[0] for _rol, p in RUTAS_EXPORTADAS}
    for imprescindible in [
        "/transferencias-caja",  # pestaña Transferencias
        "/usuarios",             # padrón
        "/trabajos-recurrentes", # tareas programadas
    ]:
        assert imprescindible in paths


def test_falla_si_una_ruta_declarada_devuelve_un_error():
    # Una ruta mal escrita en la tabla no revienta el export: el backend
    # contesta 405/404 y el cuerpo del error queda guardado como si fueran
    # datos, y la demo muestra una pantalla vacía sin que nadie se entere.
    # Pasó de verdad con "/coeficientes", que no existe como listado.
    class _ApiConRutaRota:
        def req(self, metodo, path, **kwargs):
            roto = path == "/gastos-habituales"

            class _R:
                status_code = 405 if roto else 200

                @staticmethod
                def json():
                    if roto:
                        return {"detail": "Method Not Allowed"}
                    return [{"id": 1, "periodo": "2026-01"}]

            return _R()

    with pytest.raises(RuntimeError, match="/gastos-habituales"):
        exportar(_ApiConRutaRota(), "tok-admin", {1: "tok-depto"}, cid=1)


def test_una_ruta_pedida_con_query_se_guarda_bajo_la_ruta_limpia():
    # El sustituto del navegador busca por path sin query y después aplica
    # los filtros (frontend/src/demo/servidor.js). Si la clave del dataset
    # llevara el `?solo_deudores=false` con el que se pidió, no la
    # encontraría nunca y el reporte quedaría vacío.
    api = _ApiFalsa()
    datos = exportar(api, "tok-admin", {1: "tok-depto"}, cid=1)
    assert "/reportes/morosos" in datos
    assert not any("?" in clave for clave in datos)
    # Pero al backend sí se le pidió con el query, o vendría ya filtrado.
    assert "/reportes/morosos?solo_deudores=false" in [p for _, p in api.pedidos]


def test_exporta_la_lista_de_consorcios_de_la_administracion():
    # Sin esto, "Consorcios de la administración" dice "todavía no tenés
    # consorcios" arriba de un consorcio con seis meses cargados.
    paths = {p.split("?")[0] for _rol, p in RUTAS_EXPORTADAS}
    assert "/consorcios" in paths


def test_exporta_los_presupuestos_de_cada_trabajo():
    # El detalle de un trabajo los pide al abrirse (ModalDetalleTrabajo):
    # aprobar un presupuesto es media pantalla del argumento de mantenimiento.
    assert "/trabajos/{id}/presupuestos" in RUTAS_POR_TRABAJO


def test_exporta_los_movimientos_de_cada_caja():
    # La pestaña Cajas abre el detalle de una caja: sin esto el detalle
    # aparece vacío aunque la caja tenga saldo.
    assert "/cajas/{id}/movimientos" in RUTAS_POR_CAJA


def test_resuelve_la_plantilla_por_caja():
    api = _ApiFalsa()
    datos = exportar(api, "tok-admin", {1: "tok-depto"}, cid=1)
    paths_pedidos = [p for _, p in api.pedidos]
    # `_ApiFalsa` devuelve un elemento con id 1 para toda ruta.
    assert "/cajas/1/movimientos" in paths_pedidos
    assert "/cajas/1/movimientos" in datos


def test_notificaciones_se_exportan_solo_para_los_dos_perfiles_de_depto():
    # /notificaciones es historia personal de la unidad (avisos en segunda
    # persona: "tu comprobante fue aprobado"), no un catálogo compartido por
    # rol como preferencias -- no alcanza una sola variante de depto. Ver el
    # comentario junto a _CODIGOS_DEPTOS_NOTIFICACIONES en export_demo.py.
    class _ApiDeptos:
        def req(self, metodo, path, **kwargs):
            token = kwargs.get("token")

            class _R:
                status_code = 200

                @staticmethod
                def json():
                    if path == "/departamentos":
                        return [
                            {"id": 1, "codigo": "UF-01A"},
                            {"id": 2, "codigo": "UF-02B"},
                            {"id": 3, "codigo": "UF-03C"},
                        ]
                    if path in ("/periodos", "/cajas", "/trabajos"):
                        return []
                    if path == "/notificaciones":
                        return [{"mensaje": f"para {token}"}]
                    if path == "/notificaciones/no-leidas-count":
                        return {"count": 1, "otros_consorcios": 0}
                    return [{"id": 1, "periodo": "2026-01"}]

            return _R()

    tokens_depto = {1: "tok-1", 2: "tok-2", 3: "tok-3"}
    datos = exportar(_ApiDeptos(), "tok-admin", tokens_depto, cid=1)

    # Sólo UF-01A (id 1) y UF-03C (id 3): UF-02B (id 2) no es un perfil del
    # selector de demo-login y no tiene por qué llevarse notificaciones.
    assert set(datos["_notificaciones_depto"].keys()) == {1, 3}
    assert set(datos["_notificaciones_no_leidas_depto"].keys()) == {1, 3}
    assert datos["_notificaciones_depto"][1][0]["mensaje"] == "para tok-1"
    assert datos["_notificaciones_depto"][3][0]["mensaje"] == "para tok-3"


def test_el_export_deja_la_fecha_de_generacion():
    # Sin esto no se puede calcular cuánto correr las fechas al abrir la demo.
    class _Api:
        def req(self, metodo, path, **kwargs):
            class _R:
                status_code = 200

                @staticmethod
                def json():
                    return []

            return _R()

    datos = exportar(_Api(), "tok", {1: "tok-depto"}, cid=1)
    assert "_generado" in datos
    assert datos["_generado"].count("-") == 2  # ISO: YYYY-MM-DD

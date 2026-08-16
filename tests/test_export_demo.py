from backend.export_demo import RUTAS_EXPORTADAS, exportar, exportar_pdfs


class _ApiFalsa:
    """Registra qué se pidió y devuelve un cuerpo reconocible por path."""

    def __init__(self):
        self.pedidos = []

    def req(self, metodo, path, **kwargs):
        self.pedidos.append((metodo, path))

        class _R:
            status_code = 200

            @staticmethod
            def json():
                return [{"path_pedido": path}]

        return _R()


def test_exporta_todas_las_rutas_declaradas():
    api = _ApiFalsa()
    datos = exportar(api, "tok-admin", {1: "tok-depto"}, cid=1)
    paths_pedidos = [p for _, p in api.pedidos]
    for _rol, path in RUTAS_EXPORTADAS:
        assert path in paths_pedidos


def test_el_export_indexa_por_path():
    api = _ApiFalsa()
    datos = exportar(api, "tok-admin", {1: "tok-depto"}, cid=1)
    assert "/departamentos" in datos
    assert datos["/departamentos"] == [{"path_pedido": "/departamentos"}]


def test_incluye_las_rutas_del_recorrido_de_venta():
    # Si alguien saca una de estas del export, la demo del navegador queda
    # sin datos en una pantalla del recorrido.
    paths = {p for _rol, p in RUTAS_EXPORTADAS}
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
                    return [{"path_pedido": path}]
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

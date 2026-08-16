from backend.export_demo import RUTAS_EXPORTADAS, exportar


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

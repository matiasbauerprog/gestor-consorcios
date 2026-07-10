"""IDOR cross-tenant: referenciar recursos de OTRO consorcio debe dar 404.

El seed de conftest carga en el consorcio 1: clase 500, proveedor 600,
caja 900, deptos 1-2, empleado 900, peticiones 10-11. Un admin del
consorcio 2 no debe poder usarlos como referencias.
"""
from datetime import date

import pytest


@pytest.fixture
def admin_c2(dos_consorcios):
    return dos_consorcios["headers_admin_c2"]


def _gasto_base(**overrides):
    base = {
        "periodo": "2026-07",
        "rubro": "servicios_publicos",
        "concepto": "Gasto cross-tenant",
        "monto": 1000,
        "forma_pago": "efectivo",
        "fecha_pago": "2026-07-05",
        "caja_id": 901,          # caja de c2
        "clase_prorrateo_id": None,
        "departamento_id": 3,    # depto de c2
        "proveedor_id": None,
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


@pytest.fixture
def proveedor_c2(client, admin_c2):
    r = client.post("/proveedores", json={
        "razon_social": "Proveedor C2 SRL", "cuit": "30-77777001-1",
    }, headers=admin_c2)
    assert r.status_code == 201
    return r.json()["id"]


def test_gasto_con_clase_de_otro_consorcio_404(client, admin_c2, proveedor_c2):
    r = client.post("/gastos", json=_gasto_base(
        clase_prorrateo_id=500, departamento_id=None, proveedor_id=proveedor_c2,
    ), headers=admin_c2)
    assert r.status_code == 404


def test_gasto_con_depto_de_otro_consorcio_404(client, admin_c2, proveedor_c2):
    r = client.post("/gastos", json=_gasto_base(
        departamento_id=1, proveedor_id=proveedor_c2,
    ), headers=admin_c2)
    assert r.status_code == 404


def test_gasto_con_proveedor_de_otro_consorcio_404(client, admin_c2):
    r = client.post("/gastos", json=_gasto_base(proveedor_id=600), headers=admin_c2)
    assert r.status_code == 404


def test_gasto_con_caja_de_otro_consorcio_404(client, admin_c2, proveedor_c2):
    r = client.post("/gastos", json=_gasto_base(
        caja_id=900, proveedor_id=proveedor_c2,
    ), headers=admin_c2)
    assert r.status_code == 404


def test_gasto_habitual_con_refs_de_otro_consorcio_404(client, admin_c2, proveedor_c2):
    # clase de c1
    r = client.post("/gastos-habituales", json={
        "nombre": "Plantilla cross", "rubro": "abonos_y_servicios",
        "clase_prorrateo_id": 500, "proveedor_id": proveedor_c2,
        "concepto": "x", "monto": 1000, "forma_pago": "efectivo", "caja_id": 901,
    }, headers=admin_c2)
    assert r.status_code == 404
    # caja de c1
    r2 = client.post("/gastos-habituales", json={
        "nombre": "Plantilla cross 2", "rubro": "abonos_y_servicios",
        "clase_prorrateo_id": 560, "proveedor_id": proveedor_c2,
        "concepto": "x", "monto": 1000, "forma_pago": "efectivo", "caja_id": 900,
    }, headers=admin_c2)
    assert r2.status_code == 404


def test_trabajo_desde_peticion_de_otro_consorcio_404(client, admin_c2):
    # Petición 10 es del consorcio 1.
    r = client.post("/trabajos", json={
        "peticion_id": 10, "descripcion": "Trabajo cross-tenant",
    }, headers=admin_c2)
    assert r.status_code == 404


def test_presupuesto_sobre_trabajo_de_otro_consorcio_404(client, dos_consorcios, admin_c2):
    # Admin c1 crea un trabajo en c1; admin c2 intenta presupuestarlo.
    r = client.post("/trabajos", json={"descripcion": "Trabajo c1"},
                    headers=dos_consorcios["headers_admin_c1"])
    assert r.status_code == 201
    trabajo_c1 = r.json()["id"]

    r2 = client.post(f"/trabajos/{trabajo_c1}/presupuestos",
                     data={"proveedor_id": "600", "monto": "5000"},
                     headers=admin_c2)
    assert r2.status_code == 404


def test_presupuesto_con_proveedor_de_otro_consorcio_404(client, dos_consorcios, admin_c2):
    r = client.post("/trabajos", json={"descripcion": "Trabajo c2"}, headers=admin_c2)
    assert r.status_code == 201
    trabajo_c2 = r.json()["id"]

    # proveedor 600 es de c1
    r2 = client.post(f"/trabajos/{trabajo_c2}/presupuestos",
                     data={"proveedor_id": "600", "monto": "5000"},
                     headers=admin_c2)
    assert r2.status_code == 404


def test_movimientos_de_caja_de_otro_consorcio_404(client, admin_c2):
    r = client.get("/cajas/900/movimientos", headers=admin_c2)
    assert r.status_code == 404


def test_crear_usuario_con_depto_de_otro_consorcio_404(client, admin_c2):
    r = client.post("/usuarios", json={
        "email": "cross@x.local", "password": "12345678x",
        "rol": "departamento", "departamento_id": 1,  # depto de c1
    }, headers=admin_c2)
    assert r.status_code == 404


def test_patch_usuario_de_otro_consorcio_404(client, dos_consorcios):
    # Admin de c2 intenta editar el email del usuario depto de c1 (id=2).
    r = client.patch("/usuarios/2", json={"email": "hackeado@x.local"},
                     headers=dos_consorcios["headers_admin_c2"])
    assert r.status_code == 404


def test_empleado_con_proveedor_de_otro_consorcio_404(client, admin_c2):
    r = client.post("/empleados", json={
        "nombre_completo": "Cross Tenant", "cuil": "20-99999999-1",
        "categoria": "encargado_permanente_sin_vivienda",
        "fecha_ingreso": "2024-01-01", "fecha_egreso": None,
        "sueldo_basico": 500000, "proveedor_id": 600,  # proveedor de c1
    }, headers=admin_c2)
    assert r.status_code == 404


def test_concepto_con_proveedor_de_otro_consorcio_404(client, admin_c2):
    r = client.post("/conceptos-liquidacion", json={
        "nombre": "Cross", "tipo": "descuento", "porcentaje": 5.0,
        "proveedor_id": 600, "orden": 1,
    }, headers=admin_c2)
    assert r.status_code == 404


def test_trabajo_recurrente_con_proveedor_de_otro_consorcio_404(client, admin_c2):
    r = client.post("/trabajos-recurrentes", json={
        "nombre": "Cross", "descripcion": "x",
        "periodicidad": "mensual", "proveedor_sugerido_id": 600,
    }, headers=admin_c2)
    assert r.status_code == 404


def test_liquidacion_con_caja_de_otro_consorcio_404(client, admin_c2, dos_consorcios, db):
    from backend.models import ClaseProrrateo, Empleado, CategoriaEmpleado, Proveedor
    # setup mínimo en c2: clase + proveedor + empleado propios
    db.add(ClaseProrrateo(id=565, consorcio_id=2, codigo="LQ", nombre="Liq c2", activa=True))
    db.add(Proveedor(id=655, consorcio_id=2, razon_social="Prov Liq C2", cuit="30-77777002-2", activo=True))
    db.flush()
    db.add(Empleado(
        id=905, consorcio_id=2, nombre_completo="Encargado C2", cuil="20-88888888-8",
        categoria=CategoriaEmpleado.encargado_permanente_sin_vivienda,
        fecha_ingreso=date(2024, 1, 1), sueldo_basico=500000.0,
        proveedor_id=655, activo=True,
    ))
    db.commit()

    r = client.post("/liquidaciones", json={
        "empleado_id": 905, "periodo": "2026-07",
        "caja_id": 900,  # caja de c1
        "haberes": [],
    }, headers=admin_c2)
    assert r.status_code == 404


def test_liquidacion_con_empleado_de_otro_consorcio_404(client, admin_c2):
    r = client.post("/liquidaciones", json={
        "empleado_id": 900,  # empleado de c1
        "periodo": "2026-07", "caja_id": 901, "haberes": [],
    }, headers=admin_c2)
    assert r.status_code == 404


def test_aprobar_comprobante_con_caja_de_otro_consorcio_400(client, dos_consorcios, db):
    from backend.models import Comprobante, EstadoComprobante
    # Comprobante pendiente en c2.
    c = Comprobante(
        consorcio_id=2, departamento_id=3, fecha_pago=date(2026, 7, 1),
        monto=1000.0, archivo_path="comprobantes/x.png",
        estado=EstadoComprobante.pendiente_verificacion,
    )
    db.add(c)
    db.commit()

    r = client.patch(f"/comprobantes/{c.id}", json={
        "estado": "aprobado", "caja_destino_id": 900,  # caja de c1
    }, headers=dos_consorcios["headers_admin_c2"])
    assert r.status_code == 400

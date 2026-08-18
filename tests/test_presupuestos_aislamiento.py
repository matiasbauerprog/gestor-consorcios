"""Aislamiento entre consorcios en las operaciones de escritura sobre presupuestos.

Las cuatro operaciones que mutan un presupuesto (editar, borrar, aprobar,
rechazar) resolvían el presupuesto con `db.get(Presupuesto, id)` sin comprobar a
qué consorcio pertenecía, y ni siquiera declaraban la dependencia que resuelve
el consorcio activo. La administración de un consorcio podía operar sobre los
presupuestos de otro con sólo conocer los ids.

`require_modulo` no alcanzaba: valida que el usuario tenga acceso al consorcio
del header, no que el recurso pedido sea de ese consorcio.
"""
from datetime import date

import pytest

from backend.models import EstadoPresupuesto, Presupuesto, Proveedor, Trabajo


@pytest.fixture()
def presupuesto_del_consorcio_2(db_session, dos_consorcios) -> int:
    """Un presupuesto que vive enteramente en el consorcio 2. Devuelve su id."""
    trabajo = Trabajo(
        id=900,
        consorcio_id=2,
        descripcion="Trabajo del consorcio ajeno",
    )
    proveedor = Proveedor(
        id=900,
        consorcio_id=2,
        razon_social="Proveedor del consorcio ajeno",
        cuit="30-90000000-0",
    )
    db_session.add_all([trabajo, proveedor])
    db_session.flush()

    presupuesto = Presupuesto(
        id=900,
        consorcio_id=2,
        trabajo_id=900,
        proveedor_id=900,
        monto=50000.0,
        fecha_presentacion=date.today(),
        estado=EstadoPresupuesto.presentado,
    )
    db_session.add(presupuesto)
    db_session.commit()
    return 900


def test_admin_de_otro_consorcio_no_puede_editar_el_presupuesto(
    client, db_session, dos_consorcios, presupuesto_del_consorcio_2
):
    r = client.patch(
        "/trabajos/900/presupuestos/900",
        headers=dos_consorcios["headers_admin_c1"],
        json={"monto": 1.0},
    )

    assert r.status_code == 404, r.text
    db_session.expire_all()
    assert db_session.get(Presupuesto, 900).monto == 50000.0


def test_admin_de_otro_consorcio_no_puede_borrar_el_presupuesto(
    client, db_session, dos_consorcios, presupuesto_del_consorcio_2
):
    r = client.delete(
        "/trabajos/900/presupuestos/900",
        headers=dos_consorcios["headers_admin_c1"],
    )

    assert r.status_code == 404, r.text
    db_session.expire_all()
    assert db_session.get(Presupuesto, 900) is not None


def test_admin_de_otro_consorcio_no_puede_aprobar_el_presupuesto(
    client, db_session, dos_consorcios, presupuesto_del_consorcio_2
):
    r = client.post(
        "/trabajos/900/presupuestos/900/aprobar",
        headers=dos_consorcios["headers_admin_c1"],
    )

    assert r.status_code == 404, r.text
    db_session.expire_all()
    assert db_session.get(Presupuesto, 900).estado == EstadoPresupuesto.presentado


def test_admin_de_otro_consorcio_no_puede_rechazar_el_presupuesto(
    client, db_session, dos_consorcios, presupuesto_del_consorcio_2
):
    r = client.post(
        "/trabajos/900/presupuestos/900/rechazar",
        headers=dos_consorcios["headers_admin_c1"],
    )

    assert r.status_code == 404, r.text
    db_session.expire_all()
    assert db_session.get(Presupuesto, 900).estado == EstadoPresupuesto.presentado


def test_editar_cambiando_el_proveedor_no_revienta(
    client, db_session, dos_consorcios, presupuesto_del_consorcio_2
):
    """`_validar_proveedor(db, cid, ...)` se llamaba con un `cid` que no existía
    en el ámbito de la función: cambiar el proveedor de un presupuesto tiraba
    NameError, o sea un 500."""
    proveedor_propio = Proveedor(
        id=901, consorcio_id=2, razon_social="Otro proveedor del consorcio 2", cuit="30-90000001-0"
    )
    db_session.add(proveedor_propio)
    db_session.commit()

    r = client.patch(
        "/trabajos/900/presupuestos/900",
        headers=dos_consorcios["headers_admin_c2"],
        json={"proveedor_id": 901},
    )

    assert r.status_code == 200, r.text
    assert r.json()["proveedor_id"] == 901


def test_editar_con_un_proveedor_de_otro_consorcio_se_rechaza(
    client, db_session, dos_consorcios, presupuesto_del_consorcio_2
):
    """El proveedor tiene que ser del mismo consorcio que el presupuesto."""
    proveedor_ajeno = Proveedor(
        id=902, consorcio_id=1, razon_social="Proveedor del consorcio 1", cuit="30-90000002-0"
    )
    db_session.add(proveedor_ajeno)
    db_session.commit()

    r = client.patch(
        "/trabajos/900/presupuestos/900",
        headers=dos_consorcios["headers_admin_c2"],
        json={"proveedor_id": 902},
    )

    assert r.status_code == 404, r.text

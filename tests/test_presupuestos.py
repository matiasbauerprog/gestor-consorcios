"""Tests del router de presupuestos."""
import io

from backend.models import EstadoPresupuesto, Presupuesto, Proveedor, Trabajo


def _crear_trabajo(db, descripcion="Trabajo de test"):
    t = Trabajo(consorcio_id=1, descripcion=descripcion)
    db.add(t); db.commit(); db.refresh(t)
    return t


def _proveedor_id(db) -> int:
    p = db.query(Proveedor).first()
    assert p is not None, "El seed debe tener al menos un proveedor"
    return p.id


def test_listar_presupuestos_vacio(client, headers_admin, db):
    t = _crear_trabajo(db)
    r = client.get(f"/trabajos/{t.id}/presupuestos", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


def test_crear_presupuesto_sin_archivo(client, headers_admin, db):
    t = _crear_trabajo(db)
    r = client.post(
        f"/trabajos/{t.id}/presupuestos",
        data={"proveedor_id": str(_proveedor_id(db)), "monto": "12000"},
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json()["monto"] == 12000
    assert r.json()["archivo_path"] is None


def test_crear_presupuesto_con_archivo(client, headers_admin, db):
    t = _crear_trabajo(db)
    files = {"archivo": ("cot.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")}
    r = client.post(
        f"/trabajos/{t.id}/presupuestos",
        data={"proveedor_id": str(_proveedor_id(db)), "monto": "15000"},
        files=files,
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json()["archivo_path"] is not None


def test_crear_proveedor_inexistente_404(client, headers_admin, db):
    t = _crear_trabajo(db)
    r = client.post(
        f"/trabajos/{t.id}/presupuestos",
        data={"proveedor_id": "99999", "monto": "100"},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_crear_monto_negativo_400(client, headers_admin, db):
    t = _crear_trabajo(db)
    r = client.post(
        f"/trabajos/{t.id}/presupuestos",
        data={"proveedor_id": str(_proveedor_id(db)), "monto": "-50"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_aprobar_un_segundo_desaprueba_el_primero(client, headers_admin, db):
    t = _crear_trabajo(db)
    p1 = Presupuesto(consorcio_id=1, trabajo_id=t.id, proveedor_id=_proveedor_id(db), monto=100)
    p2 = Presupuesto(consorcio_id=1, trabajo_id=t.id, proveedor_id=_proveedor_id(db), monto=200)
    db.add_all([p1, p2]); db.commit(); db.refresh(p1); db.refresh(p2)

    r1 = client.post(f"/trabajos/{t.id}/presupuestos/{p1.id}/aprobar", headers=headers_admin)
    assert r1.status_code == 200
    db.refresh(p1); db.refresh(t)
    assert p1.estado == EstadoPresupuesto.aprobado
    assert t.presupuesto_aprobado_id == p1.id

    r2 = client.post(f"/trabajos/{t.id}/presupuestos/{p2.id}/aprobar", headers=headers_admin)
    assert r2.status_code == 200
    db.refresh(p1); db.refresh(p2); db.refresh(t)
    assert p1.estado == EstadoPresupuesto.rechazado
    assert p2.estado == EstadoPresupuesto.aprobado
    assert t.presupuesto_aprobado_id == p2.id


def test_patch_aprobado_devuelve_409(client, headers_admin, db):
    t = _crear_trabajo(db)
    p = Presupuesto(consorcio_id=1, trabajo_id=t.id, proveedor_id=_proveedor_id(db), monto=100,
                    estado=EstadoPresupuesto.aprobado)
    db.add(p); db.commit(); db.refresh(p)
    r = client.patch(
        f"/trabajos/{t.id}/presupuestos/{p.id}",
        json={"monto": 500},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_delete_aprobado_devuelve_409(client, headers_admin, db):
    t = _crear_trabajo(db)
    p = Presupuesto(consorcio_id=1, trabajo_id=t.id, proveedor_id=_proveedor_id(db), monto=100,
                    estado=EstadoPresupuesto.aprobado)
    db.add(p); db.commit(); db.refresh(p)
    r = client.delete(f"/trabajos/{t.id}/presupuestos/{p.id}", headers=headers_admin)
    assert r.status_code == 409


def test_depto_no_puede_crear(client, headers_depto_a, db):
    t = _crear_trabajo(db)
    r = client.post(
        f"/trabajos/{t.id}/presupuestos",
        data={"proveedor_id": str(_proveedor_id(db)), "monto": "100"},
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_depto_puede_listar(client, headers_depto_a, db):
    t = _crear_trabajo(db)
    r = client.get(f"/trabajos/{t.id}/presupuestos", headers=headers_depto_a)
    assert r.status_code == 200

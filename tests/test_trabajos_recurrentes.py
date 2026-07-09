"""Tests del router de trabajos recurrentes."""
from backend.models import PeriodicidadRecurrente, Proveedor, TrabajoRecurrente


def test_listar_admin_200(client, headers_admin):
    r = client.get("/trabajos-recurrentes", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_listar_depto_403(client, headers_depto_a):
    r = client.get("/trabajos-recurrentes", headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_admin_201(client, headers_admin, db):
    prov = db.query(Proveedor).first()
    r = client.post("/trabajos-recurrentes", json={
        "nombre": "Limpieza tanque",
        "descripcion": "Limpieza trimestral del tanque",
        "periodicidad": "trimestral",
        "proveedor_sugerido_id": prov.id,
        "monto_estimado": 50000,
    }, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["nombre"] == "Limpieza tanque"


def test_crear_proveedor_inexistente_404(client, headers_admin):
    r = client.post("/trabajos-recurrentes", json={
        "nombre": "X", "descripcion": "y", "periodicidad": "mensual",
        "proveedor_sugerido_id": 99999,
    }, headers=headers_admin)
    assert r.status_code == 404


def test_patch_actualiza(client, headers_admin, db):
    tr = TrabajoRecurrente(consorcio_id=1, nombre="A", descripcion="x",
                            periodicidad=PeriodicidadRecurrente.mensual)
    db.add(tr); db.commit(); db.refresh(tr)
    r = client.patch(f"/trabajos-recurrentes/{tr.id}",
                     json={"nombre": "B"}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "B"


def test_materializar_crea_trabajo(client, headers_admin, db):
    tr = TrabajoRecurrente(consorcio_id=1, nombre="N", descripcion="D",
                            periodicidad=PeriodicidadRecurrente.anual)
    db.add(tr); db.commit(); db.refresh(tr)
    r = client.post(f"/trabajos-recurrentes/{tr.id}/materializar", headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert "N — D" in body["descripcion"]


def test_materializar_inactiva_400(client, headers_admin, db):
    tr = TrabajoRecurrente(consorcio_id=1, nombre="X", descripcion="x",
                            periodicidad=PeriodicidadRecurrente.mensual, activa=False)
    db.add(tr); db.commit(); db.refresh(tr)
    r = client.post(f"/trabajos-recurrentes/{tr.id}/materializar", headers=headers_admin)
    assert r.status_code == 400

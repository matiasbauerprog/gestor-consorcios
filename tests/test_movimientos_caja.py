"""Tests de POST/GET /cajas/{id}/movimientos."""
from datetime import date


def _crear_caja(client, headers, nombre="Caja Mov Test"):
    return client.post(
        "/cajas", json={"nombre": nombre, "tipo": "banco"}, headers=headers
    ).json()


def test_post_ajuste_positivo_suma_al_saldo(client, headers_admin):
    c = _crear_caja(client, headers_admin)
    r = client.post(
        f"/cajas/{c['id']}/movimientos",
        json={"fecha": date.today().isoformat(), "monto": 500, "descripcion": "Ajuste positivo de prueba"},
        headers=headers_admin
    )
    assert r.status_code == 201
    cajas = client.get("/cajas", headers=headers_admin).json()
    nueva = next(x for x in cajas if x["id"] == c["id"])
    assert nueva["saldo_actual"] == 500


def test_post_ajuste_negativo_resta(client, headers_admin):
    c = _crear_caja(client, headers_admin, nombre="Caja Neg")
    r = client.post(
        f"/cajas/{c['id']}/movimientos",
        json={"fecha": date.today().isoformat(), "monto": -200, "descripcion": "Ajuste negativo prueba"},
        headers=headers_admin
    )
    assert r.status_code == 201
    cajas = client.get("/cajas", headers=headers_admin).json()
    nueva = next(x for x in cajas if x["id"] == c["id"])
    assert nueva["saldo_actual"] == -200


def test_ajuste_descripcion_corta_devuelve_400(client, headers_admin):
    c = _crear_caja(client, headers_admin, nombre="Caja Corta")
    r = client.post(
        f"/cajas/{c['id']}/movimientos",
        json={"fecha": date.today().isoformat(), "monto": 100, "descripcion": "abc"},
        headers=headers_admin
    )
    assert r.status_code == 400


def test_ajuste_caja_inexistente_404(client, headers_admin):
    r = client.post(
        "/cajas/9999/movimientos",
        json={"fecha": date.today().isoformat(), "monto": 100, "descripcion": "test ajuste largo"},
        headers=headers_admin
    )
    assert r.status_code == 404


def test_ajuste_caja_inactiva_400(client, headers_admin):
    c = _crear_caja(client, headers_admin, nombre="Caja Inactiva")
    client.patch(f"/cajas/{c['id']}", json={"activa": False}, headers=headers_admin)
    r = client.post(
        f"/cajas/{c['id']}/movimientos",
        json={"fecha": date.today().isoformat(), "monto": 100, "descripcion": "intento ajuste"},
        headers=headers_admin
    )
    assert r.status_code == 400


def test_listar_movimientos_paginado(client, headers_admin):
    c = _crear_caja(client, headers_admin, nombre="Caja Paginada")
    for i in range(5):
        client.post(
            f"/cajas/{c['id']}/movimientos",
            json={"fecha": date.today().isoformat(), "monto": 10*(i+1), "descripcion": f"Ajuste numero {i}"},
            headers=headers_admin
        )
    r = client.get(f"/cajas/{c['id']}/movimientos?limit=3", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_listar_movimientos_depto_403(client, headers_depto_a):
    r = client.get("/cajas/1/movimientos", headers=headers_depto_a)
    assert r.status_code == 403

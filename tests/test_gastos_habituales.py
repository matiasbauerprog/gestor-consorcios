# ---------------------------------------------------------------------------
# GET /gastos-habituales
# ---------------------------------------------------------------------------


def test_listar_habituales_sin_token_devuelve_401(client):
    r = client.get("/gastos-habituales")
    assert r.status_code == 401


def test_listar_habituales_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/gastos-habituales", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_habituales_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/gastos-habituales", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    nombres = {h["nombre"] for h in data}
    assert "Plantilla Test" in nombres


def test_listar_habituales_filtra_por_activa(client, headers_admin):
    # Crear una inactiva.
    creada = client.post(
        "/gastos-habituales",
        json={
            "nombre": "Plantilla Inactiva",
            "rubro": "abonos_y_servicios",
            "clase_prorrateo_id": 500,
            "proveedor_id": 600,
            "concepto": "x",
            "monto": 1000,
            "forma_pago": "transferencia",
        },
        headers=headers_admin,
    ).json()
    client.patch(f"/gastos-habituales/{creada['id']}", json={"activa": False}, headers=headers_admin)

    r = client.get("/gastos-habituales?activa=true", headers=headers_admin)
    assert all(h["activa"] for h in r.json())

    r2 = client.get("/gastos-habituales?activa=false", headers=headers_admin)
    assert all(not h["activa"] for h in r2.json())


# ---------------------------------------------------------------------------
# POST /gastos-habituales
# ---------------------------------------------------------------------------


_NUEVA = {
    "nombre": "Sueldo Encargado",
    "rubro": "sueldos_y_cargas_sociales",
    "clase_prorrateo_id": 500,
    "proveedor_id": 600,
    "concepto": "Sueldo mensual",
    "monto": 800000,
    "forma_pago": "transferencia",
}


def test_crear_habitual_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/gastos-habituales", json=_NUEVA, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "Sueldo Encargado"
    assert body["activa"] is True


def test_crear_habitual_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/gastos-habituales", json=_NUEVA, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_habitual_monto_negativo_devuelve_400(client, headers_admin):
    payload = dict(_NUEVA, monto=-1)
    r = client.post("/gastos-habituales", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_habitual_clase_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_NUEVA, clase_prorrateo_id=9999)
    r = client.post("/gastos-habituales", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_habitual_proveedor_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_NUEVA, proveedor_id=9999)
    r = client.post("/gastos-habituales", json=payload, headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /gastos-habituales/{id}
# ---------------------------------------------------------------------------


def test_obtener_habitual_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/gastos-habituales/9999", headers=headers_admin)
    assert r.status_code == 404


def test_obtener_habitual_existente_devuelve_200(client, headers_admin):
    r = client.get("/gastos-habituales/700", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Plantilla Test"


# ---------------------------------------------------------------------------
# PATCH /gastos-habituales/{id}
# ---------------------------------------------------------------------------


def test_patch_habitual_cambia_nombre(client, headers_admin):
    r = client.patch("/gastos-habituales/700", json={"nombre": "Renombrada"}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Renombrada"


def test_patch_habitual_desactiva(client, headers_admin):
    r = client.patch("/gastos-habituales/700", json={"activa": False}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activa"] is False


def test_patch_habitual_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/gastos-habituales/9999", json={"nombre": "x"}, headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /gastos-habituales/{id}
# ---------------------------------------------------------------------------


def test_delete_habitual_sin_gastos_es_hard_delete(client, headers_admin):
    creada = client.post("/gastos-habituales", json=_NUEVA, headers=headers_admin).json()
    r = client.delete(f"/gastos-habituales/{creada['id']}", headers=headers_admin)
    assert r.status_code == 204

    r2 = client.get(f"/gastos-habituales/{creada['id']}", headers=headers_admin)
    assert r2.status_code == 404


def test_delete_habitual_con_gastos_es_soft_delete(client, headers_admin, db_session):
    from backend.models import Gasto as GastoModel, FormaPago as FP, Rubro as R
    from datetime import date as d
    db_session.add(
        GastoModel(
            periodo="2026-06",
            rubro=R.abonos_y_servicios,
            clase_prorrateo_id=500,
            proveedor_id=600,
            concepto="generado",
            monto=1000,
            forma_pago=FP.transferencia,
            fecha_pago=d(2026, 6, 1),
            gasto_habitual_id=700,
        )
    )
    db_session.commit()

    r = client.delete("/gastos-habituales/700", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activa"] is False

    r2 = client.get("/gastos-habituales/700", headers=headers_admin)
    assert r2.status_code == 200


def test_delete_habitual_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/gastos-habituales/9999", headers=headers_admin)
    assert r.status_code == 404

from datetime import date


_EMPLEADO_NUEVO = {
    "nombre_completo": "Juan Pérez",
    "cuil": "20-12345678-9",
    "categoria": "encargado_permanente_sin_vivienda",
    "fecha_ingreso": "2024-03-01",
    "fecha_egreso": None,
    "sueldo_basico": 800000,
    "proveedor_id": 600,
}


# ---------------------------------------------------------------------------
# GET /empleados
# ---------------------------------------------------------------------------


def test_listar_empleados_sin_token_devuelve_401(client):
    r = client.get("/empleados")
    assert r.status_code == 401


def test_listar_empleados_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/empleados", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_empleados_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/empleados", headers=headers_admin)
    assert r.status_code == 200
    cuils = {e["cuil"] for e in r.json()}
    assert "20-30000000-3" in cuils


def test_listar_empleados_filtra_activos_por_default(client, headers_admin):
    r = client.get("/empleados", headers=headers_admin)
    assert all(e["activo"] for e in r.json())


def test_listar_empleados_inactivos_via_query(client, headers_admin):
    # Desactivar al empleado del seed.
    client.delete("/empleados/900", headers=headers_admin)

    r = client.get("/empleados?activo=false", headers=headers_admin)
    assert any(e["id"] == 900 for e in r.json())


# ---------------------------------------------------------------------------
# POST /empleados
# ---------------------------------------------------------------------------


def test_crear_empleado_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/empleados", json=_EMPLEADO_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["nombre_completo"] == "Juan Pérez"
    assert body["activo"] is True


def test_crear_empleado_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/empleados", json=_EMPLEADO_NUEVO, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_empleado_cuil_duplicado_devuelve_409(client, headers_admin):
    payload = dict(_EMPLEADO_NUEVO, cuil="20-30000000-3")
    r = client.post("/empleados", json=payload, headers=headers_admin)
    assert r.status_code == 409


def test_crear_empleado_cuil_invalido_devuelve_400(client, headers_admin):
    payload = dict(_EMPLEADO_NUEVO, cuil="ABC")
    r = client.post("/empleados", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_empleado_proveedor_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_EMPLEADO_NUEVO, proveedor_id=9999)
    r = client.post("/empleados", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_empleado_sueldo_cero_devuelve_400(client, headers_admin):
    payload = dict(_EMPLEADO_NUEVO, sueldo_basico=0)
    r = client.post("/empleados", json=payload, headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /empleados/{id}
# ---------------------------------------------------------------------------


def test_obtener_empleado_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/empleados/9999", headers=headers_admin)
    assert r.status_code == 404


def test_obtener_empleado_existente_devuelve_200(client, headers_admin):
    r = client.get("/empleados/900", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["cuil"] == "20-30000000-3"


# ---------------------------------------------------------------------------
# PATCH /empleados/{id}
# ---------------------------------------------------------------------------


def test_patch_empleado_actualiza_sueldo(client, headers_admin):
    r = client.patch("/empleados/900", json={"sueldo_basico": 1500000}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["sueldo_basico"] == 1500000


def test_patch_empleado_cuil_en_body_es_ignorado(client, headers_admin):
    r = client.patch(
        "/empleados/900",
        json={"cuil": "99-99999999-9", "sueldo_basico": 1200000},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["cuil"] == "20-30000000-3"


def test_patch_empleado_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/empleados/9999", json={"sueldo_basico": 1}, headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /empleados/{id}
# ---------------------------------------------------------------------------


def test_delete_empleado_sin_liquidaciones_es_hard_delete(client, headers_admin):
    creado = client.post("/empleados", json=_EMPLEADO_NUEVO, headers=headers_admin).json()
    r = client.delete(f"/empleados/{creado['id']}", headers=headers_admin)
    assert r.status_code == 204

    r2 = client.get(f"/empleados/{creado['id']}", headers=headers_admin)
    assert r2.status_code == 404


def test_delete_empleado_con_liquidaciones_es_soft_delete(client, headers_admin, db_session):
    from backend.models import LiquidacionEmpleado as Liq
    db_session.add(Liq(empleado_id=900, periodo="2026-06", sueldo_bruto=1000000))
    db_session.commit()

    r = client.delete("/empleados/900", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False

    r2 = client.get("/empleados/900", headers=headers_admin)
    assert r2.status_code == 200
    assert r2.json()["activo"] is False


def test_delete_empleado_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/empleados/9999", headers=headers_admin)
    assert r.status_code == 404

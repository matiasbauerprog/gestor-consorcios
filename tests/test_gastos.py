from datetime import date


_GASTO_VALIDO = {
    "periodo": "2026-06",
    "rubro": "servicios_publicos",
    "clase_prorrateo_id": 500,
    "departamento_id": None,
    "proveedor_id": 600,
    "concepto": "Agua AYSA",
    "monto": 30000,
    "forma_pago": "transferencia",
    "fecha_pago": "2026-06-15",
}


# ---------------------------------------------------------------------------
# GET /gastos
# ---------------------------------------------------------------------------


def test_listar_gastos_sin_token_devuelve_401(client):
    r = client.get("/gastos")
    assert r.status_code == 401


def test_listar_gastos_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/gastos", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_gastos_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/gastos", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    conceptos = {g["concepto"] for g in data}
    assert "Luz pasillos" in conceptos


def test_listar_gastos_filtra_periodo(client, headers_admin):
    r = client.get("/gastos?periodo=2026-06", headers=headers_admin)
    assert r.status_code == 200
    assert all(g["periodo"] == "2026-06" for g in r.json())


def test_listar_gastos_filtra_rubro(client, headers_admin):
    r = client.get("/gastos?rubro=servicios_publicos", headers=headers_admin)
    assert r.status_code == 200
    assert all(g["rubro"] == "servicios_publicos" for g in r.json())


def test_listar_gastos_filtra_clase(client, headers_admin):
    r = client.get("/gastos?clase_prorrateo_id=500", headers=headers_admin)
    assert r.status_code == 200
    assert all(g["clase_prorrateo_id"] == 500 for g in r.json())


def test_listar_gastos_filtra_proveedor(client, headers_admin):
    r = client.get("/gastos?proveedor_id=600", headers=headers_admin)
    assert r.status_code == 200
    assert all(g["proveedor_id"] == 600 for g in r.json())


# ---------------------------------------------------------------------------
# POST /gastos — happy paths y validaciones
# ---------------------------------------------------------------------------


def test_crear_gasto_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/gastos", json=_GASTO_VALIDO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["concepto"] == "Agua AYSA"
    assert body["monto"] == 30000
    assert body["gasto_habitual_id"] is None


def test_crear_gasto_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/gastos", json=_GASTO_VALIDO, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_gasto_clase_y_depto_juntos_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, clase_prorrateo_id=500, departamento_id=1)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_ni_clase_ni_depto_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, clase_prorrateo_id=None, departamento_id=None)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_particular_a_depto_es_201(client, headers_admin):
    payload = dict(_GASTO_VALIDO, clase_prorrateo_id=None, departamento_id=1)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["departamento_id"] == 1
    assert r.json()["clase_prorrateo_id"] is None


def test_crear_gasto_monto_cero_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, monto=0)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_cuota_actual_sin_total_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, cuota_actual=1)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_cuota_actual_mayor_total_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, cuota_actual=5, cuota_total=3)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_periodo_invalido_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, periodo="2026-13")
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_clase_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_GASTO_VALIDO, clase_prorrateo_id=9999)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_gasto_depto_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_GASTO_VALIDO, clase_prorrateo_id=None, departamento_id=9999)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_gasto_proveedor_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_GASTO_VALIDO, proveedor_id=9999)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /gastos/{id}
# ---------------------------------------------------------------------------


def test_obtener_gasto_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/gastos/9999", headers=headers_admin)
    assert r.status_code == 404


def test_obtener_gasto_existente_devuelve_200(client, headers_admin):
    r = client.get("/gastos/800", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["concepto"] == "Luz pasillos"


# ---------------------------------------------------------------------------
# PATCH /gastos/{id}
# ---------------------------------------------------------------------------


def test_patch_gasto_cambia_monto(client, headers_admin):
    r = client.patch("/gastos/800", json={"monto": 20000}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["monto"] == 20000


def test_patch_gasto_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/gastos/9999", json={"monto": 1}, headers=headers_admin)
    assert r.status_code == 404


def test_patch_gasto_monto_negativo_devuelve_400(client, headers_admin):
    r = client.patch("/gastos/800", json={"monto": -1}, headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /gastos/{id}
# ---------------------------------------------------------------------------


def test_delete_gasto_es_hard_delete(client, headers_admin):
    r = client.delete("/gastos/800", headers=headers_admin)
    assert r.status_code == 204

    r2 = client.get("/gastos/800", headers=headers_admin)
    assert r2.status_code == 404


def test_delete_gasto_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/gastos/9999", headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /gastos/plan-cuotas
# ---------------------------------------------------------------------------


_PLAN_VALIDO = {
    "periodo": "2026-06",
    "rubro": "abonos_y_servicios",
    "clase_prorrateo_id": 500,
    "departamento_id": None,
    "proveedor_id": 600,
    "concepto": "Seguro anual",
    "monto": 50000,
    "forma_pago": "transferencia",
    "fecha_pago": "2026-06-10",
    "cuota_total": 3,
}


def test_plan_cuotas_sin_token_devuelve_401(client):
    r = client.post("/gastos/plan-cuotas", json=_PLAN_VALIDO)
    assert r.status_code == 401


def test_plan_cuotas_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/gastos/plan-cuotas", json=_PLAN_VALIDO, headers=headers_depto_a)
    assert r.status_code == 403


def test_plan_cuotas_crea_n_gastos_consecutivos(client, headers_admin):
    r = client.post("/gastos/plan-cuotas", json=_PLAN_VALIDO, headers=headers_admin)
    assert r.status_code == 201
    gastos = r.json()
    assert len(gastos) == 3

    # Períodos consecutivos.
    assert [g["periodo"] for g in gastos] == ["2026-06", "2026-07", "2026-08"]

    # Cuotas numeradas correctamente.
    assert [g["cuota_actual"] for g in gastos] == [1, 2, 3]
    assert all(g["cuota_total"] == 3 for g in gastos)

    # Fechas de pago desplazadas 1 mes.
    assert [g["fecha_pago"] for g in gastos] == ["2026-06-10", "2026-07-10", "2026-08-10"]

    # Mismo concepto, monto, proveedor.
    assert all(g["concepto"] == "Seguro anual" for g in gastos)
    assert all(g["monto"] == 50000 for g in gastos)


def test_plan_cuotas_total_uno_devuelve_400(client, headers_admin):
    payload = dict(_PLAN_VALIDO, cuota_total=1)
    r = client.post("/gastos/plan-cuotas", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_plan_cuotas_clase_y_depto_juntos_devuelve_400(client, headers_admin):
    payload = dict(_PLAN_VALIDO, clase_prorrateo_id=500, departamento_id=1)
    r = client.post("/gastos/plan-cuotas", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_plan_cuotas_proveedor_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_PLAN_VALIDO, proveedor_id=9999)
    r = client.post("/gastos/plan-cuotas", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_plan_cuotas_cruza_anio(client, headers_admin):
    # Empezando en noviembre, 3 cuotas → nov, dic, ene del año siguiente.
    payload = dict(_PLAN_VALIDO, periodo="2026-11", fecha_pago="2026-11-15", cuota_total=3)
    r = client.post("/gastos/plan-cuotas", json=payload, headers=headers_admin)
    assert r.status_code == 201
    gastos = r.json()
    assert [g["periodo"] for g in gastos] == ["2026-11", "2026-12", "2027-01"]
    assert [g["fecha_pago"] for g in gastos] == ["2026-11-15", "2026-12-15", "2027-01-15"]


# ---------------------------------------------------------------------------
# POST /gastos/cargar-habituales
# ---------------------------------------------------------------------------


def test_cargar_habituales_sin_token_devuelve_401(client):
    r = client.post("/gastos/cargar-habituales", json={"periodo": "2026-07"})
    assert r.status_code == 401


def test_cargar_habituales_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-07"},
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_cargar_habituales_genera_un_gasto_por_plantilla_activa(client, headers_admin):
    # En el seed hay 1 plantilla activa (id=700).
    r = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-07"},
        headers=headers_admin,
    )
    assert r.status_code == 201
    generados = r.json()
    assert len(generados) == 1
    assert generados[0]["periodo"] == "2026-07"
    assert generados[0]["gasto_habitual_id"] == 700
    assert generados[0]["concepto"] == "Servicio mensual de prueba"
    assert generados[0]["monto"] == 10000


def test_cargar_habituales_es_idempotente(client, headers_admin):
    # Primera llamada genera 1.
    r1 = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-07"},
        headers=headers_admin,
    )
    assert len(r1.json()) == 1

    # Segunda llamada no genera nada (ya existe).
    r2 = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-07"},
        headers=headers_admin,
    )
    assert r2.status_code == 201
    assert r2.json() == []


def test_cargar_habituales_ignora_plantillas_inactivas(client, headers_admin):
    # Desactivar la plantilla 700.
    client.patch("/gastos-habituales/700", json={"activa": False}, headers=headers_admin)

    r = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-08"},
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json() == []


def test_cargar_habituales_periodo_invalido_devuelve_400(client, headers_admin):
    r = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "abc"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_cargar_habituales_usa_fecha_primer_dia_del_periodo(client, headers_admin):
    r = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-07"},
        headers=headers_admin,
    )
    generado = r.json()[0]
    assert generado["fecha_pago"] == "2026-07-01"

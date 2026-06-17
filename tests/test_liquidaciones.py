from datetime import date


def _payload_basico():
    """Liquidación con 2 haberes simples y los conceptos del seed."""
    return {
        "empleado_id": 900,
        "periodo": "2026-07",
        "haberes": [
            {"haber_id": 940, "valor_override": None, "cantidad": None},  # Básico 100% → $1.000.000
            {"haber_id": 941, "valor_override": 12.0, "cantidad": None},  # Antigüedad 12% → $120.000
        ],
        "haberes_ad_hoc": [],
    }


# ---------------------------------------------------------------------------
# GET /liquidaciones
# ---------------------------------------------------------------------------


def test_listar_liquidaciones_sin_token_devuelve_401(client):
    r = client.get("/liquidaciones")
    assert r.status_code == 401


def test_listar_liquidaciones_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/liquidaciones", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_liquidaciones_vacio_inicialmente(client, headers_admin):
    # Filtrar por período 2026-07 (el seed tiene periodo="2025-01"), debe estar vacío.
    r = client.get("/liquidaciones?periodo=2026-07", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# POST /liquidaciones — happy path
# ---------------------------------------------------------------------------


def test_crear_liquidacion_calcula_bruto_correctamente(client, headers_admin):
    # Empleado seed tiene sueldo_basico=1.000.000.
    # Básico = 100% × 1.000.000 = 1.000.000
    # Antigüedad = 12% × 1.000.000 = 120.000
    # Bruto = 1.120.000
    r = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["sueldo_bruto"] == 1120000
    assert len(body["haberes"]) == 2
    assert body["haberes"][0]["nombre"] == "Básico Test"
    assert body["haberes"][0]["monto"] == 1000000
    assert body["haberes"][1]["nombre"] == "Antigüedad Test"
    assert body["haberes"][1]["monto"] == 120000


def test_crear_liquidacion_aplica_conceptos_sobre_bruto(client, headers_admin):
    r = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)
    body = r.json()
    # Conceptos seed: Jubilación 11% descuento + AFIP 16% contribución.
    # Sobre bruto 1.120.000: jubilación = 123.200, AFIP = 179.200.
    detalle = {d["concepto_nombre"]: d for d in body["detalle"]}
    assert detalle["Jubilación Test"]["monto"] == 123200
    assert detalle["Jubilación Test"]["concepto_tipo"] == "descuento"
    assert detalle["AFIP Test"]["monto"] == 179200
    assert detalle["AFIP Test"]["concepto_tipo"] == "contribucion"


def test_crear_liquidacion_haberes_ad_hoc(client, headers_admin):
    payload = _payload_basico()
    payload["haberes_ad_hoc"] = [{"nombre": "SAC", "monto": 500000}]
    r = client.post("/liquidaciones", json=payload, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    # Bruto = 1.000.000 + 120.000 + 500.000 = 1.620.000.
    assert body["sueldo_bruto"] == 1620000
    nombres = {h["nombre"] for h in body["haberes"]}
    assert "SAC" in nombres


def test_crear_liquidacion_haber_cantidad_x_valor(client, headers_admin):
    # Crear un haber de tipo cantidad_x_valor.
    nuevo_haber = client.post(
        "/haberes",
        json={"nombre": "HE 50 Test", "tipo": "cantidad_x_valor", "valor_default": 5000, "orden": 5},
        headers=headers_admin,
    ).json()

    payload = {
        "empleado_id": 900,
        "periodo": "2026-07",
        "haberes": [
            {"haber_id": 940, "valor_override": None, "cantidad": None},  # Básico
            {"haber_id": nuevo_haber["id"], "valor_override": None, "cantidad": 10},  # 10 × 5000
        ],
        "haberes_ad_hoc": [],
    }
    r = client.post("/liquidaciones", json=payload, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    # Básico 1M + HE 10*5000 = 1.050.000.
    assert body["sueldo_bruto"] == 1050000


def test_crear_liquidacion_genera_gastos_asociados(client, headers_admin):
    r = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)
    liq_id = r.json()["id"]

    rg = client.get(f"/gastos?gasto_habitual_id=&periodo=2026-07", headers=headers_admin)
    # Filtramos manualmente por liquidacion_id mirando todos los gastos del período.
    todos = client.get("/gastos?periodo=2026-07", headers=headers_admin).json()
    gastos_liq = [g for g in todos if g.get("liquidacion_id") == liq_id]
    assert len(gastos_liq) >= 2  # sueldo neto + al menos 1 por proveedor
    assert all(g["rubro"] == "sueldos_y_cargas_sociales" for g in gastos_liq)


def test_crear_liquidacion_duplicada_devuelve_409(client, headers_admin):
    client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)
    r = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)
    assert r.status_code == 409


def test_crear_liquidacion_empleado_inexistente_devuelve_404(client, headers_admin):
    payload = _payload_basico()
    payload["empleado_id"] = 9999
    r = client.post("/liquidaciones", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_liquidacion_haber_inexistente_devuelve_404(client, headers_admin):
    payload = _payload_basico()
    payload["haberes"][0]["haber_id"] = 9999
    r = client.post("/liquidaciones", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_liquidacion_periodo_invalido_devuelve_400(client, headers_admin):
    payload = _payload_basico()
    payload["periodo"] = "abc"
    r = client.post("/liquidaciones", json=payload, headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Snapshot: cambiar % de concepto NO afecta liquidaciones pasadas
# ---------------------------------------------------------------------------


def test_snapshot_concepto_no_se_modifica_retroactivamente(client, headers_admin):
    client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)

    # Cambiar el % de Jubilación de 11 a 50.
    client.patch("/conceptos-liquidacion/950", json={"porcentaje": 50.0}, headers=headers_admin)

    # La liquidación anterior conserva el % original.
    todas = client.get("/liquidaciones", headers=headers_admin).json()
    detalle = {d["concepto_nombre"]: d for d in todas[0]["detalle"]}
    assert detalle["Jubilación Test"]["porcentaje_aplicado"] == 11.0


# ---------------------------------------------------------------------------
# PATCH /liquidaciones/{id}
# ---------------------------------------------------------------------------


def test_patch_liquidacion_recalcula_bruto(client, headers_admin):
    creada = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin).json()

    # Cambiar antigüedad de 12% a 20%.
    nuevo = {
        "haberes": [
            {"haber_id": 940, "valor_override": None, "cantidad": None},
            {"haber_id": 941, "valor_override": 20.0, "cantidad": None},
        ],
        "haberes_ad_hoc": [],
    }
    r = client.patch(f"/liquidaciones/{creada['id']}", json=nuevo, headers=headers_admin)
    assert r.status_code == 200
    # Bruto = 1.000.000 + 200.000 = 1.200.000.
    assert r.json()["sueldo_bruto"] == 1200000


def test_patch_liquidacion_regenera_gastos(client, headers_admin):
    creada = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin).json()

    # Contar gastos pre-PATCH.
    pre = client.get("/gastos?periodo=2026-07", headers=headers_admin).json()
    pre_count = len([g for g in pre if g.get("liquidacion_id") == creada["id"]])
    assert pre_count > 0

    # PATCH cambia los haberes.
    nuevo = {
        "haberes": [
            {"haber_id": 940, "valor_override": None, "cantidad": None},
            {"haber_id": 941, "valor_override": 50.0, "cantidad": None},
        ],
        "haberes_ad_hoc": [],
    }
    client.patch(f"/liquidaciones/{creada['id']}", json=nuevo, headers=headers_admin)

    # Verificar que los gastos siguen existiendo (regenerados, mismo total de filas).
    post = client.get("/gastos?periodo=2026-07", headers=headers_admin).json()
    post_count = len([g for g in post if g.get("liquidacion_id") == creada["id"]])
    assert post_count == pre_count


# ---------------------------------------------------------------------------
# DELETE /liquidaciones/{id}
# ---------------------------------------------------------------------------


def test_delete_liquidacion_cascada_borra_haberes_detalle_y_gastos(client, headers_admin):
    creada = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin).json()

    r = client.delete(f"/liquidaciones/{creada['id']}", headers=headers_admin)
    assert r.status_code == 204

    # Liquidación no existe.
    r2 = client.get(f"/liquidaciones/{creada['id']}", headers=headers_admin)
    assert r2.status_code == 404

    # Gastos asociados ya no aparecen con ese liquidacion_id.
    todos = client.get("/gastos?periodo=2026-07", headers=headers_admin).json()
    assert not any(g.get("liquidacion_id") == creada["id"] for g in todos)


def test_delete_liquidacion_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/liquidaciones/9999", headers=headers_admin)
    assert r.status_code == 404

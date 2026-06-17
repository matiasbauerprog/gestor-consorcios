# ---------------------------------------------------------------------------
# Filtro departamento_id (Task 5)
# ---------------------------------------------------------------------------


def test_listar_expensas_admin_filtra_por_departamento(client, headers_admin):
    r = client.get("/expensas?departamento_id=1", headers=headers_admin)
    assert r.status_code == 200
    expensas = r.json()
    assert len(expensas) > 0
    assert all(e["departamento_id"] == 1 for e in expensas)


def test_listar_expensas_admin_filtra_por_departamento_inexistente_devuelve_lista_vacia(
    client, headers_admin
):
    r = client.get("/expensas?departamento_id=99999", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


def test_listar_expensas_departamento_ignora_query_de_otro_depto(client, headers_depto_a):
    # Depto A intenta pedir las del depto B; el backend debe seguir devolviendo
    # solo las de A (ignorar el query param).
    r = client.get("/expensas?departamento_id=2", headers=headers_depto_a)
    assert r.status_code == 200
    expensas = r.json()
    assert all(e["departamento_id"] == 1 for e in expensas)


# ---------------------------------------------------------------------------
# Estado calculado FIFO (Task 3.5)
# ---------------------------------------------------------------------------


def test_listar_expensas_devuelve_estado_calculado(client, headers_depto_a):
    r = client.get("/expensas", headers=headers_depto_a)
    assert r.status_code == 200
    for e in r.json():
        assert "estado_calculado" in e
        assert e["estado_calculado"] in ("pendiente", "parcial", "pagada", "vencida")
        assert "monto_pendiente" in e
        assert e["monto_pendiente"] >= 0


def test_listar_expensas_no_devuelve_estado_persistido(client, headers_admin):
    r = client.get("/expensas", headers=headers_admin)
    assert r.status_code == 200
    for e in r.json():
        assert "estado" not in e
        assert "ultimo_comprobante" not in e


# ---------------------------------------------------------------------------
# POST genera MovimientoCuenta automáticamente
# ---------------------------------------------------------------------------


def test_crear_expensa_genera_movimiento(client, headers_admin, headers_depto_a):
    r = client.post(
        "/expensas",
        json={
            "departamento_id": 1,
            "periodo": "2026-08",
            "monto": 100000,
            "fecha_vencimiento": "2026-09-10",
        },
        headers=headers_admin,
    )
    assert r.status_code == 201

    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    assert r.status_code == 200
    movs = r.json()["movimientos"]
    assert any(
        m["tipo"] == "expensa_emitida" and m["monto"] == 100000
        for m in movs
    )


# ---------------------------------------------------------------------------
# DELETE expensa (admin)
# ---------------------------------------------------------------------------


def test_delete_expensa_sin_pagos_204(client, headers_admin):
    r = client.post(
        "/expensas",
        json={
            "departamento_id": 1,
            "periodo": "2026-07",
            "monto": 50000,
            "fecha_vencimiento": "2026-08-10",
        },
        headers=headers_admin,
    )
    assert r.status_code == 201
    expensa_id = r.json()["id"]

    r = client.delete(f"/expensas/{expensa_id}", headers=headers_admin)
    assert r.status_code == 204


def test_delete_expensa_inexistente_404(client, headers_admin):
    r = client.delete("/expensas/99999", headers=headers_admin)
    assert r.status_code == 404


def test_delete_expensa_depto_403(client, headers_depto_a):
    r = client.delete("/expensas/100", headers=headers_depto_a)
    assert r.status_code == 403


def test_delete_expensa_con_pagos_409(client, headers_admin, headers_depto_a):
    # depto_a presenta y admin aprueba un comprobante → genera movimiento pago_recibido
    # → FIFO aplica ese pago a la expensa 100 (la más vieja del depto_a).
    files = {"archivo": ("recibo.pdf", b"%PDF-1.4 test", "application/pdf")}
    r = client.post(
        "/comprobantes",
        data={"fecha_pago": "2026-06-05", "monto": "85000"},
        files=files,
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    comp_id = r.json()["id"]

    r = client.patch(
        f"/comprobantes/{comp_id}",
        json={"estado": "aprobado"},
        headers=headers_admin,
    )
    assert r.status_code == 200

    # Ahora la expensa 100 tiene pago aplicado → DELETE debe dar 409.
    r = client.delete("/expensas/100", headers=headers_admin)
    assert r.status_code == 409
    assert "pago" in r.json()["detail"].lower()

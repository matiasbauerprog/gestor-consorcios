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
            "monto_primer_vencimiento": 100000,
            "fecha_primer_vencimiento": "2026-09-10",
            "monto_segundo_vencimiento": 107000,
            "fecha_segundo_vencimiento": "2026-09-20",
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
            "monto_primer_vencimiento": 50000,
            "fecha_primer_vencimiento": "2026-08-10",
            "monto_segundo_vencimiento": 53500,
            "fecha_segundo_vencimiento": "2026-08-20",
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


# ---------------------------------------------------------------------------
# Desglose de monto exigible e interés acumulado (Task 4)
# ---------------------------------------------------------------------------


def test_expensa_out_expone_exigible_e_interes(client, headers_admin):
    r = client.get("/expensas", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body, "el seed debe dejar al menos una expensa"
    assert "monto_exigible" in body[0]
    assert "interes_acumulado" in body[0]


# ---------------------------------------------------------------------------
# Devengamiento perezoso en las lecturas de expensas
# ---------------------------------------------------------------------------


def _expensa_vencida_impaga(db_session, expensa_id=170):
    """Expensa con 1er vencimiento pasado y 2do futuro, sin pagos.

    El 2do vencimiento a futuro deja el interés punitorio en cero, así que el
    pendiente es exactamente 1er vencimiento + recargo.
    """
    from datetime import date, timedelta

    from backend.models import Expensa, MovimientoCuenta, TipoMovimiento

    hoy = date.today()
    db_session.add(Expensa(
        id=expensa_id, consorcio_id=1, departamento_id=1, periodo="2026-03",
        monto_primer_vencimiento=1000.0,
        fecha_primer_vencimiento=hoy - timedelta(days=5),
        monto_segundo_vencimiento=1070.0,
        fecha_segundo_vencimiento=hoy + timedelta(days=5),
        saldo_anterior=0.0,
    ))
    db_session.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=1, fecha=hoy - timedelta(days=25),
        tipo=TipoMovimiento.expensa_emitida, descripcion="Expensa 2026-03",
        monto=1000.0, expensa_id=expensa_id,
    ))
    db_session.commit()
    return expensa_id


def _recargos_de(db_session, expensa_id):
    from backend.models import MovimientoCuenta, TipoMovimiento

    return (
        db_session.query(MovimientoCuenta)
        .filter(
            MovimientoCuenta.expensa_id == expensa_id,
            MovimientoCuenta.tipo == TipoMovimiento.recargo,
        )
        .all()
    )


def test_listar_expensas_devenga_el_recargo_antes_de_informar(
    client, headers_depto_a, db_session
):
    """Regresión: `GET /expensas` calculaba la cuenta sin devengar. El exigible
    sale del recargo asentado, así que sin devengar la pantalla que mira el
    departamento informaba 1000 en vez de 1070."""
    expensa_id = _expensa_vencida_impaga(db_session)
    assert _recargos_de(db_session, expensa_id) == []

    r = client.get("/expensas", headers=headers_depto_a)
    assert r.status_code == 200
    e = next(x for x in r.json() if x["id"] == expensa_id)

    assert e["monto_exigible"] == 1070.0
    assert e["monto_pendiente"] == 1070.0
    assert len(_recargos_de(db_session, expensa_id)) == 1


def test_obtener_expensa_devenga_el_recargo_antes_de_informar(
    client, headers_depto_a, db_session
):
    expensa_id = _expensa_vencida_impaga(db_session, expensa_id=171)
    assert _recargos_de(db_session, expensa_id) == []

    r = client.get(f"/expensas/{expensa_id}", headers=headers_depto_a)
    assert r.status_code == 200
    assert r.json()["monto_exigible"] == 1070.0
    assert len(_recargos_de(db_session, expensa_id)) == 1


def test_listar_expensas_no_devenga_de_una_pagada_en_termino(
    client, headers_depto_a, db_session
):
    """La contracara: al que pagó a tiempo no le aparece ningún recargo."""
    from datetime import date, timedelta

    from backend.models import MovimientoCuenta, TipoMovimiento

    expensa_id = _expensa_vencida_impaga(db_session, expensa_id=172)
    hoy = date.today()
    db_session.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=1, fecha=hoy - timedelta(days=20),
        tipo=TipoMovimiento.pago_recibido, descripcion="Pago en término",
        monto=1000.0,
    ))
    db_session.commit()

    r = client.get("/expensas", headers=headers_depto_a)
    assert r.status_code == 200
    e = next(x for x in r.json() if x["id"] == expensa_id)

    assert e["monto_exigible"] == 1000.0
    assert _recargos_de(db_session, expensa_id) == []

"""Tests del router de movimientos (cuenta corriente y notas)."""


# ---------------------------------------------------------------------------
# GET /movimientos/mi-cuenta
# ---------------------------------------------------------------------------


def test_get_mi_cuenta_sin_token_401(client):
    r = client.get("/movimientos/mi-cuenta")
    assert r.status_code == 401


def test_get_mi_cuenta_admin_403(client, headers_admin):
    r = client.get("/movimientos/mi-cuenta", headers=headers_admin)
    assert r.status_code == 403


def test_get_mi_cuenta_representante_403(client, headers_representante):
    r = client.get("/movimientos/mi-cuenta", headers=headers_representante)
    assert r.status_code == 403


def test_get_mi_cuenta_depto_200(client, headers_depto_a):
    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    assert r.status_code == 200
    body = r.json()
    assert body["departamento_id"] == 1
    # El seed crea un movimiento expensa_emitida de 85000 para depto_a → saldo = 85000.
    assert body["saldo_total"] == 85000.0
    assert isinstance(body["movimientos"], list)
    assert len(body["movimientos"]) >= 1
    assert all(m["departamento_id"] == 1 for m in body["movimientos"])


def test_mi_cuenta_filtra_por_fecha(client, headers_admin, headers_depto_a):
    # Crear nota con fecha vieja vía endpoint admin
    r = client.post(
        "/movimientos/nota",
        json={
            "departamento_id": 1,
            "tipo": "nota_credito",
            "monto": 1,
            "descripcion": "vieja",
            "fecha": "2020-01-01",
        },
        headers=headers_admin,
    )
    assert r.status_code == 201

    r = client.get("/movimientos/mi-cuenta?desde=2026-01-01", headers=headers_depto_a)
    assert r.status_code == 200
    movs = r.json()["movimientos"]
    assert all(m["fecha"] >= "2026-01-01" for m in movs)


# ---------------------------------------------------------------------------
# GET /departamentos/{departamento_id}/cuenta
# ---------------------------------------------------------------------------


def test_get_cuenta_departamento_admin_200(client, headers_admin):
    r = client.get("/departamentos/1/cuenta", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["departamento_id"] == 1


def test_get_cuenta_departamento_depto_403(client, headers_depto_a):
    r = client.get("/departamentos/2/cuenta", headers=headers_depto_a)
    assert r.status_code == 403


def test_get_cuenta_departamento_representante_403(client, headers_representante):
    r = client.get("/departamentos/1/cuenta", headers=headers_representante)
    assert r.status_code == 403


def test_get_cuenta_departamento_inexistente_404(client, headers_admin):
    r = client.get("/departamentos/9999/cuenta", headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /movimientos/nota
# ---------------------------------------------------------------------------


def test_post_nota_credito_admin_201(client, headers_admin, headers_depto_a):
    r = client.post(
        "/movimientos/nota",
        json={
            "departamento_id": 1,
            "tipo": "nota_credito",
            "monto": 500,
            "descripcion": "Bonificación verano",
        },
        headers=headers_admin,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["tipo"] == "nota_credito"
    assert body["monto"] == 500
    assert body["departamento_id"] == 1

    # Verificar que aparece en la cuenta del depto.
    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    movs = r.json()["movimientos"]
    assert any(m["tipo"] == "nota_credito" and m["monto"] == 500 for m in movs)


def test_post_nota_debito_admin_201(client, headers_admin):
    r = client.post(
        "/movimientos/nota",
        json={
            "departamento_id": 1,
            "tipo": "nota_debito",
            "monto": 100,
            "descripcion": "Recargo administrativo",
        },
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json()["tipo"] == "nota_debito"


def test_post_nota_monto_invalido_400(client, headers_admin):
    r = client.post(
        "/movimientos/nota",
        json={
            "departamento_id": 1,
            "tipo": "nota_credito",
            "monto": 0,
            "descripcion": "x",
        },
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_post_nota_tipo_invalido_400(client, headers_admin):
    r = client.post(
        "/movimientos/nota",
        json={
            "departamento_id": 1,
            "tipo": "pago_recibido",
            "monto": 100,
            "descripcion": "x",
        },
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_post_nota_depto_403(client, headers_depto_a):
    r = client.post(
        "/movimientos/nota",
        json={
            "departamento_id": 1,
            "tipo": "nota_credito",
            "monto": 100,
            "descripcion": "x",
        },
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_post_nota_depto_inexistente_404(client, headers_admin):
    r = client.post(
        "/movimientos/nota",
        json={
            "departamento_id": 9999,
            "tipo": "nota_credito",
            "monto": 100,
            "descripcion": "x",
        },
        headers=headers_admin,
    )
    assert r.status_code == 404

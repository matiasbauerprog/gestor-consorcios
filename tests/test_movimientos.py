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


# ---------------------------------------------------------------------------
# GET /movimientos/cuentas — listado consolidado saldo por depto
# ---------------------------------------------------------------------------


def test_get_cuentas_sin_token_401(client):
    r = client.get("/movimientos/cuentas")
    assert r.status_code == 401


def test_get_cuentas_como_departamento_403(client, headers_depto_a):
    r = client.get("/movimientos/cuentas", headers=headers_depto_a)
    assert r.status_code == 403


def test_get_cuentas_como_representante_403(client, headers_representante):
    r = client.get("/movimientos/cuentas", headers=headers_representante)
    assert r.status_code == 403


def test_get_cuentas_admin_devuelve_todos_los_deptos_del_consorcio(client, headers_admin):
    r = client.get("/movimientos/cuentas", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    # Seed: 2 deptos en consorcio 1 (UF-1A, UF-2B)
    assert len(data) == 2
    codigos = {item["codigo"] for item in data}
    assert codigos == {"UF-1A", "UF-2B"}
    for item in data:
        assert "departamento_id" in item
        assert "codigo" in item
        assert "ubicacion" in item
        assert "saldo_total" in item
        assert isinstance(item["saldo_total"], (int, float))


def test_get_cuentas_saldo_refleja_movimientos(client, headers_admin, db_session):
    # El seed carga una expensa emitida por 85000 al depto 1 (UF-1A) → debe estar en saldo
    r = client.get("/movimientos/cuentas", headers=headers_admin)
    assert r.status_code == 200
    por_codigo = {item["codigo"]: item for item in r.json()}
    assert por_codigo["UF-1A"]["saldo_total"] == 85000.0


def test_get_cuentas_incluye_flag_en_mora(client, headers_admin, db_session):
    from backend.models import Expensa
    from datetime import date, timedelta

    r = client.get("/movimientos/cuentas", headers=headers_admin)
    assert r.status_code == 200
    por_codigo = {item["codigo"]: item for item in r.json()}
    # El seed pone las expensas con segundo vencimiento en VENC_2, siempre
    # futuro respecto de hoy. No debería estar en mora aunque tenga saldo.
    assert por_codigo["UF-1A"]["saldo_total"] > 0
    assert por_codigo["UF-1A"]["en_mora"] is False


def test_get_cuentas_en_mora_true_si_segundo_venc_paso_y_debe(client, headers_admin, db_session):
    from backend.models import Expensa
    from datetime import date, timedelta
    # Meto una expensa vencida hace tiempo para el depto 1
    e = Expensa(
        consorcio_id=1,
        departamento_id=1,
        periodo="2025-01",
        monto_primer_vencimiento=50000.0,
        fecha_primer_vencimiento=date(2025, 1, 10),
        monto_segundo_vencimiento=53000.0,
        fecha_segundo_vencimiento=date(2025, 1, 20),  # ya venció
        saldo_anterior=0.0,
    )
    db_session.add(e)
    db_session.commit()
    r = client.get("/movimientos/cuentas", headers=headers_admin)
    assert r.status_code == 200
    por_codigo = {item["codigo"]: item for item in r.json()}
    # El depto UF-1A ahora tiene saldo positivo + expensa con 2do venc pasado
    assert por_codigo["UF-1A"]["en_mora"] is True


def test_get_cuentas_en_mora_false_si_saldo_es_cero(client, headers_admin):
    r = client.get("/movimientos/cuentas", headers=headers_admin)
    por_codigo = {item["codigo"]: item for item in r.json()}
    # UF-2B tiene saldo 92000 pero segundo venc aún no pasó → no está en mora
    assert por_codigo["UF-2B"]["en_mora"] is False


def test_get_cuentas_scope_multitenant(client, dos_consorcios):
    # Admin de c2 solo ve el depto de c2 (UF-1A del c2), no los de c1.
    r = client.get(
        "/movimientos/cuentas",
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["codigo"] == "UF-1A"
    # Cross-check: solo el depto 3 del c2 debe estar
    assert data[0]["departamento_id"] == 3


# ---------------------------------------------------------------------------
# Devengamiento perezoso del recargo por mora al leer la cuenta
# ---------------------------------------------------------------------------
#
# El seed deja al depto 1 con la expensa 100 (85000, primer venc futuro) y su
# movimiento `expensa_emitida`. Estos tests le agregan una expensa cuyo PRIMER
# vencimiento ya pasó pero cuyo SEGUNDO todavía no: así rige el monto con
# recargo sin que se mezclen intereses punitorios (que sólo corren pasado el
# segundo vencimiento) y la aritmética queda limpia.

_VENCIDA_MONTO_1 = 50000.0
_VENCIDA_MONTO_2 = 53500.0          # 50000 + 7% de recargo
_RECARGO_ESPERADO = 3500.0
_SALDO_CON_RECARGO = 85000.0 + _VENCIDA_MONTO_2   # 138500.0


def _expensa_primer_venc_pasado(db_session):
    """Agrega al depto 1 una expensa con el primer vencimiento ya pasado.

    Devuelve la fecha del primer vencimiento, que es cómo debe quedar fechado
    el movimiento de recargo.
    """
    from datetime import date, timedelta

    from backend.models import Expensa, MovimientoCuenta, TipoMovimiento

    hoy = date.today()
    venc_1 = hoy - timedelta(days=5)
    venc_2 = hoy + timedelta(days=5)

    db_session.add(Expensa(
        id=150,
        consorcio_id=1,
        departamento_id=1,
        periodo="2026-04",
        monto_primer_vencimiento=_VENCIDA_MONTO_1,
        fecha_primer_vencimiento=venc_1,
        monto_segundo_vencimiento=_VENCIDA_MONTO_2,
        fecha_segundo_vencimiento=venc_2,
        saldo_anterior=0.0,
    ))
    db_session.add(MovimientoCuenta(
        consorcio_id=1,
        departamento_id=1,
        fecha=venc_1 - timedelta(days=20),
        tipo=TipoMovimiento.expensa_emitida,
        descripcion="Expensa 2026-04",
        monto=_VENCIDA_MONTO_1,
        expensa_id=150,
    ))
    db_session.commit()
    return venc_1


def test_mi_cuenta_devenga_recargo_y_el_saldo_iguala_los_pendientes(
    client, headers_depto_a, db_session
):
    _expensa_primer_venc_pasado(db_session)

    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    assert r.status_code == 200
    saldo = r.json()["saldo_total"]

    r = client.get("/expensas", headers=headers_depto_a)
    assert r.status_code == 200
    suma_pendientes = round(sum(e["monto_pendiente"] for e in r.json()), 2)

    assert saldo == _SALDO_CON_RECARGO
    assert saldo == suma_pendientes


def test_mi_cuenta_lista_el_movimiento_de_recargo(
    client, headers_depto_a, db_session
):
    venc_1 = _expensa_primer_venc_pasado(db_session)

    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    assert r.status_code == 200
    recargos = [m for m in r.json()["movimientos"] if m["tipo"] == "recargo"]

    assert len(recargos) == 1
    assert recargos[0]["monto"] == _RECARGO_ESPERADO
    assert recargos[0]["expensa_id"] == 150
    # Se gana el día del primer vencimiento, así que va fechado ahí.
    assert recargos[0]["fecha"] == venc_1.isoformat()
    assert "Recargo por mora" in recargos[0]["descripcion"]


def test_leer_la_cuenta_dos_veces_no_duplica_el_recargo(
    client, headers_depto_a, db_session
):
    _expensa_primer_venc_pasado(db_session)

    client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    assert r.status_code == 200
    body = r.json()

    assert len([m for m in body["movimientos"] if m["tipo"] == "recargo"]) == 1
    assert body["saldo_total"] == _SALDO_CON_RECARGO


def test_pagar_el_monto_con_recargo_deja_el_saldo_en_cero(
    client, headers_depto_a, db_session
):
    """Sin el recargo en la cuenta, pagar lo exigible dejaría saldo negativo."""
    from datetime import date

    from backend.models import MovimientoCuenta, TipoMovimiento

    _expensa_primer_venc_pasado(db_session)

    # Primero leemos: el recargo se materializa.
    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    assert r.json()["saldo_total"] == _SALDO_CON_RECARGO

    db_session.add(MovimientoCuenta(
        consorcio_id=1,
        departamento_id=1,
        fecha=date.today(),
        tipo=TipoMovimiento.pago_recibido,
        descripcion="Pago total",
        monto=_SALDO_CON_RECARGO,
    ))
    db_session.commit()

    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    assert r.json()["saldo_total"] == 0.0


def test_listado_de_cuentas_admin_devenga_el_recargo(
    client, headers_admin, db_session
):
    _expensa_primer_venc_pasado(db_session)

    r = client.get("/movimientos/cuentas", headers=headers_admin)
    assert r.status_code == 200
    por_codigo = {item["codigo"]: item for item in r.json()}

    assert por_codigo["UF-1A"]["saldo_total"] == _SALDO_CON_RECARGO
    # El depto B no tiene expensas vencidas: su saldo no se toca.
    assert por_codigo["UF-2B"]["saldo_total"] == 92000.0


def test_cuenta_departamento_admin_devenga_el_recargo(
    client, headers_admin, db_session
):
    _expensa_primer_venc_pasado(db_session)

    r = client.get("/departamentos/1/cuenta", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["saldo_total"] == _SALDO_CON_RECARGO

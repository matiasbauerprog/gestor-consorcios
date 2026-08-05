from datetime import date

import pytest


_GASTO_VALIDO = {
    "periodo": "2026-06",
    "rubro": "servicios_publicos",
    "clase_prorrateo_id": 500,
    "departamento_id": None,
    "proveedor_id": 600,
    "concepto": "Agua AYSA",
    "monto": 30000,
    "forma_pago": "transferencia",
    "caja_id": 900,  # Fase 5: caja default
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
    "caja_id": 900,  # Fase 5: caja default
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


def test_listar_gastos_materializa_los_recurrentes_del_mes(client, headers_admin):
    periodo = date.today().strftime("%Y-%m")
    r = client.get(f"/gastos?periodo={periodo}", headers=headers_admin)
    assert r.status_code == 200
    assert any(g["gasto_habitual_id"] == 700 for g in r.json())


def test_listar_gastos_no_materializa_en_periodo_futuro(client, headers_admin):
    r = client.get("/gastos?periodo=2030-01", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


def test_listar_gastos_es_idempotente(client, headers_admin):
    periodo = date.today().strftime("%Y-%m")
    primera = client.get(f"/gastos?periodo={periodo}", headers=headers_admin).json()
    segunda = client.get(f"/gastos?periodo={periodo}", headers=headers_admin).json()
    assert len(primera) == len(segunda)


def test_listar_gastos_periodo_cerrado_no_materializa(client, headers_admin):
    """Cierra el período ACTUAL (el mismo que sí tiene la plantilla 700
    disponible para materializar) y confirma que el GET posterior no generó
    nada. A diferencia de un período futuro, acá la única razón por la que no
    debería materializar es el cierre — si se invirtiera ese chequeo, este
    test es el que lo detecta."""
    periodo = date.today().strftime("%Y-%m")
    r_cierre = client.post(f"/periodos/{periodo}/cerrar", json={}, headers=headers_admin)
    assert r_cierre.status_code == 201

    r = client.get(f"/gastos?periodo={periodo}", headers=headers_admin)
    assert r.status_code == 200
    assert not any(g["gasto_habitual_id"] == 700 for g in r.json())


def test_listar_gastos_sin_periodo_no_materializa(client, headers_admin):
    """Sin `periodo` no hay contra qué materializar: el GET debe seguir
    siendo una lectura pura."""
    r = client.get("/gastos", headers=headers_admin)
    assert r.status_code == 200
    assert not any(g["gasto_habitual_id"] == 700 for g in r.json())


def test_habituales_se_materializan_sin_pagar_ni_mover_caja(
    client, headers_admin, db_session
):
    from backend.models import MovimientoCaja

    r = client.post(
        "/gastos/cargar-habituales", json={"periodo": "2026-08"}, headers=headers_admin
    )
    assert r.status_code == 201
    creados = r.json()
    assert creados, "la plantilla 700 del seed debe materializarse"
    assert all(g["pagado"] is False for g in creados)

    ids = [g["id"] for g in creados]
    movs = db_session.query(MovimientoCaja).filter(MovimientoCaja.gasto_id.in_(ids)).all()
    assert movs == [], "un gasto sin pagar no debe generar movimiento de caja"


# ---------------------------------------------------------------------------
# Bloqueos con período cerrado (Task 8)
# ---------------------------------------------------------------------------


def test_plan_cuotas_periodo_cerrado_409(client, headers_admin):
    """POST /gastos/plan-cuotas con período cerrado devuelve 409."""
    # Cerrar el período inicial 2026-11
    r_cierre = client.post(
        "/periodos/2026-11/cerrar",
        json={},
        headers=headers_admin
    )
    assert r_cierre.status_code == 201

    # Intentar POST /plan-cuotas con período cerrado → 409
    payload = dict(_PLAN_VALIDO, periodo="2026-11")
    r = client.post("/gastos/plan-cuotas", json=payload, headers=headers_admin)
    assert r.status_code == 409
    assert "cerrado" in r.json()["detail"].lower()


def test_cargar_habituales_periodo_cerrado_409(client, headers_admin):
    """POST /gastos/cargar-habituales con período cerrado devuelve 409."""
    # Cerrar el período 2026-07
    r_cierre = client.post(
        "/periodos/2026-07/cerrar",
        json={},
        headers=headers_admin
    )
    assert r_cierre.status_code == 201

    # Intentar POST /cargar-habituales → 409
    r = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-07"},
        headers=headers_admin,
    )
    assert r.status_code == 409
    assert "cerrado" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Integración Cajas — Task 8
# ---------------------------------------------------------------------------


def test_crear_gasto_caja_inexistente_404(client, headers_admin):
    """POST /gastos con caja_id inexistente devuelve 404."""
    payload = dict(_GASTO_VALIDO, caja_id=99999)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_gasto_genera_movimiento_caja(client, headers_admin, db_session):
    """POST /gastos crea un MovimientoCaja egreso asociado."""
    from backend.models import MovimientoCaja
    r = client.post("/gastos", json=_GASTO_VALIDO, headers=headers_admin)
    assert r.status_code == 201
    gasto_id = r.json()["id"]
    movs = db_session.query(MovimientoCaja).filter_by(gasto_id=gasto_id).all()
    assert len(movs) == 1
    assert movs[0].tipo.value == "egreso"
    assert movs[0].monto == r.json()["monto"]


def test_patch_gasto_recrea_movimiento(client, headers_admin, db_session):
    """PATCH /gastos/{id} recrea el MovimientoCaja con valores actualizados."""
    from backend.models import MovimientoCaja
    r = client.post("/gastos", json=_GASTO_VALIDO, headers=headers_admin).json()
    gasto_id = r["id"]
    nuevo_monto = r["monto"] + 100
    client.patch(f"/gastos/{gasto_id}", json={"monto": nuevo_monto}, headers=headers_admin)
    movs = db_session.query(MovimientoCaja).filter_by(gasto_id=gasto_id).all()
    assert len(movs) == 1
    assert movs[0].monto == nuevo_monto


def test_delete_gasto_borra_movimiento(client, headers_admin, db_session):
    """DELETE /gastos/{id} elimina el MovimientoCaja asociado."""
    from backend.models import MovimientoCaja
    r = client.post("/gastos", json=_GASTO_VALIDO, headers=headers_admin).json()
    gasto_id = r["id"]
    client.delete(f"/gastos/{gasto_id}", headers=headers_admin)
    movs = db_session.query(MovimientoCaja).filter_by(gasto_id=gasto_id).all()
    assert len(movs) == 0


# ---------------------------------------------------------------------------
# Fase 11: Integración POST /gastos con trabajo_id
# ---------------------------------------------------------------------------


def test_crear_gasto_con_trabajo_id_marca_finalizado(client, headers_admin, db_session):
    """POST /gastos con trabajo_id marca el trabajo como finalizado y setea gasto_id."""
    from backend.models import EstadoTrabajo, Trabajo
    t = Trabajo(consorcio_id=1, descripcion="Trabajo para gasto")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    payload = dict(_GASTO_VALIDO, trabajo_id=t.id)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 201
    gasto_id = r.json()["id"]

    db_session.refresh(t)
    assert t.estado == EstadoTrabajo.finalizado
    assert t.gasto_id == gasto_id


def test_crear_gasto_con_trabajo_id_inexistente_404(client, headers_admin):
    payload = dict(_GASTO_VALIDO, trabajo_id=99999)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Columna `pagado`
# ---------------------------------------------------------------------------


GASTO_VALIDO = {
    "periodo": "2026-07",
    "rubro": "servicios_publicos",
    "clase_prorrateo_id": 500,
    "proveedor_id": 600,
    "concepto": "Luz pasillos julio",
    "monto": 15000.0,
    "forma_pago": "transferencia",
    "caja_id": 900,
    "fecha_pago": "2026-07-10",
}


def test_gasto_creado_a_mano_nace_pagado(client, headers_admin):
    r = client.post("/gastos", json=GASTO_VALIDO, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["pagado"] is True


# ---------------------------------------------------------------------------
# POST /gastos/{gasto_id}/pagar
# ---------------------------------------------------------------------------


def _un_gasto_sin_pagar(client, headers_admin, periodo):
    """Materializa los recurrentes del período y devuelve uno sin pagar."""
    gastos = client.get(f"/gastos?periodo={periodo}", headers=headers_admin).json()
    return next(g for g in gastos if g["pagado"] is False)


def test_pagar_gasto_crea_movimiento_de_caja(client, headers_admin, db_session):
    from backend.models import MovimientoCaja

    periodo = date.today().strftime("%Y-%m")
    sin_pagar = _un_gasto_sin_pagar(client, headers_admin, periodo)

    r = client.post(
        f"/gastos/{sin_pagar['id']}/pagar",
        json={"monto": 63400.0, "fecha_pago": f"{periodo}-15", "caja_id": 900},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["pagado"] is True
    assert r.json()["monto"] == 63400.0

    movs = (
        db_session.query(MovimientoCaja)
        .filter(MovimientoCaja.gasto_id == sin_pagar["id"])
        .all()
    )
    assert len(movs) == 1
    assert movs[0].monto == 63400.0


def test_pagar_dos_veces_devuelve_409(client, headers_admin):
    periodo = date.today().strftime("%Y-%m")
    sin_pagar = _un_gasto_sin_pagar(client, headers_admin, periodo)
    body = {"monto": 100.0, "fecha_pago": f"{periodo}-15", "caja_id": 900}

    assert client.post(
        f"/gastos/{sin_pagar['id']}/pagar", json=body, headers=headers_admin
    ).status_code == 200
    assert client.post(
        f"/gastos/{sin_pagar['id']}/pagar", json=body, headers=headers_admin
    ).status_code == 409


def test_pagar_gasto_inexistente_devuelve_404(client, headers_admin):
    r = client.post(
        "/gastos/999999/pagar",
        json={"monto": 100.0, "fecha_pago": "2026-08-15", "caja_id": 900},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_pagar_gasto_con_monto_cero_devuelve_400(client, headers_admin):
    periodo = date.today().strftime("%Y-%m")
    sin_pagar = _un_gasto_sin_pagar(client, headers_admin, periodo)
    r = client.post(
        f"/gastos/{sin_pagar['id']}/pagar",
        json={"monto": 0, "fecha_pago": f"{periodo}-15", "caja_id": 900},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_pagar_gasto_periodo_cerrado_con_otro_monto_devuelve_409(
    client, headers_admin, db_session
):
    """Sobre un período cerrado sólo se admite confirmar el MISMO monto: acá
    se paga 100 contra un gasto de otro importe, así que cambiaría lo ya
    prorrateado a los departamentos y se rechaza."""
    from backend.models import CoeficienteDepartamento

    periodo = date.today().strftime("%Y-%m")
    sin_pagar = _un_gasto_sin_pagar(client, headers_admin, periodo)

    # Cerrar el período requiere que la clase de prorrateo del gasto recién
    # materializado tenga coeficientes completos para los deptos del seed;
    # si no, el cierre da 409 por validaciones bloqueantes (coeficientes
    # faltantes) en vez del 409 de "período cerrado" que este test ejercita.
    db_session.add_all([
        CoeficienteDepartamento(consorcio_id=1, departamento_id=1, clase_prorrateo_id=500, porcentaje=50),
        CoeficienteDepartamento(consorcio_id=1, departamento_id=2, clase_prorrateo_id=500, porcentaje=50),
    ])
    db_session.commit()

    r_cierre = client.post(f"/periodos/{periodo}/cerrar", json={}, headers=headers_admin)
    assert r_cierre.status_code == 201

    r = client.post(
        f"/gastos/{sin_pagar['id']}/pagar",
        json={"monto": 100.0, "fecha_pago": f"{periodo}-15", "caja_id": 900},
        headers=headers_admin,
    )
    assert r.status_code == 409
    assert "cerrado" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Guarda del PATCH: no debe crear movimiento de caja para un gasto sin pagar
# ---------------------------------------------------------------------------


def test_patch_gasto_no_pagado_no_crea_movimiento_de_caja(
    client, headers_admin, db_session
):
    """Editar un gasto UNPAID no debe conjurar un MovimientoCaja de la nada
    ni marcarlo como pagado de rebote. Sólo POST /pagar puede pagar un gasto."""
    from backend.models import MovimientoCaja

    periodo = date.today().strftime("%Y-%m")
    sin_pagar = _un_gasto_sin_pagar(client, headers_admin, periodo)

    r = client.patch(
        f"/gastos/{sin_pagar['id']}",
        json={"concepto": "Actualizado sin pagar"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["pagado"] is False

    movs = (
        db_session.query(MovimientoCaja)
        .filter(MovimientoCaja.gasto_id == sin_pagar["id"])
        .all()
    )
    assert movs == []


def test_pagar_gasto_periodo_cerrado_mismo_monto_200(client, headers_admin, db_session):
    """El cierre sólo ADVIERTE sobre gastos impagos, así que cerrar por encima
    de ellos es un flujo esperado y la factura puede llegar tres días después.
    Confirmar el pago por el mismo monto no cambia nada de lo prorrateado, así
    que se permite: si no, el egreso se perdía y la caja quedaba mal para
    siempre."""
    from backend.models import CoeficienteDepartamento, MovimientoCaja

    periodo = date.today().strftime("%Y-%m")
    sin_pagar = _un_gasto_sin_pagar(client, headers_admin, periodo)

    db_session.add_all([
        CoeficienteDepartamento(consorcio_id=1, departamento_id=1, clase_prorrateo_id=500, porcentaje=50),
        CoeficienteDepartamento(consorcio_id=1, departamento_id=2, clase_prorrateo_id=500, porcentaje=50),
    ])
    db_session.commit()

    assert client.post(
        f"/periodos/{periodo}/cerrar", json={}, headers=headers_admin
    ).status_code == 201

    r = client.post(
        f"/gastos/{sin_pagar['id']}/pagar",
        json={"monto": sin_pagar["monto"], "fecha_pago": f"{periodo}-15", "caja_id": 900},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["pagado"] is True

    movs = (
        db_session.query(MovimientoCaja)
        .filter(MovimientoCaja.gasto_id == sin_pagar["id"])
        .all()
    )
    assert len(movs) == 1
    assert movs[0].monto == sin_pagar["monto"]


def test_pagar_gasto_periodo_abierto_admite_cualquier_monto(client, headers_admin):
    """En un período abierto no cambia nada: el monto real de la factura pisa
    al estimado de la plantilla."""
    periodo = date.today().strftime("%Y-%m")
    sin_pagar = _un_gasto_sin_pagar(client, headers_admin, periodo)
    otro_monto = sin_pagar["monto"] + 1234.0

    r = client.post(
        f"/gastos/{sin_pagar['id']}/pagar",
        json={"monto": otro_monto, "fecha_pago": f"{periodo}-15", "caja_id": 900},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["monto"] == otro_monto


# ---------------------------------------------------------------------------
# Restricción única de los recurrentes materializados
# ---------------------------------------------------------------------------


def _gasto_recurrente(periodo, habitual_id, monto=1000.0):
    from backend.models import FormaPago, Gasto, Rubro

    return Gasto(
        consorcio_id=1, periodo=periodo, rubro=Rubro.abonos_y_servicios,
        clase_prorrateo_id=500, proveedor_id=600, concepto="Recurrente",
        monto=monto, forma_pago=FormaPago.transferencia, caja_id=900,
        fecha_pago=date(2026, 8, 1), pagado=False,
        gasto_habitual_id=habitual_id,
    )


def test_una_plantilla_no_puede_generar_dos_gastos_en_el_mismo_periodo(db_session):
    """`_materializar_habituales` chequea y después inserta, y FastAPI atiende
    los endpoints sync en un threadpool: dos GET concurrentes pasan el chequeo
    los dos. La restricción de la base es la que decide."""
    from sqlalchemy.exc import IntegrityError

    db_session.add(_gasto_recurrente("2026-08", 700))
    db_session.commit()

    db_session.add(_gasto_recurrente("2026-08", 700))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_la_misma_plantilla_en_otro_periodo_no_choca(db_session):
    db_session.add(_gasto_recurrente("2026-08", 700))
    db_session.add(_gasto_recurrente("2026-09", 700))
    db_session.commit()


def test_los_gastos_comunes_sin_plantilla_no_los_alcanza_la_restriccion(db_session):
    """`gasto_habitual_id` es NULL en los gastos comunes y SQLite trata cada
    NULL como distinto, así que varios del mismo período conviven."""
    db_session.add(_gasto_recurrente("2026-08", None))
    db_session.add(_gasto_recurrente("2026-08", None))
    db_session.add(_gasto_recurrente("2026-08", None))
    db_session.commit()

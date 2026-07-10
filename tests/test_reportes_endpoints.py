"""Tests de endpoints HTTP de reportes."""


def test_morosos_admin_200(client, headers_admin):
    r = client.get("/reportes/morosos", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_morosos_depto_sin_permiso_devuelve_403(client, headers_depto_a):
    """Por default reportes_visibles_a_depto=False → depto recibe 403."""
    r = client.get("/reportes/morosos", headers=headers_depto_a)
    assert r.status_code == 403


def test_morosos_depto_con_permiso_devuelve_200(client, headers_depto_a, headers_admin, db):
    """Cuando admin habilita el flag, depto puede ver el reporte."""
    from backend.models import Consorcio
    cfg = db.get(Consorcio, 1)
    cfg.reportes_visibles_a_depto = True
    db.commit()
    try:
        r = client.get("/reportes/morosos", headers=headers_depto_a)
        assert r.status_code == 200
    finally:
        cfg.reportes_visibles_a_depto = False
        db.commit()


def test_morosos_sin_token_401(client):
    r = client.get("/reportes/morosos")
    assert r.status_code == 401


def test_morosos_pdf_admin_200(client, headers_admin):
    r = client.get("/reportes/morosos/pdf", headers=headers_admin)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")


def test_estado_financiero_admin_200(client, headers_admin):
    r = client.get("/reportes/estado-financiero", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "activo_total" in body and "pasivo_total" in body and "patrimonio_neto" in body


def test_estado_financiero_filtro_fecha(client, headers_admin):
    r = client.get("/reportes/estado-financiero?fecha_corte=2026-01-01", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["fecha_corte"] == "2026-01-01"


def test_estado_financiero_pdf_admin_200(client, headers_admin):
    r = client.get("/reportes/estado-financiero/pdf", headers=headers_admin)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")


def test_gastos_periodo_admin_200(client, headers_admin):
    r = client.get("/reportes/gastos/2026-05", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["periodo"] == "2026-05"
    assert "por_rubro" in body and "particulares" in body


def test_gastos_periodo_filtro_rubro(client, headers_admin):
    r = client.get("/reportes/gastos/2026-05?rubro=abonos_y_servicios", headers=headers_admin)
    assert r.status_code == 200
    for items in r.json()["por_rubro"].values():
        for it in items:
            assert it["rubro"] == "abonos_y_servicios"


def test_gastos_periodo_inexistente_total_cero(client, headers_admin):
    r = client.get("/reportes/gastos/2099-12", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["total_general"] == 0


def test_gastos_periodo_pdf_admin_200(client, headers_admin):
    r = client.get("/reportes/gastos/2026-05/pdf", headers=headers_admin)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")


def test_proveedores_admin_200(client, headers_admin):
    r = client.get("/reportes/proveedores?anio=2026", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_proveedores_pdf_admin_200(client, headers_admin):
    r = client.get("/reportes/proveedores/pdf?anio=2026", headers=headers_admin)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# Multitenant
# ---------------------------------------------------------------------------


def test_flag_reportes_se_lee_del_consorcio_activo(client, dos_consorcios, db):
    """El flag del consorcio 2 habilita a los deptos de c2, aunque c1 lo tenga
    apagado. Antes se leía hardcodeado el consorcio 1."""
    from backend.models import Consorcio
    c2 = db.get(Consorcio, 2)
    c2.reportes_visibles_a_depto = True
    db.commit()

    r = client.get("/reportes/morosos", headers=dos_consorcios["headers_depto_c2"])
    assert r.status_code == 200

    # El depto de c1 sigue bloqueado (flag de c1 = False).
    r = client.get("/reportes/morosos", headers=dos_consorcios["headers_depto_c1"])
    assert r.status_code == 403


def test_morosos_no_mezcla_consorcios(client, dos_consorcios, db):
    """Los morosos de c1 no deben incluir deptos de c2."""
    from datetime import date
    from backend.models import Expensa, MovimientoCuenta, TipoMovimiento

    # Genero deuda vencida en el depto 3 (consorcio 2).
    db.add(Expensa(
        consorcio_id=2, departamento_id=3, periodo="2025-01",
        monto_primer_vencimiento=70000.0, fecha_primer_vencimiento=date(2025, 1, 10),
        monto_segundo_vencimiento=74900.0, fecha_segundo_vencimiento=date(2025, 1, 20),
        saldo_anterior=0.0,
    ))
    db.add(MovimientoCuenta(
        consorcio_id=2, departamento_id=3, fecha=date(2025, 1, 1),
        tipo=TipoMovimiento.expensa_emitida, descripcion="Expensa 2025-01",
        monto=70000.0,
    ))
    db.commit()

    r = client.get("/reportes/morosos", headers=dos_consorcios["headers_admin_c1"])
    assert r.status_code == 200
    ids = {item["departamento_id"] for item in r.json()}
    assert 3 not in ids  # depto de c2 jamás en el reporte de c1

    r2 = client.get("/reportes/morosos", headers=dos_consorcios["headers_admin_c2"])
    assert r2.status_code == 200
    ids2 = {item["departamento_id"] for item in r2.json()}
    assert 3 in ids2
    assert ids2.isdisjoint({1, 2})  # deptos de c1 jamás en el reporte de c2


def test_gastos_periodo_no_mezcla_consorcios(client, dos_consorcios, db):
    from datetime import date
    from backend.models import Caja, FormaPago, Gasto, Proveedor, Rubro

    prov_c2 = Proveedor(
        id=650, consorcio_id=2, razon_social="Proveedor C2 SA",
        cuit="30-55555555-5", activo=True,
    )
    db.add(prov_c2)
    db.flush()
    db.add(Gasto(
        consorcio_id=2, periodo="2026-05", rubro=Rubro.gastos_generales,
        clase_prorrateo_id=None, departamento_id=None, proveedor_id=650,
        concepto="Gasto exclusivo de c2", monto=99999.0,
        forma_pago=FormaPago.transferencia, caja_id=901,
        fecha_pago=date(2026, 5, 15),
    ))
    db.commit()

    # Reporte de c1 para 2026-05: no debe incluir el gasto de c2.
    r = client.get("/reportes/gastos/2026-05", headers=dos_consorcios["headers_admin_c1"])
    assert r.status_code == 200
    conceptos = [
        it["concepto"]
        for items in r.json()["por_rubro"].values()
        for it in items
    ]
    assert "Gasto exclusivo de c2" not in conceptos

    # Y el de c2 sí lo incluye.
    r2 = client.get("/reportes/gastos/2026-05", headers=dos_consorcios["headers_admin_c2"])
    assert r2.status_code == 200
    conceptos2 = [
        it["concepto"]
        for items in r2.json()["por_rubro"].values()
        for it in items
    ]
    assert "Gasto exclusivo de c2" in conceptos2


def test_estado_financiero_no_mezcla_cajas(client, dos_consorcios):
    """Las cajas de c2 no aparecen en el estado financiero de c1."""
    r = client.get("/reportes/estado-financiero", headers=dos_consorcios["headers_admin_c1"])
    assert r.status_code == 200
    nombres = {c["nombre"] for c in r.json()["cajas"]}
    assert "Banco C2" not in nombres

    r2 = client.get("/reportes/estado-financiero", headers=dos_consorcios["headers_admin_c2"])
    assert r2.status_code == 200
    nombres2 = {c["nombre"] for c in r2.json()["cajas"]}
    assert nombres2 == {"Banco C2"}


def test_proveedores_no_mezcla_consorcios(client, dos_consorcios, db):
    from datetime import date
    from backend.models import FormaPago, Gasto, Proveedor, Rubro

    prov_c2 = Proveedor(
        id=651, consorcio_id=2, razon_social="Solo C2 SRL",
        cuit="30-66666666-6", activo=True,
    )
    db.add(prov_c2)
    db.flush()
    db.add(Gasto(
        consorcio_id=2, periodo="2026-04", rubro=Rubro.gastos_generales,
        clase_prorrateo_id=None, departamento_id=None, proveedor_id=651,
        concepto="Servicio c2", monto=5000.0,
        forma_pago=FormaPago.transferencia, caja_id=901,
        fecha_pago=date(2026, 4, 10),
    ))
    db.commit()

    r = client.get("/reportes/proveedores?anio=2026", headers=dos_consorcios["headers_admin_c1"])
    assert r.status_code == 200
    razones = {p["razon_social"] for p in r.json()}
    assert "Solo C2 SRL" not in razones

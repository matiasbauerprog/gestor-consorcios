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

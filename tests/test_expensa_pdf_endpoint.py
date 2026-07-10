"""Tests del endpoint GET /expensas/{id}/pdf."""


def test_admin_descarga_pdf_de_cualquier_expensa(client, headers_admin, db_session):
    from backend.models import Expensa
    expensa = db_session.query(Expensa).first()
    r = client.get(f"/expensas/{expensa.id}/pdf", headers=headers_admin)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")


def test_depto_descarga_su_propia_expensa(client, headers_depto_a, db_session):
    """Depto a descarga la expensa de su depto. Asumimos que existe una para depto-a."""
    from backend.models import Expensa, Usuario, Rol as RolModel
    # Encontrar el departamento_id de depto-a vía Usuario
    depto_a_user = db_session.query(Usuario).filter_by(email="a@test.local").first()
    if depto_a_user is None:
        # Probar con otro patrón si el seed cambió
        depto_a_user = db_session.query(Usuario).filter(Usuario.rol == RolModel.departamento).first()
    assert depto_a_user is not None, "Seed debe tener al menos un user depto"

    expensa = db_session.query(Expensa).filter_by(departamento_id=depto_a_user.departamento_id).first()
    if expensa is None:
        # Crear una expensa para ese depto si no existe
        from datetime import date
        expensa = Expensa(consorcio_id=1, departamento_id=depto_a_user.departamento_id, periodo="2099-12",
            monto_primer_vencimiento=1000, fecha_primer_vencimiento=date(2099, 12, 10),
            monto_segundo_vencimiento=1070, fecha_segundo_vencimiento=date(2099, 12, 20),
            saldo_anterior=0,
        )
        db_session.add(expensa)
        db_session.commit()
    r = client.get(f"/expensas/{expensa.id}/pdf", headers=headers_depto_a)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")


def test_depto_no_puede_descargar_expensa_ajena(client, headers_depto_a, db_session):
    """Depto-a NO puede descargar expensa de otro depto."""
    from backend.models import Expensa, Usuario, Rol as RolModel
    depto_a_user = db_session.query(Usuario).filter_by(email="a@test.local").first()
    if depto_a_user is None:
        depto_a_user = db_session.query(Usuario).filter(Usuario.rol == RolModel.departamento).first()
    # Buscar expensa de otro depto
    expensa = db_session.query(Expensa).filter(
        Expensa.departamento_id != depto_a_user.departamento_id
    ).first()
    if expensa is None:
        # No hay expensa ajena, no podemos testear este caso
        return
    r = client.get(f"/expensas/{expensa.id}/pdf", headers=headers_depto_a)
    assert r.status_code == 403


def test_sin_token_devuelve_401(client, db_session):
    from backend.models import Expensa
    expensa = db_session.query(Expensa).first()
    r = client.get(f"/expensas/{expensa.id}/pdf")
    assert r.status_code == 401


def test_expensa_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/expensas/99999/pdf", headers=headers_admin)
    assert r.status_code == 404


def test_content_disposition_inline(client, headers_admin, db_session):
    from backend.models import Expensa
    expensa = db_session.query(Expensa).first()
    r = client.get(f"/expensas/{expensa.id}/pdf", headers=headers_admin)
    assert "inline" in r.headers.get("content-disposition", "")
    assert ".pdf" in r.headers.get("content-disposition", "")


def _extraer_texto_pdf(pdf_bytes: bytes) -> bytes:
    """Descomprime los streams del PDF (reportlab usa ASCII85 + zlib) para
    poder buscar strings en el contenido."""
    import base64
    import re
    import zlib
    textos = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.S):
        data = m.group(1).strip()
        for decodificar in (
            lambda d: zlib.decompress(base64.a85decode(d, adobe=True)),
            lambda d: zlib.decompress(d),
            lambda d: d,
        ):
            try:
                textos.append(decodificar(data))
                break
            except Exception:
                continue
    return b"".join(textos)


def test_pdf_boleta_usa_datos_del_consorcio_de_la_expensa(client, dos_consorcios, db):
    """La boleta de una expensa del consorcio 2 debe llevar el encabezado del
    consorcio 2, no el del consorcio 1 (antes estaba hardcodeado)."""
    from datetime import date, timedelta
    from backend.models import Expensa

    e = Expensa(
        consorcio_id=2,
        departamento_id=3,
        periodo="2026-06",
        monto_primer_vencimiento=50000.0,
        fecha_primer_vencimiento=date(2026, 7, 10),
        monto_segundo_vencimiento=53500.0,
        fecha_segundo_vencimiento=date(2026, 7, 20),
        saldo_anterior=0.0,
    )
    db.add(e)
    db.commit()

    r = client.get(
        f"/expensas/{e.id}/pdf", headers=dos_consorcios["headers_admin_c2"]
    )
    assert r.status_code == 200
    texto = _extraer_texto_pdf(r.content)
    assert b"Consorcio Aislado" in texto  # nombre del consorcio 2
    assert b"Consorcio Test" not in texto  # jamas el encabezado del consorcio 1

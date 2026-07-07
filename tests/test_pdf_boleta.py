"""Tests de generación de PDF de boleta (ReportLab)."""
from backend.pdf import generar_pdf_boleta


def test_genera_pdf_devuelve_bytes_con_magic_header(db_session):
    """Smoke: para una expensa sembrada, generar PDF devuelve bytes válidos."""
    from backend.models import Expensa
    expensa = db_session.query(Expensa).first()
    assert expensa is not None, "El seed debe tener al menos una expensa"
    pdf = generar_pdf_boleta(expensa, db_session)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1000, "PDF debería pesar al menos 1KB"
    assert pdf.startswith(b"%PDF-"), "Debería empezar con magic header de PDF"


def test_genera_pdf_con_saldo_anterior(db_session):
    """Si la expensa tiene saldo_anterior > 0, igual genera sin error."""
    from backend.models import Expensa
    expensa = db_session.query(Expensa).first()
    expensa.saldo_anterior = 2500.0
    db_session.flush()
    pdf = generar_pdf_boleta(expensa, db_session)
    assert pdf.startswith(b"%PDF-")


def test_genera_pdf_con_detalle_multi_rubro(db_session):
    """Expensa con ExpensaDetalle en varios rubros se renderiza correctamente."""
    from backend.models import Expensa, ExpensaDetalle, Rubro
    expensa = db_session.query(Expensa).first()
    db_session.add_all([
        ExpensaDetalle(consorcio_id=1, expensa_id=expensa.id, rubro=Rubro.servicios_publicos,
            clase_prorrateo_id=None, departamento_origen_id=None,
            concepto="Luz", monto=5000,
        ),
        ExpensaDetalle(consorcio_id=1, expensa_id=expensa.id, rubro=Rubro.seguros,
            clase_prorrateo_id=None, departamento_origen_id=None,
            concepto="Seguro hogar", monto=3000,
        ),
    ])
    db_session.flush()
    pdf = generar_pdf_boleta(expensa, db_session)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000

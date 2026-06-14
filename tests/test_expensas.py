# ---------------------------------------------------------------------------
# ExpensaOut.ultimo_comprobante
# ---------------------------------------------------------------------------


def test_listar_expensas_ultimo_comprobante_es_null_si_no_hay(client, headers_admin):
    r = client.get("/expensas", headers=headers_admin)
    assert r.status_code == 200
    for expensa in r.json():
        assert expensa["ultimo_comprobante"] is None


def test_listar_expensas_ultimo_comprobante_es_el_mas_reciente(
    client, headers_depto_a, db_session
):
    from datetime import date, datetime, timezone, timedelta
    from backend.models import Comprobante, EstadoComprobante

    c_viejo = Comprobante(
        id=500,
        expensa_id=100,
        fecha_pago=date(2026, 5, 5),
        monto=50000.0,
        archivo_url=None,
        estado=EstadoComprobante.rechazado,
    )
    c_nuevo = Comprobante(
        id=501,
        expensa_id=100,
        fecha_pago=date(2026, 5, 6),
        monto=85000.0,
        archivo_url="https://drive.example/x.pdf",
        estado=EstadoComprobante.pendiente_verificacion,
    )
    db_session.add_all([c_viejo, c_nuevo])
    db_session.flush()
    # Forzar fecha_creacion: nuevo > viejo (en una segunda al menos).
    c_viejo.fecha_creacion = datetime.now(timezone.utc) - timedelta(minutes=10)
    c_nuevo.fecha_creacion = datetime.now(timezone.utc)
    db_session.commit()

    r = client.get("/expensas", headers=headers_depto_a)
    assert r.status_code == 200
    expensa_100 = next(e for e in r.json() if e["id"] == 100)
    assert expensa_100["ultimo_comprobante"] is not None
    assert expensa_100["ultimo_comprobante"]["id"] == 501
    assert expensa_100["ultimo_comprobante"]["estado"] == "pendiente_verificacion"

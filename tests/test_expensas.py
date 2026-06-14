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

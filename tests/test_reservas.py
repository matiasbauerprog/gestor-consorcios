from datetime import datetime, timedelta

from backend.models import Amenity, EstadoReserva, Reserva


def _en_futuro(dias=1, horas=10, dur_horas=2):
    """Devuelve (inicio_iso, fin_iso) en el futuro relativo a now()."""
    inicio = datetime.now().replace(microsecond=0) + timedelta(days=dias, hours=horas)
    fin = inicio + timedelta(hours=dur_horas)
    return inicio.isoformat(), fin.isoformat()


def test_crear_reserva_como_representante_devuelve_403(client, headers_representante):
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_representante,
    )
    assert r.status_code == 403


def test_crear_reserva_amenity_inactivo_devuelve_409(client, headers_depto_a, db_session):
    a = db_session.get(Amenity, 301)
    a.activo = False
    db_session.commit()
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 409


def test_crear_reserva_en_el_pasado_devuelve_400(client, headers_depto_a):
    pasado_inicio = (datetime.now() - timedelta(days=2)).isoformat()
    pasado_fin = (datetime.now() - timedelta(days=2) + timedelta(hours=2)).isoformat()
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": pasado_inicio, "fin": pasado_fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_crear_reserva_supera_duracion_maxima_devuelve_400(client, headers_depto_a, db_session):
    a = db_session.get(Amenity, 301)
    a.duracion_maxima_horas = 2
    db_session.commit()
    inicio, fin = _en_futuro(dur_horas=5)
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_crear_reserva_supera_anticipacion_maxima_devuelve_400(client, headers_depto_a, db_session):
    a = db_session.get(Amenity, 301)
    a.anticipacion_maxima_dias = 5
    db_session.commit()
    inicio, fin = _en_futuro(dias=10)
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_crear_reserva_supera_max_activas_por_depto_devuelve_409(client, headers_depto_a, db_session):
    a = db_session.get(Amenity, 301)
    a.max_reservas_activas_por_depto = 1
    db_session.commit()
    inicio1, fin1 = _en_futuro(dias=2)
    r1 = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio1, "fin": fin1},
        headers=headers_depto_a,
    )
    assert r1.status_code == 201
    inicio2, fin2 = _en_futuro(dias=5)
    r2 = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio2, "fin": fin2},
        headers=headers_depto_a,
    )
    assert r2.status_code == 409


def test_crear_reserva_admin_no_aplica_max_activas(client, headers_admin, db_session):
    a = db_session.get(Amenity, 301)
    a.max_reservas_activas_por_depto = 1
    db_session.commit()
    inicio1, fin1 = _en_futuro(dias=2)
    inicio2, fin2 = _en_futuro(dias=5)
    assert client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio1, "fin": fin1},
        headers=headers_admin,
    ).status_code == 201
    assert client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio2, "fin": fin2},
        headers=headers_admin,
    ).status_code == 201

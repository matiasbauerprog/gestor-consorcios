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


def test_reservar_amenity_con_precio_genera_movimiento_cuenta(client, headers_depto_a, db_session):
    from backend.models import MovimientoCuenta, TipoMovimiento

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 5000.0
    db_session.commit()

    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["movimiento_cuenta_id"] is not None

    m = db_session.get(MovimientoCuenta, body["movimiento_cuenta_id"])
    assert m is not None
    assert m.tipo == TipoMovimiento.nota_debito
    assert m.monto == 5000.0
    assert m.departamento_id == 1  # depto_a
    assert "Laundry" in m.descripcion


def test_reservar_amenity_sin_precio_no_genera_movimiento(client, headers_depto_a, db_session):
    a = db_session.get(Amenity, 301)
    assert a.precio_reserva is None
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    assert r.json()["movimiento_cuenta_id"] is None


def test_reservar_admin_amenity_con_precio_no_genera_movimiento(client, headers_admin, db_session):
    a = db_session.get(Amenity, 301)
    a.precio_reserva = 5000.0
    db_session.commit()
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json()["movimiento_cuenta_id"] is None


def test_movimiento_usa_fecha_de_hoy_no_inicio_reserva(client, headers_depto_a, db_session):
    from datetime import date as date_cls
    from backend.models import MovimientoCuenta

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 3000.0
    db_session.commit()
    inicio, fin = _en_futuro(dias=30)
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    mov_id = r.json()["movimiento_cuenta_id"]
    m = db_session.get(MovimientoCuenta, mov_id)
    assert m.fecha == date_cls.today()


def test_cancelar_reserva_dueno_dentro_de_plazo_reversa_cargo(client, headers_depto_a, db_session):
    from backend.models import MovimientoCuenta, TipoMovimiento

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 4000.0
    a.horas_minimas_cancelacion = 24
    db_session.commit()

    # Reserva en +5 días → dentro del plazo gratuito (24h)
    inicio, fin = _en_futuro(dias=5)
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]
    mov_inicial_id = r.json()["movimiento_cuenta_id"]

    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_depto_a)
    assert rc.status_code == 200

    reversa = db_session.query(MovimientoCuenta).filter(
        MovimientoCuenta.departamento_id == 1,
        MovimientoCuenta.tipo == TipoMovimiento.nota_credito,
        MovimientoCuenta.monto == 4000.0,
    ).order_by(MovimientoCuenta.id.desc()).first()
    assert reversa is not None
    assert reversa.id != mov_inicial_id


def test_cancelar_reserva_dueno_fuera_de_plazo_no_reversa(client, headers_depto_a, db_session):
    from datetime import datetime, timedelta
    from backend.models import MovimientoCuenta, TipoMovimiento

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 4000.0
    a.horas_minimas_cancelacion = 48
    db_session.commit()

    # Reserva en +12h → FUERA del plazo gratuito de 48h
    inicio = (datetime.now() + timedelta(hours=12)).replace(microsecond=0).isoformat()
    fin = (datetime.now() + timedelta(hours=14)).replace(microsecond=0).isoformat()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    reserva_id = r.json()["id"]

    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_depto_a)
    assert rc.status_code == 200

    reversa = db_session.query(MovimientoCuenta).filter(
        MovimientoCuenta.departamento_id == 1,
        MovimientoCuenta.tipo == TipoMovimiento.nota_credito,
    ).first()
    assert reversa is None


def test_cancelar_reserva_admin_cancela_ajena_siempre_reversa(client, headers_admin, headers_depto_a, db_session):
    from datetime import datetime, timedelta
    from backend.models import MovimientoCuenta, TipoMovimiento

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 4000.0
    a.horas_minimas_cancelacion = 48
    db_session.commit()

    # Depto reserva con +12h (fuera del plazo gratuito normalmente)
    inicio = (datetime.now() + timedelta(hours=12)).replace(microsecond=0).isoformat()
    fin = (datetime.now() + timedelta(hours=14)).replace(microsecond=0).isoformat()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]

    # Admin cancela → reversa SIEMPRE
    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_admin)
    assert rc.status_code == 200

    reversa = db_session.query(MovimientoCuenta).filter(
        MovimientoCuenta.tipo == TipoMovimiento.nota_credito,
    ).first()
    assert reversa is not None


def test_cancelar_reserva_sin_horas_minimas_siempre_reversa(client, headers_depto_a, db_session):
    from datetime import datetime, timedelta
    from backend.models import MovimientoCuenta, TipoMovimiento

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 4000.0
    # horas_minimas_cancelacion queda en None
    db_session.commit()

    inicio = (datetime.now() + timedelta(hours=1)).replace(microsecond=0).isoformat()
    fin = (datetime.now() + timedelta(hours=3)).replace(microsecond=0).isoformat()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]

    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_depto_a)
    assert rc.status_code == 200

    reversa = db_session.query(MovimientoCuenta).filter(
        MovimientoCuenta.tipo == TipoMovimiento.nota_credito,
    ).first()
    assert reversa is not None


def test_obtener_reserva_dueno_devuelve_200(client, headers_depto_a):
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]
    rg = client.get(f"/reservas/{reserva_id}", headers=headers_depto_a)
    assert rg.status_code == 200
    assert rg.json()["id"] == reserva_id


def test_obtener_reserva_admin_devuelve_200(client, headers_admin, headers_depto_a):
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]
    rg = client.get(f"/reservas/{reserva_id}", headers=headers_admin)
    assert rg.status_code == 200


def test_obtener_reserva_ajena_como_depto_devuelve_403(client, headers_depto_a, headers_depto_b):
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]
    rg = client.get(f"/reservas/{reserva_id}", headers=headers_depto_b)
    assert rg.status_code == 403


def test_obtener_reserva_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/reservas/99999", headers=headers_admin)
    assert r.status_code == 404


def test_admin_cancela_reserva_ajena_notifica_al_depto(client, headers_admin, headers_depto_a, db_session):
    from backend.models import Notificacion

    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]

    notif_antes = db_session.query(Notificacion).count()
    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_admin)
    assert rc.status_code == 200

    notif_despues = db_session.query(Notificacion).count()
    assert notif_despues > notif_antes


def test_depto_cancela_su_reserva_no_genera_notificacion(client, headers_depto_a, db_session):
    from backend.models import Notificacion

    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]

    notif_antes = db_session.query(Notificacion).count()
    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_depto_a)
    assert rc.status_code == 200

    notif_despues = db_session.query(Notificacion).count()
    assert notif_despues == notif_antes


def test_admin_cancela_reserva_solo_avisa_a_quien_reservo(
    client, headers_admin, headers_depto_a, db_session
):
    """En la unidad pueden convivir propietario e inquilino.

    "La administración canceló TU reserva... se reversó el cargo de $N" está
    escrito hacia quien reservó: al conviviente le hablaría de una reserva y de
    un cargo que no son suyos.
    """
    from backend.models import Notificacion, Rol, Usuario

    conviviente = Usuario(
        id=77, email="conviviente@test.local", password_hash="x",
        rol=Rol.departamento, departamento_id=1,
    )
    db_session.add(conviviente)
    db_session.commit()

    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]
    reserva = db_session.get(Reserva, reserva_id)
    assert reserva.usuario_id == 2  # el depto A, no el conviviente

    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_admin)
    assert rc.status_code == 200

    avisos = (
        db_session.query(Notificacion)
        .filter_by(tipo="reserva_cancelada_por_admin")
        .all()
    )
    assert [n.usuario_id for n in avisos] == [2]


def test_reserva_de_depto_avisa_al_admin(client, headers_depto_a, db_session):
    from backend.models import Notificacion
    from tests.conftest import RESERVA_INICIO

    inicio = (RESERVA_INICIO.replace(hour=9)).isoformat()
    fin = (RESERVA_INICIO.replace(hour=11)).isoformat()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 201

    n = db_session.query(Notificacion).filter_by(tipo="reserva_nueva_de_depto").one()
    assert n.usuario_id == 1
    assert "Laundry" in n.mensaje


def test_reserva_del_admin_no_se_autoavisa(client, headers_admin, db_session):
    from backend.models import Notificacion
    from tests.conftest import RESERVA_INICIO

    inicio = (RESERVA_INICIO.replace(hour=19)).isoformat()
    fin = (RESERVA_INICIO.replace(hour=21)).isoformat()
    client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_admin,
    )
    assert db_session.query(Notificacion).filter_by(tipo="reserva_nueva_de_depto").count() == 0

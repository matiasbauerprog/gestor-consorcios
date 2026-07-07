"""Tests del módulo y router de notificaciones."""
from backend.models import EstadoPeticion, Notificacion, Peticion, Rol, Usuario
from backend.notificaciones import crear_notificacion, notificar_cambio_estado_peticion


def test_crear_notificacion_persiste(db):
    u = db.query(Usuario).filter_by(rol=Rol.departamento).first()
    n = crear_notificacion(db, usuario_id=u.id, mensaje="Test", link="/test")
    db.commit()
    assert n.id is not None
    assert n.leida is False
    assert n.usuario_id == u.id


def test_notificar_abierta_a_convertida_crea_notif(db, capsys):
    p = Peticion(consorcio_id=1, departamento_id=1, titulo="Test peti",
        descripcion="x", estado=EstadoPeticion.convertida_en_trabajo,
    )
    db.add(p); db.flush()
    before = db.query(Notificacion).filter_by(link="/peticiones").count()
    notificar_cambio_estado_peticion(db, p, EstadoPeticion.abierta)
    db.commit()
    after = db.query(Notificacion).filter_by(link="/peticiones").count()
    assert after > before


def test_notificar_sin_cambio_estado_no_hace_nada(db):
    p = Peticion(consorcio_id=1, departamento_id=1, titulo="X", descripcion="x",
        estado=EstadoPeticion.convertida_en_trabajo,
    )
    db.add(p); db.flush()
    before = db.query(Notificacion).count()
    notificar_cambio_estado_peticion(db, p, EstadoPeticion.convertida_en_trabajo)
    after = db.query(Notificacion).count()
    assert before == after


def test_get_notificaciones_filtra_por_usuario(client, headers_depto_a, headers_depto_b, db):
    u_a = db.query(Usuario).filter_by(id=2).first()
    u_b = db.query(Usuario).filter_by(id=3).first()
    db.add(Notificacion(consorcio_id=1, usuario_id=u_a.id, mensaje="Para A", link="/peticiones"))
    db.add(Notificacion(consorcio_id=1, usuario_id=u_b.id, mensaje="Para B", link="/peticiones"))
    db.commit()
    r = client.get("/notificaciones", headers=headers_depto_a)
    assert r.status_code == 200
    mensajes = [n["mensaje"] for n in r.json()]
    assert "Para A" in mensajes
    assert "Para B" not in mensajes


def test_no_leidas_count(client, headers_depto_a, db):
    u = db.query(Usuario).filter_by(id=2).first()
    db.add(Notificacion(consorcio_id=1, usuario_id=u.id, mensaje="No leida 1", leida=False))
    db.add(Notificacion(consorcio_id=1, usuario_id=u.id, mensaje="No leida 2", leida=False))
    db.add(Notificacion(consorcio_id=1, usuario_id=u.id, mensaje="Leida", leida=True))
    db.commit()
    r = client.get("/notificaciones/no-leidas-count", headers=headers_depto_a)
    assert r.status_code == 200
    assert r.json()["count"] >= 2


def test_marcar_leida_solo_propia(client, headers_depto_a, db):
    u_b = db.query(Usuario).filter_by(id=3).first()
    notif_ajena = Notificacion(consorcio_id=1, usuario_id=u_b.id, mensaje="ajena", leida=False)
    db.add(notif_ajena); db.commit()
    r = client.post(f"/notificaciones/{notif_ajena.id}/marcar-leida", headers=headers_depto_a)
    assert r.status_code == 404

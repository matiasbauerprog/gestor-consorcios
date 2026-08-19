"""Sólo se persisten las diferencias contra el default del catálogo."""
from backend.models import PreferenciaNotificacion
from backend.notificaciones.catalogo import evento
from backend.notificaciones.preferencias import (
    email_activo_para,
    guardar_preferencia,
    preferencias_de,
)

# comunicado_publicado tiene email_por_defecto=True.
# comprobante_aprobado tiene email_por_defecto=False.


def test_sin_fila_vale_el_default_del_catalogo(db):
    assert email_activo_para(db, 2, evento("comunicado_publicado")) is True
    assert email_activo_para(db, 2, evento("comprobante_aprobado")) is False


def test_guardar_distinto_del_default_crea_fila(db):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    filas = db.query(PreferenciaNotificacion).filter_by(usuario_id=2).all()
    assert len(filas) == 1
    assert filas[0].email_activo is False
    assert email_activo_para(db, 2, evento("comunicado_publicado")) is False


def test_volver_al_default_borra_la_fila(db):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    guardar_preferencia(db, 2, evento("comunicado_publicado"), True)
    db.flush()
    assert db.query(PreferenciaNotificacion).filter_by(usuario_id=2).count() == 0
    assert email_activo_para(db, 2, evento("comunicado_publicado")) is True


def test_guardar_igual_al_default_no_crea_fila(db):
    guardar_preferencia(db, 2, evento("comprobante_aprobado"), False)
    db.flush()
    assert db.query(PreferenciaNotificacion).filter_by(usuario_id=2).count() == 0


def test_reguardar_el_mismo_valor_no_duplica(db):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    assert db.query(PreferenciaNotificacion).filter_by(usuario_id=2).count() == 1


def test_preferencias_de_devuelve_solo_lo_guardado(db):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    assert preferencias_de(db, 2) == {"comunicado_publicado": False}


def test_las_preferencias_no_se_cruzan_entre_usuarios(db):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    assert email_activo_para(db, 3, evento("comunicado_publicado")) is True

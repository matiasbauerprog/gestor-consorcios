"""El emisor: destinatarios, filtro de actor, pendientes y canal."""
from backend.models import Notificacion, Usuario
from backend.notificaciones import emitir, resolver_pendiente
from backend.notificaciones.preferencias import guardar_preferencia
from backend.notificaciones.catalogo import evento


def _ctx_comunicado():
    return {"titulo": "Corte de agua", "cuerpo": "Mañana de 9 a 13."}


def test_emitir_crea_una_notificacion_por_destinatario(db):
    emitir(
        db, "comunicado_publicado",
        consorcio_id=1, contexto=_ctx_comunicado(),
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()
    ns = db.query(Notificacion).filter_by(tipo="comunicado_publicado").all()
    assert [n.usuario_id for n in ns] == [2]
    assert ns[0].mensaje == "Nuevo comunicado: Corte de agua"
    assert ns[0].link == "/comunicados"


def test_emitir_excluye_al_actor(db):
    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-1A", "titulo": "Filtración"},
        actor_usuario_id=1, entidad_id=10,
    )
    db.commit()
    ns = db.query(Notificacion).filter_by(tipo="peticion_nueva").all()
    assert ns == []  # el único admin del consorcio es el actor


def test_emitir_guarda_la_entidad_si_el_evento_es_pendiente(db):
    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-1A", "titulo": "Filtración"},
        actor_usuario_id=2, entidad_id=10,
    )
    db.commit()
    n = db.query(Notificacion).filter_by(tipo="peticion_nueva").one()
    assert n.entidad_tipo == "peticion"
    assert n.entidad_id == 10


def test_emitir_evento_informativo_no_guarda_entidad(db):
    emitir(
        db, "comunicado_publicado",
        consorcio_id=1, contexto=_ctx_comunicado(),
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()
    n = db.query(Notificacion).filter_by(tipo="comunicado_publicado").one()
    assert n.entidad_tipo is None
    assert n.entidad_id is None


def test_evento_solo_mail_no_crea_campanita(db, capsys):
    emitir(
        db, "reserva_confirmada",
        consorcio_id=1,
        contexto={"amenity": "SUM", "fecha": "2026-09-01 14:00", "monto": None},
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()
    assert db.query(Notificacion).filter_by(tipo="reserva_confirmada").count() == 0
    assert "a@test.local" in capsys.readouterr().out


def test_restringir_a_usuario_deja_afuera_al_resto_del_departamento(db, capsys):
    """El aviso en segunda persona va sólo a quien hizo la acción.

    En la unidad 1 pueden convivir propietario e inquilino. "Tu reserva fue
    confirmada" le hablaría al segundo de algo que no hizo.
    """
    conviviente = Usuario(
        id=51, email="conviviente@test.local", password_hash="x",
        rol=db.get(Usuario, 2).rol, departamento_id=1,
    )
    db.add(conviviente)
    db.flush()
    capsys.readouterr()  # descartar salida previa

    emitir(
        db, "reserva_confirmada",
        consorcio_id=1,
        contexto={"amenity": "SUM", "fecha": "2026-09-01 14:00", "monto": 1500.0},
        actor_usuario_id=None, departamento_id=1,
        restringir_a_usuario_id=2,
    )
    db.commit()

    salida = capsys.readouterr().out
    assert "To: a@test.local" in salida
    assert "conviviente@test.local" not in salida
    assert salida.count("[EMAIL CONSOLE MODE] To:") == 1


def test_restringir_a_usuario_ajeno_no_emite_nada(db, capsys):
    """El usuario 3 es del departamento 2: no está entre los resueltos."""
    capsys.readouterr()

    emitir(
        db, "comunicado_publicado",
        consorcio_id=1, contexto=_ctx_comunicado(),
        actor_usuario_id=1, departamento_id=1,
        restringir_a_usuario_id=3,
    )
    db.commit()

    assert db.query(Notificacion).filter_by(tipo="comunicado_publicado").count() == 0
    assert "[EMAIL CONSOLE MODE] To:" not in capsys.readouterr().out


def test_preferencia_apagada_no_manda_mail_pero_si_campanita(db, capsys):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    capsys.readouterr()  # descartar salida previa

    emitir(
        db, "comunicado_publicado",
        consorcio_id=1, contexto=_ctx_comunicado(),
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()

    assert db.query(Notificacion).filter_by(tipo="comunicado_publicado").count() == 1
    assert "Nuevo comunicado" not in capsys.readouterr().out


def test_emitir_no_commitea(db):
    emitir(
        db, "comunicado_publicado",
        consorcio_id=1, contexto=_ctx_comunicado(),
        actor_usuario_id=1, departamento_id=1,
    )
    db.rollback()
    assert db.query(Notificacion).filter_by(tipo="comunicado_publicado").count() == 0


def test_resolver_pendiente_apaga_todas_las_copias(db):
    otro_admin = Usuario(
        id=50, email="admin2@test.local", password_hash="x",
        rol=db.get(Usuario, 1).rol, administracion_id=1,
    )
    db.add(otro_admin)
    db.flush()

    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-1A", "titulo": "Filtración"},
        actor_usuario_id=2, entidad_id=10,
    )
    db.commit()
    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 2

    apagadas = resolver_pendiente(
        db, consorcio_id=1, entidad_tipo="peticion", entidad_id=10,
    )
    db.commit()
    assert apagadas == 2
    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 0


def test_resolver_pendiente_no_toca_otras_entidades(db):
    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-1A", "titulo": "A"},
        actor_usuario_id=2, entidad_id=10,
    )
    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-2B", "titulo": "B"},
        actor_usuario_id=3, entidad_id=11,
    )
    db.commit()

    resolver_pendiente(db, consorcio_id=1, entidad_tipo="peticion", entidad_id=10)
    db.commit()
    restantes = db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).all()
    assert [n.entidad_id for n in restantes] == [11]


def test_resolver_pendiente_no_cruza_consorcios(db, dos_consorcios):
    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-1A", "titulo": "A"},
        actor_usuario_id=2, entidad_id=10,
    )
    db.commit()
    apagadas = resolver_pendiente(
        db, consorcio_id=2, entidad_tipo="peticion", entidad_id=10,
    )
    assert apagadas == 0


def test_clave_desconocida_explota(db):
    import pytest

    with pytest.raises(KeyError):
        emitir(
            db, "no_existe",
            consorcio_id=1, contexto={}, actor_usuario_id=1,
        )

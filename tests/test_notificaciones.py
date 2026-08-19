"""Tests del módulo y router de notificaciones."""
from backend.models import Notificacion, Usuario


def test_emitir_persiste_la_campanita(db):
    from backend.notificaciones import emitir

    emitir(
        db, "peticion_estado_cambiado",
        consorcio_id=1,
        contexto={"titulo": "Test", "estado": "rechazada", "peticion_id": 10},
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()
    n = db.query(Notificacion).filter_by(tipo="peticion_estado_cambiado").one()
    assert n.usuario_id == 2
    assert n.leida is False
    assert n.link == "/peticiones"


def test_emitir_conversion_menciona_el_estado_crudo(db):
    from backend.notificaciones import emitir

    emitir(
        db, "peticion_estado_cambiado",
        consorcio_id=1,
        contexto={
            "titulo": "Test peti",
            "estado": "convertida_en_trabajo",
            "peticion_id": 10,
        },
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()
    n = db.query(Notificacion).filter_by(tipo="peticion_estado_cambiado").one()
    assert "convertida_en_trabajo" in n.mensaje


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


def test_notificacion_guarda_tipo_y_entidad(db):
    from backend.models import Notificacion

    n = Notificacion(
        consorcio_id=1,
        usuario_id=2,
        tipo="peticion_nueva",
        mensaje="X",
        link="/peticiones",
        entidad_tipo="peticion",
        entidad_id=10,
    )
    db.add(n)
    db.commit()
    assert n.tipo == "peticion_nueva"
    assert n.entidad_tipo == "peticion"
    assert n.entidad_id == 10


def test_preferencia_notificacion_unica_por_usuario_y_tipo(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from backend.models import PreferenciaNotificacion

    db.add(PreferenciaNotificacion(usuario_id=2, tipo="comunicado_publicado", email_activo=False))
    db.commit()

    db.add(PreferenciaNotificacion(usuario_id=2, tipo="comunicado_publicado", email_activo=True))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_listado_filtra_por_consorcio_activo(client, headers_admin, db, dos_consorcios):
    from backend.models import Notificacion

    db.add(Notificacion(consorcio_id=1, usuario_id=1, tipo="peticion_nueva", mensaje="del 1"))
    db.add(Notificacion(consorcio_id=2, usuario_id=1, tipo="peticion_nueva", mensaje="del 2"))
    db.commit()

    r = client.get("/notificaciones", headers=headers_admin)
    assert r.status_code == 200
    mensajes = [n["mensaje"] for n in r.json()]
    assert "del 1" in mensajes
    assert "del 2" not in mensajes


def test_listado_expone_el_tipo(client, headers_depto_a, db):
    from backend.models import Notificacion

    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="comunicado_publicado", mensaje="X"))
    db.commit()
    r = client.get("/notificaciones", headers=headers_depto_a)
    assert r.json()[0]["tipo"] == "comunicado_publicado"


def test_listado_solo_no_leidas(client, headers_depto_a, db):
    from backend.models import Notificacion

    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje="pendiente", leida=False))
    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje="vista", leida=True))
    db.commit()

    r = client.get("/notificaciones?solo_no_leidas=true", headers=headers_depto_a)
    assert [n["mensaje"] for n in r.json()] == ["pendiente"]


def test_listado_busca_por_texto_sin_distinguir_mayusculas(client, headers_depto_a, db):
    from backend.models import Notificacion

    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje="Corte de AGUA"))
    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje="Reunión"))
    db.commit()

    r = client.get("/notificaciones?q=agua", headers=headers_depto_a)
    assert [n["mensaje"] for n in r.json()] == ["Corte de AGUA"]


def test_listado_pagina_con_offset(client, headers_depto_a, db):
    from backend.models import Notificacion

    for i in range(5):
        db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje=f"n{i}"))
    db.commit()

    primera = client.get("/notificaciones?limit=2", headers=headers_depto_a).json()
    segunda = client.get("/notificaciones?limit=2&offset=2", headers=headers_depto_a).json()
    assert len(primera) == 2
    assert len(segunda) == 2
    assert {n["id"] for n in primera}.isdisjoint({n["id"] for n in segunda})


def test_contador_reporta_otros_consorcios(client, db, dos_consorcios):
    """Un admin de una administración con dos consorcios ve el contador del otro."""
    from backend.auth import create_access_token
    from backend.models import Consorcio, Notificacion, Rol

    # Mover el consorcio 2 bajo la administración 1: mismo admin, dos edificios.
    db.get(Consorcio, 2).administracion_id = 1
    db.add(Notificacion(consorcio_id=1, usuario_id=1, tipo="x", mensaje="acá", leida=False))
    db.add(Notificacion(consorcio_id=2, usuario_id=1, tipo="x", mensaje="allá", leida=False))
    db.add(Notificacion(consorcio_id=2, usuario_id=1, tipo="x", mensaje="allá2", leida=False))
    db.commit()

    token = create_access_token(user_id=1, rol=Rol.administracion, departamento_id=None)
    headers = {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}

    r = client.get("/notificaciones/no-leidas-count", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"count": 1, "otros_consorcios": 2}


def test_contador_de_depto_no_tiene_otros_consorcios(client, headers_depto_a, db):
    from backend.models import Notificacion

    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje="X", leida=False))
    db.commit()
    r = client.get("/notificaciones/no-leidas-count", headers=headers_depto_a)
    assert r.json()["otros_consorcios"] == 0


def test_marcar_todas_alcanza_solo_al_consorcio_activo(client, db, dos_consorcios):
    from backend.auth import create_access_token
    from backend.models import Consorcio, Notificacion, Rol

    db.get(Consorcio, 2).administracion_id = 1
    db.add(Notificacion(consorcio_id=1, usuario_id=1, tipo="x", mensaje="acá", leida=False))
    n2 = Notificacion(consorcio_id=2, usuario_id=1, tipo="x", mensaje="allá", leida=False)
    db.add(n2)
    db.commit()

    token = create_access_token(user_id=1, rol=Rol.administracion, departamento_id=None)
    headers = {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}

    r = client.post("/notificaciones/marcar-todas-leidas", headers=headers)
    assert r.status_code == 204
    db.refresh(n2)
    assert n2.leida is False

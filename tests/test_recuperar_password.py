"""Recuperación de contraseña por email.

Lo que se protege acá, además del circuito feliz:
  - no revelar qué emails están registrados,
  - que el token sea de un solo uso y venza,
  - que en la base nunca quede el token en claro.
"""
from datetime import datetime, timedelta, timezone

import pytest

from backend.models import TokenRecuperacion, Usuario


def test_el_modelo_guarda_hash_vencimiento_y_uso(db_session):
    token = TokenRecuperacion(
        usuario_id=1,
        token_hash="a" * 64,
        expira_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(token)
    db_session.commit()

    guardado = db_session.get(TokenRecuperacion, token.id)
    assert guardado.usado_at is None
    assert guardado.creado_at is not None


def test_dos_tokens_no_pueden_compartir_hash(db_session):
    """El hash es la llave de canje: si se repitiera, un canje afectaría a dos
    usuarios."""
    from sqlalchemy.exc import IntegrityError

    vence = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.add(TokenRecuperacion(usuario_id=1, token_hash="b" * 64, expira_at=vence))
    db_session.commit()

    db_session.add(TokenRecuperacion(usuario_id=2, token_hash="b" * 64, expira_at=vence))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- Logica del token, sin HTTP de por medio -------------------------------


def test_emitir_token_devuelve_el_claro_y_guarda_solo_el_hash(db_session):
    from backend import recuperacion

    usuario = db_session.get(Usuario, 2)

    claro = recuperacion.emitir_token(db_session, usuario)

    assert claro and len(claro) >= 32
    guardado = db_session.query(TokenRecuperacion).one()
    assert guardado.token_hash != claro
    assert guardado.token_hash == recuperacion.hashear(claro)


def test_canjear_token_devuelve_el_usuario_y_lo_marca_usado(db_session):
    from backend import recuperacion

    usuario = db_session.get(Usuario, 2)
    claro = recuperacion.emitir_token(db_session, usuario)

    canjeado = recuperacion.canjear_token(db_session, claro)

    assert canjeado.id == usuario.id
    assert db_session.query(TokenRecuperacion).one().usado_at is not None


def test_un_token_no_se_puede_canjear_dos_veces(db_session):
    from backend import recuperacion

    usuario = db_session.get(Usuario, 2)
    claro = recuperacion.emitir_token(db_session, usuario)
    recuperacion.canjear_token(db_session, claro)

    assert recuperacion.canjear_token(db_session, claro) is None


def test_un_token_vencido_no_se_canjea(db_session, monkeypatch):
    from backend import recuperacion
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "RECUPERACION_TOKEN_MINUTOS", -1)
    usuario = db_session.get(Usuario, 2)
    claro = recuperacion.emitir_token(db_session, usuario)

    assert recuperacion.canjear_token(db_session, claro) is None


def test_un_token_inventado_no_se_canjea(db_session):
    from backend import recuperacion

    assert recuperacion.canjear_token(db_session, "token-que-nadie-emitio") is None


def test_emitir_invalida_los_tokens_anteriores_del_usuario(db_session):
    """Pedir un link nuevo tiene que dejar sin efecto el anterior: si no, un
    link viejo reenviado o filtrado sigue sirviendo."""
    from backend import recuperacion

    usuario = db_session.get(Usuario, 2)
    primero = recuperacion.emitir_token(db_session, usuario)
    recuperacion.emitir_token(db_session, usuario)

    assert recuperacion.canjear_token(db_session, primero) is None


def test_el_limite_por_hora_corta_los_pedidos(db_session, monkeypatch):
    from backend import recuperacion
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "RECUPERACION_MAX_POR_HORA", 2)
    usuario = db_session.get(Usuario, 2)

    assert recuperacion.emitir_token(db_session, usuario) is not None
    assert recuperacion.emitir_token(db_session, usuario) is not None
    assert recuperacion.emitir_token(db_session, usuario) is None


# --- Los dos endpoints publicos --------------------------------------------

EMAIL_DEPTO = "a@test.local"


def _token_del_email(capsys) -> str:
    """Sin SMTP configurado, mail_service imprime el mensaje a consola: de ahi
    se lee el link que le llegaria al usuario."""
    salida = capsys.readouterr().out
    assert "?token=" in salida, f"el email no traia link:\n{salida}"
    return salida.split("?token=")[1].split()[0].strip()


def test_pedir_recuperacion_de_un_email_registrado_responde_202(client, db_session):
    r = client.post("/auth/recuperar-password", json={"email": EMAIL_DEPTO})

    assert r.status_code == 202
    assert db_session.query(TokenRecuperacion).count() == 1


def test_pedir_recuperacion_de_un_email_inexistente_responde_igual(client, db_session):
    """No se puede distinguir un email registrado de uno que no lo esta: si no,
    el formulario se convierte en un verificador de cuentas."""
    registrado = client.post("/auth/recuperar-password", json={"email": EMAIL_DEPTO})
    inexistente = client.post(
        "/auth/recuperar-password", json={"email": "nadie@ejemplo.com"}
    )

    assert inexistente.status_code == registrado.status_code == 202
    assert inexistente.json() == registrado.json()
    # Y no se emitio token para el inexistente: solo esta el del registrado.
    assert db_session.query(TokenRecuperacion).count() == 1


def test_el_email_lleva_el_link_al_frontend_con_el_token(client, capsys):
    client.post("/auth/recuperar-password", json={"email": EMAIL_DEPTO})

    salida = capsys.readouterr().out
    assert "/restablecer-password?token=" in salida


def test_restablecer_con_token_valido_cambia_la_password(client, db_session, capsys):
    from backend.security import verify_password

    client.post("/auth/recuperar-password", json={"email": EMAIL_DEPTO})
    token = _token_del_email(capsys)

    r = client.post(
        "/auth/restablecer-password",
        json={"token": token, "new_password": "password-nueva-2026"},
    )

    assert r.status_code == 204
    db_session.expire_all()
    usuario = db_session.get(Usuario, 2)
    assert verify_password("password-nueva-2026", usuario.password_hash)


def test_restablecer_baja_el_flag_de_cambio_obligatorio(client, db_session, capsys):
    """Si no se bajara, el usuario resetea su clave y sigue recibiendo 403 en
    todo endpoint operacional."""
    usuario = db_session.get(Usuario, 2)
    usuario.must_change_password = True
    db_session.commit()

    client.post("/auth/recuperar-password", json={"email": EMAIL_DEPTO})
    token = _token_del_email(capsys)
    client.post(
        "/auth/restablecer-password",
        json={"token": token, "new_password": "password-nueva-2026"},
    )

    db_session.expire_all()
    assert db_session.get(Usuario, 2).must_change_password is False


def test_restablecer_con_token_invalido_responde_400(client):
    r = client.post(
        "/auth/restablecer-password",
        json={"token": "no-existe", "new_password": "password-nueva-2026"},
    )
    assert r.status_code == 400


def test_restablecer_dos_veces_con_el_mismo_link_falla_la_segunda(client, capsys):
    client.post("/auth/recuperar-password", json={"email": EMAIL_DEPTO})
    token = _token_del_email(capsys)
    cuerpo = {"token": token, "new_password": "password-nueva-2026"}

    assert client.post("/auth/restablecer-password", json=cuerpo).status_code == 204
    assert client.post("/auth/restablecer-password", json=cuerpo).status_code == 400


def test_restablecer_con_password_corta_responde_400(client, capsys):
    client.post("/auth/recuperar-password", json={"email": EMAIL_DEPTO})
    token = _token_del_email(capsys)

    r = client.post(
        "/auth/restablecer-password", json={"token": token, "new_password": "corta"}
    )
    assert r.status_code == 400


def test_despues_de_restablecer_se_puede_entrar_con_la_nueva(client, capsys):
    client.post("/auth/recuperar-password", json={"email": EMAIL_DEPTO})
    token = _token_del_email(capsys)
    client.post(
        "/auth/restablecer-password",
        json={"token": token, "new_password": "password-nueva-2026"},
    )

    r = client.post(
        "/auth/login",
        json={"email": EMAIL_DEPTO, "password": "password-nueva-2026"},
    )
    assert r.status_code == 200


def test_un_usuario_dado_de_baja_no_recibe_link(client, db_session):
    """`activa=False` es una baja: no debe poder recuperar el acceso sola."""
    usuario = db_session.get(Usuario, 2)
    usuario.activa = False
    db_session.commit()

    r = client.post("/auth/recuperar-password", json={"email": EMAIL_DEPTO})

    assert r.status_code == 202  # misma respuesta, sin revelar nada
    assert db_session.query(TokenRecuperacion).count() == 0

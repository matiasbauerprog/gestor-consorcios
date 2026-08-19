"""El correo sale después de la respuesta y nunca puede romper la operación."""
from backend.notificaciones.correo import MailPendiente, encolar, enviar_uno


def test_enviar_uno_manda_por_mail_service(capsys):
    enviar_uno(MailPendiente(
        to="a@test.local", subject="Asunto", body="Cuerpo",
        clave_evento="comunicado_publicado",
    ))
    salida = capsys.readouterr().out
    assert "a@test.local" in salida
    assert "Asunto" in salida


def test_enviar_uno_no_levanta_si_el_envio_explota(monkeypatch, db):
    from backend import database as db_module
    from backend.notificaciones import correo

    def _explota(**kwargs):
        raise RuntimeError("SMTP caído")

    monkeypatch.setattr(correo, "enviar_email", _explota)
    monkeypatch.setattr(db_module, "SessionLocal", lambda: db)

    # Sin assert a propósito: que la llamada retorne sin propagar la
    # excepción ES la aserción — es el contrato de la función con
    # BackgroundTasks. Si explota, pytest la marca como error igual.
    enviar_uno(MailPendiente(
        to="a@test.local", subject="X", body="Y",
        clave_evento="comunicado_publicado",
    ))


def test_enviar_uno_registra_el_error_con_codigo(monkeypatch, db):
    from backend import database as db_module
    from backend.models import ErrorRegistrado
    from backend.notificaciones import correo

    def _explota(**kwargs):
        raise RuntimeError("SMTP caído")

    monkeypatch.setattr(correo, "enviar_email", _explota)
    monkeypatch.setattr(db_module, "SessionLocal", lambda: db)

    antes = db.query(ErrorRegistrado).count()
    enviar_uno(MailPendiente(
        to="a@test.local", subject="X", body="Y",
        clave_evento="comunicado_publicado",
    ))
    registrados = db.query(ErrorRegistrado).all()
    assert len(registrados) == antes + 1
    assert registrados[-1].ruta == "notificaciones/comunicado_publicado"


def test_encolar_sin_background_tasks_envia_en_linea(capsys):
    encolar(None, [MailPendiente(
        to="b@test.local", subject="Inline", body="Z",
        clave_evento="comunicado_publicado",
    )])
    assert "b@test.local" in capsys.readouterr().out


def test_encolar_con_background_tasks_agrega_una_tarea_por_mail():
    from fastapi import BackgroundTasks

    tareas = BackgroundTasks()
    encolar(tareas, [
        MailPendiente(to="a@x", subject="1", body="c", clave_evento="comunicado_publicado"),
        MailPendiente(to="b@x", subject="2", body="c", clave_evento="comunicado_publicado"),
    ])
    assert len(tareas.tasks) == 2


def test_encolar_lista_vacia_no_agrega_tareas():
    from fastapi import BackgroundTasks

    tareas = BackgroundTasks()
    encolar(tareas, [])
    assert len(tareas.tasks) == 0

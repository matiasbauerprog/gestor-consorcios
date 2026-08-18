"""Comando de diagnóstico del correo saliente.

No prueba que el correo llegue —eso depende del proveedor y del DNS— sino que
el comando reporte con precisión qué configuración está usando y qué pasó, que
es lo único que sirve cuando algo no anda el día del despliegue.
"""
from backend import probar_email


def test_avisa_que_esta_en_modo_consola_si_no_hay_servidor(monkeypatch, capsys):
    """Sin SMTP_HOST el mensaje se imprime y nunca sale: si el comando dijera
    'enviado' igual, daría por buena una configuración que no manda nada."""
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "SMTP_HOST", "")

    codigo = probar_email.main(["vecino@ejemplo.com"])

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "modo consola" in salida.lower()


def test_muestra_la_configuracion_sin_revelar_la_clave(monkeypatch, capsys):
    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(settings, "SMTP_USER", "resend")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "re_una_clave_secreta_12345")
    monkeypatch.setattr(probar_email, "enviar_email", lambda **kw: True)

    probar_email.main(["vecino@ejemplo.com"])

    salida = capsys.readouterr().out
    assert "smtp.resend.com" in salida
    assert "re_una_clave_secreta_12345" not in salida, "no debe imprimir la clave"
    assert "***" in salida


def test_devuelve_cero_cuando_el_envio_sale_bien(monkeypatch, capsys):
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(probar_email, "enviar_email", lambda **kw: True)

    assert probar_email.main(["vecino@ejemplo.com"]) == 0


def test_devuelve_uno_cuando_el_envio_falla(monkeypatch, capsys):
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(probar_email, "enviar_email", lambda **kw: False)

    codigo = probar_email.main(["vecino@ejemplo.com"])

    assert codigo == 1
    assert "no se pudo" in capsys.readouterr().out.lower()


def test_sin_destinatario_explica_como_usarlo(capsys):
    codigo = probar_email.main([])

    assert codigo == 2
    assert "uso:" in capsys.readouterr().out.lower()

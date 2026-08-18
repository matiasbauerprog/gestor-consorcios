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

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.resend.com")
    # El default de Settings es `consorcio@local`, que no es una direccion
    # real: hay que fijar una valida o la validacion de forma corta antes.
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "noreply@midominio.com.ar")
    monkeypatch.setattr(probar_email, "enviar_email", lambda **kw: True)

    assert probar_email.main(["vecino@ejemplo.com"]) == 0


def test_devuelve_uno_cuando_el_envio_falla(monkeypatch, capsys):
    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "noreply@midominio.com.ar")
    monkeypatch.setattr(probar_email, "enviar_email", lambda **kw: False)

    codigo = probar_email.main(["vecino@ejemplo.com"])

    assert codigo == 1
    assert "no se pudo" in capsys.readouterr().out.lower()


def test_sin_destinatario_explica_como_usarlo(capsys):
    codigo = probar_email.main([])

    assert codigo == 2
    assert "uso:" in capsys.readouterr().out.lower()


def test_detiene_el_envio_si_el_remitente_no_tiene_arroba(monkeypatch, capsys):
    """Un punto en lugar de la arroba (`noreply.dominio.com`) es un error de
    tipeo fácil y el servidor lo rechaza con un mensaje poco claro. Se corta
    antes, diciendo exactamente qué está mal."""
    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "noreply.midominio.com.ar")
    enviados = []
    monkeypatch.setattr(probar_email, "enviar_email", lambda **kw: enviados.append(kw))

    codigo = probar_email.main(["vecino@ejemplo.com"])

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "@" in salida and "remitente" in salida.lower()
    assert enviados == [], "no debe intentar mandar con un remitente invalido"


def test_detiene_el_envio_si_el_destinatario_no_tiene_arroba(monkeypatch, capsys):
    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "noreply@midominio.com.ar")
    enviados = []
    monkeypatch.setattr(probar_email, "enviar_email", lambda **kw: enviados.append(kw))

    codigo = probar_email.main(["vecino.ejemplo.com"])

    assert codigo == 1
    assert enviados == []


def test_dominios_lista_lo_que_resend_ve_con_esa_clave(monkeypatch, capsys):
    """El caso que motiva esto: el panel muestra el dominio verificado pero el
    envío lo rechaza. Casi siempre es que la clave pertenece a otra cuenta, o
    que lo verificado es un subdominio y se manda desde el dominio pelado."""
    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "re_clave")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "noreply@midominio.com.ar")
    monkeypatch.setattr(
        probar_email,
        "_pedir_dominios",
        lambda clave: [
            {"name": "notificaciones.midominio.com.ar", "status": "verified"},
            {"name": "otro.com", "status": "pending"},
        ],
    )

    codigo = probar_email.main(["--dominios"])

    salida = capsys.readouterr().out
    assert codigo == 1, "el remitente no coincide con ningun dominio verificado"
    assert "notificaciones.midominio.com.ar" in salida
    assert "verified" in salida
    assert "midominio.com.ar" in salida
    # Y explica el desajuste concreto en vez de dejarlo a la vista nada mas.
    assert "no coincide" in salida.lower()


def test_dominios_confirma_cuando_el_remitente_si_corresponde(monkeypatch, capsys):
    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "re_clave")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "noreply@midominio.com.ar")
    monkeypatch.setattr(
        probar_email,
        "_pedir_dominios",
        lambda clave: [{"name": "midominio.com.ar", "status": "verified"}],
    )

    codigo = probar_email.main(["--dominios"])

    assert codigo == 0
    assert "corresponde" in capsys.readouterr().out.lower()


def test_dominios_avisa_si_la_clave_no_ve_ninguno(monkeypatch, capsys):
    """Lista vacía = la clave es de otra cuenta, o de una sin dominios."""
    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "re_clave")
    monkeypatch.setattr(probar_email, "_pedir_dominios", lambda clave: [])

    codigo = probar_email.main(["--dominios"])

    salida = capsys.readouterr().out.lower()
    assert codigo == 1
    assert "ningún dominio" in salida or "ningun dominio" in salida


def test_dominios_explica_que_un_403_es_una_clave_solo_de_envio(monkeypatch, capsys):
    """403 con una clave de envío es lo normal, no un error de configuración:
    las claves de Resend son "sending only" por defecto y no pueden leer la
    lista de dominios. Decir "la clave está mal" manda a arreglar lo que anda."""
    import urllib.error

    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "re_clave")

    def _403(clave):
        raise urllib.error.HTTPError(
            "https://api.resend.com/domains", 403, "Forbidden", {}, None
        )

    monkeypatch.setattr(probar_email, "_pedir_dominios", _403)

    codigo = probar_email.main(["--dominios"])

    salida = capsys.readouterr().out.lower()
    assert codigo == 0, "una clave solo de envio no es una falla"
    assert "sólo de envío" in salida or "solo de envio" in salida
    assert "está mal" not in salida


def test_dominios_distingue_un_401_que_si_es_clave_invalida(monkeypatch, capsys):
    import urllib.error

    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "re_clave")

    def _401(clave):
        raise urllib.error.HTTPError(
            "https://api.resend.com/domains", 401, "Unauthorized", {}, None
        )

    monkeypatch.setattr(probar_email, "_pedir_dominios", _401)

    codigo = probar_email.main(["--dominios"])

    assert codigo == 1
    assert "no es válida" in capsys.readouterr().out.lower()


def test_un_remitente_valido_deja_seguir(monkeypatch, capsys):
    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "noreply@midominio.com.ar")
    monkeypatch.setattr(probar_email, "enviar_email", lambda **kw: True)

    assert probar_email.main(["vecino@ejemplo.com"]) == 0

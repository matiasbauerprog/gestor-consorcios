"""Tests de Settings (backend/config.py)."""
from backend.config import Settings


def test_cors_origins_se_parsea_desde_string_separado_por_comas():
    s = Settings(
        SECRET_KEY="x",
        CORS_ORIGINS="https://app.example.com, https://admin.example.com,",
    )
    assert s.cors_origins_list == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_cors_origins_default_incluye_dev_localhost():
    s = Settings(SECRET_KEY="x")
    assert "http://localhost:5173" in s.cors_origins_list


def test_cors_origin_regex_permite_puertos_arbitrarios_localhost():
    import re

    s = Settings(SECRET_KEY="x")
    pattern = re.compile(s.CORS_ORIGIN_REGEX)
    assert pattern.match("http://localhost:5179")
    assert pattern.match("http://127.0.0.1:5179")
    assert pattern.match("http://localhost:3000")


import pytest
from pydantic import ValidationError

from backend.config import Settings


def test_demo_mode_default_es_false():
    s = Settings(SECRET_KEY="x")
    assert s.DEMO_MODE is False


def test_demo_mode_true_con_database_url_demo_es_valido():
    s = Settings(SECRET_KEY="x", DEMO_MODE=True, DATABASE_URL="sqlite:///./demo.db")
    assert s.DEMO_MODE is True


def test_demo_mode_true_con_database_url_de_produccion_falla():
    # Candado anti-produccion: DEMO_MODE expone /auth/demo-login, que emite
    # tokens sin credenciales. Si la base no es la del demo, no arranca.
    with pytest.raises(ValidationError, match="DEMO_MODE"):
        Settings(SECRET_KEY="x", DEMO_MODE=True,
                 DATABASE_URL="postgresql://user:pass@host/consorcio_prod")


def test_demo_mode_false_no_exige_nada_de_la_database_url():
    s = Settings(SECRET_KEY="x", DEMO_MODE=False,
                 DATABASE_URL="postgresql://user:pass@host/consorcio_prod")
    assert s.DEMO_MODE is False


def test_demo_mode_true_con_database_url_vacia_usa_fallback_demo():
    s = Settings(SECRET_KEY="x", DEMO_MODE=True, DATABASE_URL="")
    assert s.DEMO_MODE is True
    assert s.DATABASE_URL == "sqlite:///./demo.db"


def test_demo_mode_false_con_database_url_vacia_usa_fallback_default():
    s = Settings(SECRET_KEY="x", DEMO_MODE=False, DATABASE_URL="")
    assert s.DEMO_MODE is False
    assert s.DATABASE_URL == "sqlite:///./consorcio.db"


def test_demo_mode_fuerza_modo_consola_aunque_haya_smtp(monkeypatch, capsys):
    # Un demo publico nunca debe mandar mail real, ni siquiera si alguien
    # configura SMTP_HOST en el servicio por error.
    #
    # No usamos un monkeypatch que "explota" (raise) para detectar la llamada:
    # enviar_email() envuelve el bloque SMTP en un `except Exception` genérico
    # (backend/mail_service.py), así que cualquier excepción ahí adentro queda
    # silenciada y el test pasaría igual con o sin el candado. En cambio,
    # registramos las llamadas a smtplib.SMTP y aseguramos que la lista quede
    # vacía: eso sí distingue "nunca se intentó conectar" de "se conectó y
    # algo falló después".
    from backend import mail_service

    settings_demo = Settings(
        SECRET_KEY="x", DEMO_MODE=True, DATABASE_URL="sqlite:///./demo.db",
        SMTP_HOST="smtp.gmail.com", SMTP_USER="u", SMTP_PASSWORD="p",
    )
    monkeypatch.setattr(mail_service, "get_settings", lambda: settings_demo)

    llamadas_smtp = []
    monkeypatch.setattr(
        mail_service.smtplib, "SMTP",
        lambda *a, **kw: llamadas_smtp.append((a, kw)),
    )

    mail_service.enviar_email("dest@demo.local", "Asunto", "Cuerpo")
    assert llamadas_smtp == [], "no debe abrirse conexión SMTP en modo demo"
    assert "dest@demo.local" in capsys.readouterr().out


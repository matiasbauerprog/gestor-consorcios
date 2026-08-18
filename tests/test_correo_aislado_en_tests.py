"""El suite nunca debe mandar correo de verdad.

Sin esta guarda, quien tenga `SMTP_HOST` configurado en su `.env` —lo normal
apenas se da de alta el proveedor— corre `pytest` y el suite le manda mensajes
reales: gasta cuota, ensucia la reputación del dominio y, si algún test usa una
dirección de una persona, le escribe.

`conftest.py` fuerza `SMTP_HOST` vacío por eso, igual que ya forzaba
`DEMO_MODE=false`.
"""
import os


def test_el_suite_corre_con_el_correo_en_modo_consola():
    from backend.config import get_settings

    assert os.environ.get("SMTP_HOST") == "", (
        "conftest debe forzar SMTP_HOST vacío antes de importar la app"
    )
    assert get_settings().SMTP_HOST == "", (
        "con SMTP_HOST cargado, el suite manda correo real por la cuenta de "
        "quien lo corra"
    )


def test_enviar_email_no_sale_a_la_red_durante_el_suite(capsys):
    """La comprobación de verdad: que `enviar_email` imprima en vez de conectar."""
    from backend.mail_service import enviar_email

    assert enviar_email(to="nadie@ejemplo.com", subject="prueba", body="cuerpo") is True
    assert "[EMAIL CONSOLE MODE]" in capsys.readouterr().out

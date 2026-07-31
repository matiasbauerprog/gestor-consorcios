"""Tests del módulo de envío de email."""
from unittest.mock import patch, MagicMock

import pytest

from backend.mail_service import enviar_email


def test_modo_console_devuelve_true_y_loggea(capsys):
    """Si SMTP_HOST está vacío, modo console: loggea y devuelve True."""
    with patch("backend.mail_service.get_settings") as mock_settings:
        mock_settings.return_value.SMTP_HOST = ""
        mock_settings.return_value.SMTP_FROM_EMAIL = "from@local"
        mock_settings.return_value.SMTP_FROM_NAME = "Test"
        ok = enviar_email(
            to="depto@example.com",
            subject="Test asunto",
            body="Cuerpo del email",
            attachments=[],
        )
    captured = capsys.readouterr()
    assert ok is True
    assert "depto@example.com" in captured.out
    assert "Test asunto" in captured.out


def test_modo_smtp_llama_send_message():
    """Con SMTP_HOST seteado, llama a smtplib.SMTP.send_message."""
    with patch("backend.mail_service.get_settings") as mock_settings, \
         patch("backend.mail_service.smtplib.SMTP") as mock_smtp_cls:
        mock_settings.return_value.SMTP_HOST = "smtp.test.local"
        mock_settings.return_value.SMTP_PORT = 587
        mock_settings.return_value.SMTP_USER = "user"
        mock_settings.return_value.SMTP_PASSWORD = "pass"
        mock_settings.return_value.SMTP_FROM_EMAIL = "from@local"
        mock_settings.return_value.SMTP_FROM_NAME = "Test"
        # DEMO_MODE fuerza consola (ver mail_service.py); sin fijarlo explícito
        # el MagicMock devuelve un atributo truthy y este test de modo SMTP
        # caería por error en modo consola.
        mock_settings.return_value.DEMO_MODE = False

        mock_smtp_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp_instance

        ok = enviar_email(
            to="depto@example.com",
            subject="Test",
            body="Body",
            attachments=[],
        )

    assert ok is True
    mock_smtp_instance.send_message.assert_called_once()


def test_attachment_construye_multipart():
    """Con attachments, el mensaje incluye el PDF como parte."""
    with patch("backend.mail_service.get_settings") as mock_settings:
        mock_settings.return_value.SMTP_HOST = ""
        mock_settings.return_value.SMTP_FROM_EMAIL = "from@local"
        mock_settings.return_value.SMTP_FROM_NAME = "Test"

        ok = enviar_email(
            to="depto@example.com",
            subject="Boleta",
            body="Adjunto",
            attachments=[("boleta.pdf", b"%PDF-fake-bytes", "application/pdf")],
        )
    assert ok is True

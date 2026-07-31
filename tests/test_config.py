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


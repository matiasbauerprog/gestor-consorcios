import pytest

from backend.models import Rol, Usuario
from backend.security import verify_password


def test_seed_crea_super_admin_si_no_existe(db_empty, monkeypatch):
    from backend.seed_super_admin import seed
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "sa@x.com")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "1234567890ab")

    seed(db_empty)

    u = db_empty.query(Usuario).filter(Usuario.email == "sa@x.com").first()
    assert u is not None
    assert u.rol == Rol.super_admin
    assert u.administracion_id is None
    assert u.departamento_id is None


def test_seed_es_idempotente(db_empty, monkeypatch):
    from backend.seed_super_admin import seed
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "sa@x.com")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "1234567890ab")

    seed(db_empty)
    seed(db_empty)

    count = db_empty.query(Usuario).filter(Usuario.rol == Rol.super_admin).count()
    assert count == 1


def test_seed_falla_sin_env_vars(db_empty, monkeypatch):
    monkeypatch.delenv("SUPER_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("SUPER_ADMIN_PASSWORD", raising=False)
    from backend.seed_super_admin import seed

    with pytest.raises(RuntimeError, match="SUPER_ADMIN_EMAIL"):
        seed(db_empty)


def test_seed_force_resetea_password(db_empty, monkeypatch):
    from backend.seed_super_admin import seed

    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "sa@x.com")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "primera-pass-12")
    seed(db_empty)

    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "segunda-pass-12")
    seed(db_empty, force=True)

    u = db_empty.query(Usuario).filter(Usuario.email == "sa@x.com").first()
    assert verify_password("segunda-pass-12", u.password_hash)

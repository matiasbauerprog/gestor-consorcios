"""Tests del super-admin: CRUD administraciones + reset-password."""
from tests.conftest import TEST_PASSWORD


# ---------------------------------------------------------------------------
# GET listado / detalle
# ---------------------------------------------------------------------------


def test_get_administraciones_sin_token_devuelve_401(client):
    r = client.get("/super-admin/administraciones")
    assert r.status_code == 401


def test_get_administraciones_como_admin_devuelve_403(client, headers_admin):
    r = client.get("/super-admin/administraciones", headers=headers_admin)
    assert r.status_code == 403


def test_get_administraciones_como_super_admin_devuelve_lista(client, headers_super_admin):
    r = client.get("/super-admin/administraciones", headers=headers_super_admin)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(a["razon_social"] == "Administración Test" for a in data)


def test_get_administracion_by_id_devuelve_detalle(client, headers_super_admin):
    r = client.get("/super-admin/administraciones/1", headers=headers_super_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert body["cuit"] == "30-11111111-1"


def test_get_administracion_inexistente_devuelve_404(client, headers_super_admin):
    r = client.get("/super-admin/administraciones/9999", headers=headers_super_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST — crear administración
# ---------------------------------------------------------------------------


def _body_crear(cuit="30-77777777-7", email="boss@estudio-nuevo.local"):
    return {
        "razon_social": "Estudio Nuevo SA",
        "cuit": cuit,
        "email_contacto": "info@estudio-nuevo.local",
        "admin_email": email,
        "admin_password_inicial": "temporal-2026",
    }


def test_post_administracion_crea_tenant_y_usuario_admin(client, headers_super_admin, db):
    r = client.post(
        "/super-admin/administraciones",
        json=_body_crear(),
        headers=headers_super_admin,
    )
    assert r.status_code == 201
    out = r.json()
    assert out["razon_social"] == "Estudio Nuevo SA"
    assert out["activa"] is True
    assert out["plan"] == "free"

    from backend.models import Rol, Usuario
    u = db.query(Usuario).filter_by(email="boss@estudio-nuevo.local").one()
    assert u.rol == Rol.administracion
    assert u.administracion_id == out["id"]
    assert u.must_change_password is True


def test_post_administracion_cuit_duplicado_devuelve_409(client, headers_super_admin):
    body = _body_crear(cuit="30-11111111-1")  # cuit del seed
    r = client.post("/super-admin/administraciones", json=body, headers=headers_super_admin)
    assert r.status_code == 409


def test_post_administracion_email_admin_duplicado_devuelve_409(client, headers_super_admin):
    body = _body_crear(email="admin@test.local")  # user del seed
    r = client.post("/super-admin/administraciones", json=body, headers=headers_super_admin)
    assert r.status_code == 409


def test_post_administracion_genera_audit_log(client, headers_super_admin, db):
    r = client.post(
        "/super-admin/administraciones",
        json=_body_crear(cuit="30-33333333-3", email="audit@e.local"),
        headers=headers_super_admin,
    )
    assert r.status_code == 201
    from backend.models import AuditLogSuperAdmin
    entries = db.query(AuditLogSuperAdmin).filter_by(accion="crear_admin").all()
    assert len(entries) >= 1


# ---------------------------------------------------------------------------
# PATCH
# ---------------------------------------------------------------------------


def test_patch_administracion_cambia_razon_social(client, headers_super_admin, db):
    r = client.patch(
        "/super-admin/administraciones/1",
        json={"razon_social": "Administración Test Editada"},
        headers=headers_super_admin,
    )
    assert r.status_code == 200
    assert r.json()["razon_social"] == "Administración Test Editada"

    from backend.models import AuditLogSuperAdmin
    entries = db.query(AuditLogSuperAdmin).filter_by(accion="editar_admin").all()
    assert len(entries) >= 1


def test_patch_administracion_inexistente_devuelve_404(client, headers_super_admin):
    r = client.patch(
        "/super-admin/administraciones/9999",
        json={"razon_social": "X"},
        headers=headers_super_admin,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Toggle suspender
# ---------------------------------------------------------------------------


def test_suspender_administracion_toggle_activa(client, headers_super_admin, db):
    r1 = client.post(
        "/super-admin/administraciones/1/suspender", headers=headers_super_admin
    )
    assert r1.status_code == 200
    assert r1.json()["activa"] is False

    r2 = client.post(
        "/super-admin/administraciones/1/suspender", headers=headers_super_admin
    )
    assert r2.status_code == 200
    assert r2.json()["activa"] is True

    from backend.models import AuditLogSuperAdmin
    acciones = {e.accion for e in db.query(AuditLogSuperAdmin).all()}
    assert "suspender_admin" in acciones
    assert "reactivar_admin" in acciones


def test_login_de_usuario_de_administracion_suspendida_devuelve_403(
    client, headers_super_admin
):
    client.post(
        "/super-admin/administraciones/1/suspender", headers=headers_super_admin
    )
    r = client.post(
        "/auth/login",
        json={"email": "admin@test.local", "password": TEST_PASSWORD},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "administracion_suspendida"


# ---------------------------------------------------------------------------
# Reset password
# ---------------------------------------------------------------------------


def test_reset_password_genera_password_temporal_y_setea_must_change(
    client, headers_super_admin, db
):
    from backend.models import Usuario
    r = client.post(
        "/super-admin/administraciones/1/reset-password/1",
        headers=headers_super_admin,
    )
    assert r.status_code == 200
    out = r.json()
    assert "password_temporal" in out
    assert len(out["password_temporal"]) >= 12

    db.expire_all()
    u = db.get(Usuario, 1)
    assert u.must_change_password is True

    from backend.models import AuditLogSuperAdmin
    entries = db.query(AuditLogSuperAdmin).filter_by(accion="reset_password").all()
    assert len(entries) >= 1


def test_reset_password_usuario_de_otra_administracion_devuelve_404(
    client, headers_super_admin, db
):
    from backend.models import Administracion, Rol, Usuario
    from backend.security import hash_password
    a2 = Administracion(razon_social="A2", cuit="30-4-2", email_contacto="a2@x.local")
    db.add(a2)
    db.flush()
    u2 = Usuario(
        email="u2@x.local",
        password_hash=hash_password("x-pass-1234"),
        rol=Rol.administracion,
        administracion_id=a2.id,
    )
    db.add(u2)
    db.commit()

    r = client.post(
        f"/super-admin/administraciones/1/reset-password/{u2.id}",
        headers=headers_super_admin,
    )
    assert r.status_code == 404


def test_reset_password_administracion_inexistente_devuelve_404(
    client, headers_super_admin
):
    r = client.post(
        "/super-admin/administraciones/9999/reset-password/1",
        headers=headers_super_admin,
    )
    assert r.status_code == 404

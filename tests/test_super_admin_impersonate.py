"""Tests del super-admin: impersonate start/end + middleware audit."""


# ---------------------------------------------------------------------------
# Impersonate start
# ---------------------------------------------------------------------------


def test_impersonate_start_devuelve_jwt_15min(client, headers_super_admin, db):
    body = {"usuario_id": 2, "motivo": "Ticket #123 - no aparecen expensas julio"}
    r = client.post(
        "/super-admin/impersonate/start", json=body, headers=headers_super_admin
    )
    assert r.status_code == 200
    out = r.json()
    assert "access_token" in out
    assert out["expires_in"] == 15 * 60
    assert out["impersonated_user_id"] == 2

    from backend.models import AuditLogSuperAdmin
    e = (
        db.query(AuditLogSuperAdmin)
        .filter_by(accion="impersonate_start")
        .order_by(AuditLogSuperAdmin.id.desc())
        .first()
    )
    assert e is not None
    assert e.motivo == body["motivo"]


def test_impersonate_start_motivo_muy_corto_devuelve_400(client, headers_super_admin):
    body = {"usuario_id": 2, "motivo": "corto"}
    r = client.post(
        "/super-admin/impersonate/start", json=body, headers=headers_super_admin
    )
    assert r.status_code == 400


def test_impersonate_start_sin_motivo_devuelve_400(client, headers_super_admin):
    r = client.post(
        "/super-admin/impersonate/start",
        json={"usuario_id": 2},
        headers=headers_super_admin,
    )
    assert r.status_code == 400


def test_impersonate_start_super_admin_no_impersonable(
    client, headers_super_admin, db
):
    from backend.models import Rol, Usuario
    from backend.security import hash_password
    sa2 = Usuario(
        email="sa2@x.local",
        password_hash=hash_password("x-pass-1234"),
        rol=Rol.super_admin,
    )
    db.add(sa2)
    db.commit()

    r = client.post(
        "/super-admin/impersonate/start",
        json={"usuario_id": sa2.id, "motivo": "no deberia funcionar"},
        headers=headers_super_admin,
    )
    assert r.status_code == 400


def test_impersonate_start_usuario_inexistente_devuelve_404(client, headers_super_admin):
    r = client.post(
        "/super-admin/impersonate/start",
        json={"usuario_id": 9999, "motivo": "usuario inexistente test"},
        headers=headers_super_admin,
    )
    assert r.status_code == 404


def test_impersonate_activo_no_puede_iniciar_otro(client, headers_super_admin):
    body = {"usuario_id": 2, "motivo": "primer impersonate valido"}
    r1 = client.post(
        "/super-admin/impersonate/start", json=body, headers=headers_super_admin
    )
    assert r1.status_code == 200
    token = r1.json()["access_token"]
    headers_imp = {"Authorization": f"Bearer {token}"}

    # Con el JWT impersonado, el rol efectivo es Rol.departamento → 403.
    r2 = client.post(
        "/super-admin/impersonate/start", json=body, headers=headers_imp
    )
    assert r2.status_code == 403


def test_jwt_impersonado_funciona_como_el_user_impersonado(client, headers_super_admin):
    body = {"usuario_id": 2, "motivo": "test que el token temporal opera"}
    r = client.post(
        "/super-admin/impersonate/start", json=body, headers=headers_super_admin
    )
    token = r.json()["access_token"]
    headers_imp = {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}

    # user 2 es depto A → puede ver peticiones.
    r_get = client.get("/peticiones", headers=headers_imp)
    assert r_get.status_code == 200


# ---------------------------------------------------------------------------
# Impersonate end
# ---------------------------------------------------------------------------


def test_impersonate_end_revoca_el_token(client, headers_super_admin):
    body = {"usuario_id": 2, "motivo": "test para revocar el token"}
    r1 = client.post(
        "/super-admin/impersonate/start", json=body, headers=headers_super_admin
    )
    token = r1.json()["access_token"]
    headers_imp = {"Authorization": f"Bearer {token}"}

    r_end = client.post("/super-admin/impersonate/end", headers=headers_imp)
    assert r_end.status_code == 204

    r_after = client.get(
        "/peticiones",
        headers={**headers_imp, "X-Consorcio-Id": "1"},
    )
    assert r_after.status_code == 401


def test_impersonate_end_sin_claim_impersonated_by_devuelve_400(
    client, headers_admin
):
    r = client.post("/super-admin/impersonate/end", headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Middleware audit — mutaciones durante impersonate
# ---------------------------------------------------------------------------


def test_mutacion_durante_impersonate_queda_en_audit_log(
    client, headers_super_admin, db
):
    body = {"usuario_id": 1, "motivo": "test audit middleware mutacion"}
    r_start = client.post(
        "/super-admin/impersonate/start", json=body, headers=headers_super_admin
    )
    token = r_start.json()["access_token"]
    headers_imp = {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}

    # POST /amenities (admin puede) durante impersonate.
    r_post = client.post(
        "/amenities",
        json={"nombre": "Amenity durante impersonate", "descripcion": "audit"},
        headers=headers_imp,
    )
    assert r_post.status_code == 201

    from backend.models import AuditLogSuperAdmin
    entries = (
        db.query(AuditLogSuperAdmin).filter_by(accion="impersonate_mutacion").all()
    )
    assert len(entries) >= 1
    match = [e for e in entries if "/amenities" in (e.detalles or "")]
    assert match


def test_get_durante_impersonate_NO_queda_en_audit_log(
    client, headers_super_admin, db
):
    body = {"usuario_id": 1, "motivo": "test audit no loguea GET"}
    r_start = client.post(
        "/super-admin/impersonate/start", json=body, headers=headers_super_admin
    )
    token = r_start.json()["access_token"]
    headers_imp = {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}

    from backend.models import AuditLogSuperAdmin
    before = (
        db.query(AuditLogSuperAdmin).filter_by(accion="impersonate_mutacion").count()
    )

    client.get("/amenities", headers=headers_imp)
    client.get("/expensas", headers=headers_imp)

    after = (
        db.query(AuditLogSuperAdmin).filter_by(accion="impersonate_mutacion").count()
    )
    assert after == before


def test_mutacion_sin_impersonate_NO_queda_en_audit_log(
    client, headers_admin, db
):
    from backend.models import AuditLogSuperAdmin
    before = (
        db.query(AuditLogSuperAdmin).filter_by(accion="impersonate_mutacion").count()
    )
    r = client.post(
        "/amenities",
        json={"nombre": "Amenity sin impersonate", "descripcion": "control"},
        headers=headers_admin,
    )
    assert r.status_code == 201
    after = (
        db.query(AuditLogSuperAdmin).filter_by(accion="impersonate_mutacion").count()
    )
    assert after == before

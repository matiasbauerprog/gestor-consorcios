"""Tests del super-admin: helpers audit, métricas, endpoint audit-log."""
import json

from backend.audit import crear_audit_log_entry, redactar_payload
from backend.models import AuditLogSuperAdmin


# ---------------------------------------------------------------------------
# Helpers audit
# ---------------------------------------------------------------------------


def test_redactar_reemplaza_claves_sensibles():
    payload = {
        "email": "a@b.com",
        "password": "secreta123",
        "api_token": "abcd",
        "detalle": {"secret_key": "XYZ", "algo": "ok"},
    }
    r = redactar_payload(payload)
    assert r["email"] == "a@b.com"
    assert r["password"] == "[REDACTED]"
    assert r["api_token"] == "[REDACTED]"
    assert r["detalle"]["secret_key"] == "[REDACTED]"
    assert r["detalle"]["algo"] == "ok"


def test_redactar_trunca_a_500_caracteres():
    payload = {"big": "x" * 600}
    r = redactar_payload(payload)
    s = r if isinstance(r, str) else json.dumps(r)
    assert len(s) <= 500


def test_crear_audit_log_entry_persiste(db):
    # Crear el super admin referenciado por la FK.
    from backend.models import Rol, Usuario
    from backend.security import hash_password
    db.add(Usuario(
        id=5, email="sa-audit@test.local",
        password_hash=hash_password("x"), rol=Rol.super_admin,
    ))
    db.commit()

    entry = crear_audit_log_entry(
        db,
        super_admin_usuario_id=5,
        accion="test_accion",
        administracion_id_afectada=1,
        motivo="test motivo",
        detalles={"path": "/foo"},
    )
    db.commit()
    assert entry.id is not None
    assert entry.accion == "test_accion"
    row = db.get(AuditLogSuperAdmin, entry.id)
    assert row.motivo == "test motivo"
    assert row.administracion_id_afectada == 1
    assert "/foo" in (row.detalles or "")


# ---------------------------------------------------------------------------
# GET /super-admin/metricas
# ---------------------------------------------------------------------------


def test_get_metricas_sin_token_devuelve_401(client):
    r = client.get("/super-admin/metricas")
    assert r.status_code == 401


def test_get_metricas_como_admin_devuelve_403(client, headers_admin):
    r = client.get("/super-admin/metricas", headers=headers_admin)
    assert r.status_code == 403


def test_get_metricas_devuelve_agregados(client, headers_super_admin):
    r = client.get("/super-admin/metricas", headers=headers_super_admin)
    assert r.status_code == 200
    m = r.json()
    assert set(m.keys()) >= {
        "administraciones",
        "consorcios",
        "departamentos",
        "expensas_ultimo_mes",
        "impersonates_ultimos_30_dias",
    }
    assert m["administraciones"]["total"] >= 1
    assert m["consorcios"]["total"] >= 1
    assert m["departamentos"]["total"] >= 2  # seed tiene 2 deptos


def test_metricas_administraciones_cuenta_activas_y_suspendidas(
    client, headers_super_admin
):
    # Estado inicial: 1 activa, 0 suspendidas.
    r1 = client.get("/super-admin/metricas", headers=headers_super_admin)
    activas0 = r1.json()["administraciones"]["activas"]
    susp0 = r1.json()["administraciones"]["suspendidas"]

    client.post(
        "/super-admin/administraciones/1/suspender", headers=headers_super_admin
    )
    r2 = client.get("/super-admin/metricas", headers=headers_super_admin)
    assert r2.json()["administraciones"]["activas"] == activas0 - 1
    assert r2.json()["administraciones"]["suspendidas"] == susp0 + 1


# ---------------------------------------------------------------------------
# GET /super-admin/audit-log
# ---------------------------------------------------------------------------


def test_get_audit_log_devuelve_lista_ordenada_desc(client, headers_super_admin, db):
    for i in range(3):
        crear_audit_log_entry(
            db, super_admin_usuario_id=5, accion=f"test_orden_{i}"
        )
    db.commit()

    r = client.get("/super-admin/audit-log", headers=headers_super_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 3
    fechas = [entry["fecha"] for entry in data]
    assert fechas == sorted(fechas, reverse=True)


def test_audit_log_filtra_por_accion(client, headers_super_admin, db):
    crear_audit_log_entry(
        db, super_admin_usuario_id=5, accion="ejemplo_unico_test_filtro"
    )
    db.commit()

    r = client.get(
        "/super-admin/audit-log?accion=ejemplo_unico_test_filtro",
        headers=headers_super_admin,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert all(e["accion"] == "ejemplo_unico_test_filtro" for e in data)


def test_audit_log_filtra_por_administracion_id(client, headers_super_admin, db):
    crear_audit_log_entry(
        db,
        super_admin_usuario_id=5,
        accion="test_admin_filter",
        administracion_id_afectada=1,
    )
    db.commit()

    r = client.get(
        "/super-admin/audit-log?administracion_id=1",
        headers=headers_super_admin,
    )
    assert r.status_code == 200
    data = r.json()
    assert all(e["administracion_id_afectada"] == 1 for e in data)


def test_audit_log_pagina_con_limit_offset(client, headers_super_admin, db):
    for i in range(10):
        crear_audit_log_entry(db, super_admin_usuario_id=5, accion="pag_test")
    db.commit()

    r1 = client.get(
        "/super-admin/audit-log?accion=pag_test&limit=5",
        headers=headers_super_admin,
    )
    r2 = client.get(
        "/super-admin/audit-log?accion=pag_test&limit=5&offset=5",
        headers=headers_super_admin,
    )
    assert len(r1.json()) == 5
    assert len(r2.json()) == 5
    ids1 = {e["id"] for e in r1.json()}
    ids2 = {e["id"] for e in r2.json()}
    assert ids1.isdisjoint(ids2)


def test_get_audit_log_como_admin_devuelve_403(client, headers_admin):
    r = client.get("/super-admin/audit-log", headers=headers_admin)
    assert r.status_code == 403

"""Tests de módulos habilitables por administración (super_admin)."""
from backend.modulos import MODULOS


def test_administracion_tiene_columna_modulos(db_session):
    from backend.models import Administracion

    a = db_session.get(Administracion, 1)
    assert a is not None
    assert a.modulos_habilitados is None  # NULL = todos habilitados


def test_catalogo_de_modulos():
    from backend.modulos import MODULOS

    assert MODULOS == (
        "comunicacion", "cobranzas", "gastos", "finanzas",
        "operacion", "espacios_comunes", "reportes", "personal",
    )


def test_modulos_habilitados_de_null_devuelve_todos(db_session):
    from backend.models import Administracion
    from backend.modulos import MODULOS, modulos_habilitados_de

    a = db_session.get(Administracion, 1)
    assert modulos_habilitados_de(a) == set(MODULOS)


def test_modulos_habilitados_de_parsea_json(db_session):
    from backend.models import Administracion
    from backend.modulos import modulos_habilitados_de

    a = db_session.get(Administracion, 1)
    a.modulos_habilitados = '["gastos", "cobranzas"]'
    assert modulos_habilitados_de(a) == {"gastos", "cobranzas"}


def test_get_modulos_default_todos(client, headers_super_admin):
    r = client.get("/super-admin/administraciones/1/modulos", headers=headers_super_admin)
    assert r.status_code == 200
    body = r.json()
    assert set(body["disponibles"]) == set(body["habilitados"])
    assert "gastos" in body["habilitados"]


def test_put_modulos_persiste_subset(client, headers_super_admin):
    r = client.put(
        "/super-admin/administraciones/1/modulos",
        json={"habilitados": ["comunicacion", "cobranzas"]},
        headers=headers_super_admin,
    )
    assert r.status_code == 200
    assert sorted(r.json()["habilitados"]) == ["cobranzas", "comunicacion"]

    r2 = client.get("/super-admin/administraciones/1/modulos", headers=headers_super_admin)
    assert sorted(r2.json()["habilitados"]) == ["cobranzas", "comunicacion"]


def test_put_modulo_desconocido_devuelve_400(client, headers_super_admin):
    r = client.put(
        "/super-admin/administraciones/1/modulos",
        json={"habilitados": ["inventado"]},
        headers=headers_super_admin,
    )
    assert r.status_code == 400


def test_put_modulos_admin_normal_devuelve_403(client, headers_admin):
    r = client.put(
        "/super-admin/administraciones/1/modulos",
        json={"habilitados": ["gastos"]},
        headers=headers_admin,
    )
    assert r.status_code == 403


def test_get_modulos_administracion_inexistente_devuelve_404(client, headers_super_admin):
    r = client.get("/super-admin/administraciones/999/modulos", headers=headers_super_admin)
    assert r.status_code == 404


def test_put_modulos_genera_audit_log(client, headers_super_admin):
    client.put(
        "/super-admin/administraciones/1/modulos",
        json={"habilitados": ["gastos"]},
        headers=headers_super_admin,
    )
    r = client.get(
        "/super-admin/audit-log?accion=editar_modulos", headers=headers_super_admin
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert r.json()[0]["administracion_id_afectada"] == 1


# ---------------------------------------------------------------------------
# Task 4: Gate 403 modulo_no_habilitado en routers
# ---------------------------------------------------------------------------


def _deshabilitar(client, headers_super_admin, *modulos_activos):
    r = client.put(
        "/super-admin/administraciones/1/modulos",
        json={"habilitados": list(modulos_activos)},
        headers=headers_super_admin,
    )
    assert r.status_code == 200


def test_modulo_deshabilitado_devuelve_403(client, headers_admin, headers_super_admin):
    _deshabilitar(client, headers_super_admin, "comunicacion")  # gastos queda OFF
    r = client.get("/gastos", headers=headers_admin)
    assert r.status_code == 403
    assert r.json()["detail"] == "modulo_no_habilitado"


def test_modulo_habilitado_sigue_funcionando(client, headers_admin, headers_super_admin):
    _deshabilitar(client, headers_super_admin, "comunicacion")
    r = client.get("/comunicados", headers=headers_admin)
    assert r.status_code == 200


def test_gate_aplica_tambien_a_departamentos(client, headers_depto_a, headers_super_admin):
    _deshabilitar(client, headers_super_admin, "gastos")  # cobranzas OFF
    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    assert r.status_code == 403
    assert r.json()["detail"] == "modulo_no_habilitado"


def test_rehabilitar_modulo_restaura_acceso(client, headers_admin, headers_super_admin):
    _deshabilitar(client, headers_super_admin, "comunicacion")
    assert client.get("/gastos", headers=headers_admin).status_code == 403
    _deshabilitar(client, headers_super_admin, *MODULOS)
    assert client.get("/gastos", headers=headers_admin).status_code == 200


# ---------------------------------------------------------------------------
# Task 5: ConsorcioOut expone modulos_habilitados
# ---------------------------------------------------------------------------


def test_consorcio_out_incluye_modulos(client, headers_admin, headers_super_admin):
    r = client.get("/consorcios/1", headers=headers_admin)
    assert r.status_code == 200
    assert set(r.json()["modulos_habilitados"]) == set(MODULOS)

    _deshabilitar(client, headers_super_admin, "comunicacion", "cobranzas")
    r2 = client.get("/consorcios/1", headers=headers_admin)
    assert sorted(r2.json()["modulos_habilitados"]) == ["cobranzas", "comunicacion"]

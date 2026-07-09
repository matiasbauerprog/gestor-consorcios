"""Tests de aislamiento multitenant (Plan A - Task 35).

Verifica que:
1. Un usuario no puede operar contra un consorcio ajeno (spoofing con
   X-Consorcio-Id apunta a otro tenant → 403).
2. Los listados están naturalmente scoped: crear recursos en c1 no los hace
   visibles en c2 y viceversa.
3. El acceso por ID a un recurso de otro consorcio devuelve 404 (no 200 con
   datos de otro tenant).
"""
import pytest


# ---------------------------------------------------------------------------
# 1) Spoofing: X-Consorcio-Id apunta a un consorcio ajeno → 403
# ---------------------------------------------------------------------------

# Endpoints operacionales GET que deben rechazar el spoof con 403.
# Se testea con el header spoof: admin de c1 con X-Consorcio-Id=2.
_ENDPOINTS_GET_A_TESTEAR = [
    "/departamentos",
    "/expensas",
    "/comunicados",
    "/amenities",
    "/reservas",
    "/gastos",
    "/gastos-habituales",
    "/proveedores",
    "/clases-prorrateo",
    "/cajas",
    "/transferencias-caja",
    "/empleados",
    "/haberes",
    "/conceptos-liquidacion",
    "/liquidaciones",
    "/peticiones",
    "/trabajos",
    "/configuracion",
]


@pytest.mark.parametrize("path", _ENDPOINTS_GET_A_TESTEAR)
def test_spoof_admin_c1_sobre_c2_devuelve_403(client, dos_consorcios, path):
    """Admin de c1 con X-Consorcio-Id=2 (consorcio ajeno) → 403."""
    r = client.get(path, headers=dos_consorcios["headers_admin_c1_spoof_c2"])
    assert r.status_code == 403, (
        f"{path} debería rechazar spoof cross-tenant con 403, devolvió {r.status_code}"
    )


@pytest.mark.parametrize("path", _ENDPOINTS_GET_A_TESTEAR)
def test_spoof_admin_c2_sobre_c1_devuelve_403(client, dos_consorcios, path):
    """Admin de c2 con X-Consorcio-Id=1 (consorcio ajeno) → 403."""
    r = client.get(path, headers=dos_consorcios["headers_admin_c2_spoof_c1"])
    assert r.status_code == 403, (
        f"{path} debería rechazar spoof cross-tenant con 403, devolvió {r.status_code}"
    )


# ---------------------------------------------------------------------------
# 2) Aislamiento de listados: recursos creados en un consorcio no aparecen en el otro
# ---------------------------------------------------------------------------


def test_listar_departamentos_no_muestra_deptos_de_otro_consorcio(client, dos_consorcios):
    r1 = client.get("/departamentos", headers=dos_consorcios["headers_admin_c1"])
    r2 = client.get("/departamentos", headers=dos_consorcios["headers_admin_c2"])
    assert r1.status_code == 200 and r2.status_code == 200

    ids_c1 = {d["id"] for d in r1.json()}
    ids_c2 = {d["id"] for d in r2.json()}

    # Depto 1 y 2 son de c1 (sembrados); depto 3 es de c2.
    assert 1 in ids_c1 and 2 in ids_c1
    assert 3 not in ids_c1
    assert 3 in ids_c2
    assert 1 not in ids_c2 and 2 not in ids_c2


def test_crear_amenity_en_c2_no_aparece_en_c1(client, dos_consorcios):
    r_post = client.post(
        "/amenities",
        json={"nombre": "Parrilla C2", "descripcion": "solo c2"},
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r_post.status_code == 201
    amenity_c2_id = r_post.json()["id"]

    # Listado desde c1 NO debe verlo.
    r_c1 = client.get("/amenities", headers=dos_consorcios["headers_admin_c1"])
    assert r_c1.status_code == 200
    ids_c1 = {a["id"] for a in r_c1.json()}
    assert amenity_c2_id not in ids_c1

    # Listado desde c2 SÍ debe verlo.
    r_c2 = client.get("/amenities", headers=dos_consorcios["headers_admin_c2"])
    ids_c2 = {a["id"] for a in r_c2.json()}
    assert amenity_c2_id in ids_c2


def test_listar_comunicados_de_c1_no_aparecen_en_c2(client, dos_consorcios):
    # Comunicado id=200 sembrado en c1.
    r_c2 = client.get("/comunicados", headers=dos_consorcios["headers_admin_c2"])
    assert r_c2.status_code == 200
    ids_c2 = {c["id"] for c in r_c2.json()}
    assert 200 not in ids_c2


def test_listar_amenities_seed_solo_visible_en_c1(client, dos_consorcios):
    # Amenities sembrados id=300 y 301 pertenecen a c1.
    r_c1 = client.get("/amenities", headers=dos_consorcios["headers_admin_c1"])
    r_c2 = client.get("/amenities", headers=dos_consorcios["headers_admin_c2"])

    ids_c1 = {a["id"] for a in r_c1.json()}
    ids_c2 = {a["id"] for a in r_c2.json()}

    assert 300 in ids_c1 and 301 in ids_c1
    assert 300 not in ids_c2 and 301 not in ids_c2


# ---------------------------------------------------------------------------
# 3) Acceso por ID a recursos ajenos: debe devolver 404 (no 200)
# ---------------------------------------------------------------------------


def test_get_amenity_de_c1_desde_c2_devuelve_404(client, dos_consorcios):
    # Amenity 300 pertenece a c1.
    r = client.get("/amenities/300", headers=dos_consorcios["headers_admin_c2"])
    # /amenities/{id} no existe como GET, pero PATCH y DELETE sí. Probamos PATCH.
    r_patch = client.patch(
        "/amenities/300",
        json={"descripcion": "hack"},
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r_patch.status_code == 404


def test_patch_departamento_de_c1_desde_c2_devuelve_404(client, dos_consorcios):
    # Depto 1 pertenece a c1.
    r = client.patch(
        "/departamentos/1",
        json={"descripcion": "hack"},
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r.status_code == 404


def test_get_reserva_de_c1_desde_c2_devuelve_404(client, dos_consorcios):
    # Reserva 400 sembrada en c1.
    r = client.get("/reservas/400", headers=dos_consorcios["headers_admin_c2"])
    assert r.status_code == 404


def test_delete_amenity_ajeno_no_lo_borra(client, dos_consorcios):
    r_delete = client.delete(
        "/amenities/300",
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r_delete.status_code == 404

    # Sigue visible en c1.
    r_c1 = client.get("/amenities", headers=dos_consorcios["headers_admin_c1"])
    ids_c1 = {a["id"] for a in r_c1.json()}
    assert 300 in ids_c1


# ---------------------------------------------------------------------------
# 4) Header ausente / inválido
# ---------------------------------------------------------------------------


def test_endpoint_operacional_sin_header_devuelve_400(client, headers_admin):
    # headers_admin trae X-Consorcio-Id. Removemos.
    headers_sin_cid = {k: v for k, v in headers_admin.items() if k != "X-Consorcio-Id"}
    r = client.get("/departamentos", headers=headers_sin_cid)
    assert r.status_code == 400


def test_endpoint_operacional_con_header_no_numerico_devuelve_400(client, headers_admin):
    headers_bad = dict(headers_admin)
    headers_bad["X-Consorcio-Id"] = "abc"
    r = client.get("/departamentos", headers=headers_bad)
    assert r.status_code == 400

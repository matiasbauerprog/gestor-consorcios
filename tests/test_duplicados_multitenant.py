"""Unicidad por consorcio: el mismo código/nombre/CUIT/CUIL puede existir en
consorcios distintos. Los checks de duplicado no deben ser globales."""


def test_clase_prorrateo_mismo_codigo_en_otro_consorcio(client, dos_consorcios):
    # c1 ya tiene la clase "A" (seed id=500); c2 debe poder crear la suya.
    r = client.post(
        "/clases-prorrateo",
        json={"codigo": "A", "nombre": "Ordinarias c2"},
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r.status_code == 201


def test_clase_prorrateo_duplicada_mismo_consorcio_409(client, dos_consorcios):
    r = client.post(
        "/clases-prorrateo",
        json={"codigo": "A", "nombre": "Duplicada"},
        headers=dos_consorcios["headers_admin_c1"],
    )
    assert r.status_code == 409


def test_proveedor_mismo_cuit_en_otro_consorcio(client, dos_consorcios):
    # c1 tiene el proveedor seed con cuit 30-12345678-9.
    r = client.post(
        "/proveedores",
        json={"razon_social": "Proveedor compartido SA", "cuit": "30-12345678-9"},
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r.status_code == 201


def test_proveedor_duplicado_mismo_consorcio_409(client, dos_consorcios):
    r = client.post(
        "/proveedores",
        json={"razon_social": "Duplicado", "cuit": "30-12345678-9"},
        headers=dos_consorcios["headers_admin_c1"],
    )
    assert r.status_code == 409


def test_amenity_mismo_nombre_en_otro_consorcio(client, dos_consorcios):
    # c1 tiene "SUM" (seed id=300).
    r = client.post(
        "/amenities",
        json={"nombre": "SUM"},
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r.status_code == 201


def test_haber_mismo_nombre_en_otro_consorcio(client, dos_consorcios):
    # c1 tiene "Básico Test" (seed id=940).
    r = client.post(
        "/haberes",
        json={"nombre": "Básico Test", "tipo": "monto_fijo", "valor_default": 1000.0, "orden": 1},
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r.status_code == 201


def test_concepto_mismo_nombre_en_otro_consorcio(client, dos_consorcios):
    # c1 tiene "Jubilación Test" (seed id=950). El concepto exige proveedor del
    # consorcio: creo uno en c2 primero.
    rp = client.post(
        "/proveedores",
        json={"razon_social": "AFIP c2", "cuit": "30-88888800-1"},
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert rp.status_code == 201
    r = client.post(
        "/conceptos-liquidacion",
        json={
            "nombre": "Jubilación Test", "tipo": "descuento", "porcentaje": 11.0,
            "proveedor_id": rp.json()["id"], "orden": 1,
        },
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r.status_code == 201


def test_empleado_mismo_cuil_en_otro_consorcio(client, dos_consorcios):
    # c1 tiene el empleado seed cuil 20-30000000-3.
    rp = client.post(
        "/proveedores",
        json={"razon_social": "Sindicato c2", "cuit": "30-88888800-2"},
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert rp.status_code == 201
    r = client.post(
        "/empleados",
        json={
            "nombre_completo": "Mismo Encargado",
            "cuil": "20-30000000-3",
            "categoria": "encargado_permanente_sin_vivienda",
            "fecha_ingreso": "2024-01-01",
            "fecha_egreso": None,
            "sueldo_basico": 900000,
            "proveedor_id": rp.json()["id"],
        },
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r.status_code == 201

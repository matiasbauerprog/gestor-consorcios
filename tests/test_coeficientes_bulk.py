"""Tests para PUT /coeficientes: reemplazo atómico de toda la matriz del consorcio."""


def _payload(items):
    return {"coeficientes": items}


def test_put_bulk_sin_token_devuelve_401(client):
    r = client.put("/coeficientes", json=_payload([]))
    assert r.status_code == 401


def test_put_bulk_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.put("/coeficientes", json=_payload([]), headers=headers_depto_a)
    assert r.status_code == 403


def test_put_bulk_como_representante_devuelve_403(client, headers_representante):
    r = client.put("/coeficientes", json=_payload([]), headers=headers_representante)
    assert r.status_code == 403


def test_put_bulk_reemplaza_matriz_completa(client, headers_admin, db_session):
    from backend.models import CoeficienteDepartamento

    payload = _payload([
        {"departamento_id": 1, "clase_prorrateo_id": 500, "porcentaje": 60.0},
        {"departamento_id": 2, "clase_prorrateo_id": 500, "porcentaje": 40.0},
    ])
    r = client.put("/coeficientes", json=payload, headers=headers_admin)
    assert r.status_code == 200

    persistidos = db_session.query(CoeficienteDepartamento).filter(
        CoeficienteDepartamento.consorcio_id == 1
    ).all()
    persistidos_map = {(c.departamento_id, c.clase_prorrateo_id): c.porcentaje for c in persistidos}
    assert persistidos_map == {(1, 500): 60.0, (2, 500): 40.0}


def test_put_bulk_vacio_borra_todos_los_coefs_del_consorcio(client, headers_admin, db_session):
    from backend.models import CoeficienteDepartamento

    # Sembrar coefs previos.
    db_session.add_all([
        CoeficienteDepartamento(
            consorcio_id=1, departamento_id=1, clase_prorrateo_id=500, porcentaje=50.0
        ),
        CoeficienteDepartamento(
            consorcio_id=1, departamento_id=2, clase_prorrateo_id=500, porcentaje=50.0
        ),
    ])
    db_session.commit()

    r = client.put("/coeficientes", json=_payload([]), headers=headers_admin)
    assert r.status_code == 200
    remaining = db_session.query(CoeficienteDepartamento).filter(
        CoeficienteDepartamento.consorcio_id == 1
    ).count()
    assert remaining == 0


def test_put_bulk_depto_de_otro_consorcio_devuelve_404(client, dos_consorcios):
    # Admin de c1 intenta setear un coef sobre el depto 3 (que es de c2).
    payload = _payload([
        {"departamento_id": 3, "clase_prorrateo_id": 500, "porcentaje": 100.0},
    ])
    r = client.put(
        "/coeficientes", json=payload, headers=dos_consorcios["headers_admin_c1"]
    )
    assert r.status_code == 404


def test_put_bulk_clase_de_otro_consorcio_devuelve_404(client, dos_consorcios, db_session):
    from backend.models import ClaseProrrateo
    # Clase 700 en el consorcio 2.
    db_session.add(ClaseProrrateo(
        id=700, consorcio_id=2, codigo="X", nombre="Exclusiva c2", activa=True
    ))
    db_session.commit()

    payload = _payload([
        {"departamento_id": 1, "clase_prorrateo_id": 700, "porcentaje": 100.0},
    ])
    r = client.put(
        "/coeficientes", json=payload, headers=dos_consorcios["headers_admin_c1"]
    )
    assert r.status_code == 404


def test_put_bulk_no_toca_coefs_de_otro_consorcio(client, dos_consorcios, db_session):
    from backend.models import ClaseProrrateo, CoeficienteDepartamento

    # Sembrar clase y coef en c2 que NO debe ser tocado.
    db_session.add(ClaseProrrateo(
        id=750, consorcio_id=2, codigo="A", nombre="Ordinarias c2", activa=True
    ))
    db_session.flush()
    db_session.add(CoeficienteDepartamento(
        consorcio_id=2, departamento_id=3, clase_prorrateo_id=750, porcentaje=100.0
    ))
    db_session.commit()

    # Admin de c1 reemplaza los suyos.
    payload = _payload([
        {"departamento_id": 1, "clase_prorrateo_id": 500, "porcentaje": 100.0},
    ])
    r = client.put(
        "/coeficientes", json=payload, headers=dos_consorcios["headers_admin_c1"]
    )
    assert r.status_code == 200

    # El coef del c2 sigue intacto.
    intactos = db_session.query(CoeficienteDepartamento).filter(
        CoeficienteDepartamento.consorcio_id == 2
    ).count()
    assert intactos == 1


def test_put_bulk_porcentaje_negativo_devuelve_400(client, headers_admin):
    payload = _payload([
        {"departamento_id": 1, "clase_prorrateo_id": 500, "porcentaje": -1.0},
    ])
    r = client.put("/coeficientes", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_put_bulk_porcentaje_mayor_a_100_devuelve_400(client, headers_admin):
    payload = _payload([
        {"departamento_id": 1, "clase_prorrateo_id": 500, "porcentaje": 100.5},
    ])
    r = client.put("/coeficientes", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_put_bulk_permite_sumas_distintas_de_100(client, headers_admin, db_session):
    """El backend no rechaza si la suma por clase != 100 — el reglamento manda."""
    from backend.models import CoeficienteDepartamento
    payload = _payload([
        {"departamento_id": 1, "clase_prorrateo_id": 500, "porcentaje": 30.0},
        {"departamento_id": 2, "clase_prorrateo_id": 500, "porcentaje": 40.0},
    ])
    r = client.put("/coeficientes", json=payload, headers=headers_admin)
    assert r.status_code == 200
    total = db_session.query(CoeficienteDepartamento).filter(
        CoeficienteDepartamento.consorcio_id == 1
    ).count()
    assert total == 2


def test_put_bulk_duplicado_depto_clase_devuelve_400(client, headers_admin):
    payload = _payload([
        {"departamento_id": 1, "clase_prorrateo_id": 500, "porcentaje": 50.0},
        {"departamento_id": 1, "clase_prorrateo_id": 500, "porcentaje": 70.0},
    ])
    r = client.put("/coeficientes", json=payload, headers=headers_admin)
    assert r.status_code == 400

"""Tests para POST /padron/importar: alta masiva unificada de deptos + usuarios."""


def _csv(rows, header=True):
    lines = []
    if header:
        lines.append("codigo,ubicacion,email")
    lines.extend(rows)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _upload(csv):
    return {"file": ("padron.csv", csv, "text/csv")}


def test_import_sin_token_devuelve_401(client):
    r = client.post("/padron/importar", files=_upload(_csv([])))
    assert r.status_code == 401


def test_import_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.post(
        "/padron/importar",
        files=_upload(_csv(["UF-9X,Piso 9 X,x@t.local"])),
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_import_crea_depto_y_usuario(client, headers_admin, db_session):
    from backend.models import Departamento, Usuario
    r = client.post(
        "/padron/importar",
        files=_upload(_csv(["UF-3C,Piso 3 C,juan@t.local"])),
        headers=headers_admin,
    )
    assert r.status_code == 200
    resultados = r.json()["resultados"]
    assert len(resultados) == 1
    item = resultados[0]
    assert item["depto_status"] == "creado"
    assert item["usuario_status"] == "creado"
    assert len(item["password_generada"]) >= 12

    d = db_session.query(Departamento).filter(
        Departamento.consorcio_id == 1, Departamento.codigo == "UF-3C"
    ).first()
    assert d is not None
    assert d.descripcion == "Piso 3 C"

    u = db_session.query(Usuario).filter(Usuario.email == "juan@t.local").first()
    assert u is not None
    assert u.departamento_id == d.id
    assert u.must_change_password is True


def test_import_reutiliza_depto_existente_por_codigo(client, headers_admin, db_session):
    """Un mismo código en dos filas debe crear el depto una sola vez y asignarle
    los usuarios de ambas filas."""
    from backend.models import Departamento, Usuario
    csv = _csv([
        "UF-4D,Piso 4 D,propietario@t.local",
        "UF-4D,Piso 4 D,inquilino@t.local",
    ])
    r = client.post("/padron/importar", files=_upload(csv), headers=headers_admin)
    assert r.status_code == 200
    resultados = r.json()["resultados"]
    assert resultados[0]["depto_status"] == "creado"
    assert resultados[1]["depto_status"] == "reutilizado"
    assert resultados[0]["usuario_status"] == "creado"
    assert resultados[1]["usuario_status"] == "creado"

    deptos = db_session.query(Departamento).filter(
        Departamento.consorcio_id == 1, Departamento.codigo == "UF-4D"
    ).all()
    assert len(deptos) == 1
    users = db_session.query(Usuario).filter(
        Usuario.departamento_id == deptos[0].id
    ).all()
    assert {u.email for u in users} == {"propietario@t.local", "inquilino@t.local"}


def test_import_email_vacio_solo_crea_depto(client, headers_admin, db_session):
    from backend.models import Departamento
    csv = _csv(["UF-VAC,Sin usuarios,"])
    r = client.post("/padron/importar", files=_upload(csv), headers=headers_admin)
    assert r.status_code == 200
    item = r.json()["resultados"][0]
    assert item["depto_status"] == "creado"
    assert item["usuario_status"] == "sin_usuario"
    assert item["password_generada"] is None

    d = db_session.query(Departamento).filter(Departamento.codigo == "UF-VAC").first()
    assert d is not None


def test_import_depto_previo_reutilizado(client, headers_admin, db_session):
    """Si el depto ya existe en la DB (seed), se reutiliza sin actualizar
    la ubicación existente."""
    from backend.models import Usuario
    csv = _csv(["UF-1A,ubicación ignorada,nuevo@t.local"])
    r = client.post("/padron/importar", files=_upload(csv), headers=headers_admin)
    assert r.status_code == 200
    item = r.json()["resultados"][0]
    assert item["depto_status"] == "reutilizado"
    assert item["usuario_status"] == "creado"

    u = db_session.query(Usuario).filter(Usuario.email == "nuevo@t.local").first()
    assert u is not None
    assert u.departamento_id == 1  # sigue apuntando al depto seed


def test_import_email_ya_existe_error(client, headers_admin):
    csv = _csv(["UF-1A,Piso 1 A,a@test.local"])  # a@test.local ya existe en el seed
    r = client.post("/padron/importar", files=_upload(csv), headers=headers_admin)
    assert r.status_code == 200
    item = r.json()["resultados"][0]
    assert item["usuario_status"] == "error"
    assert item["error"] == "email_duplicado"


def test_import_email_invalido_error(client, headers_admin):
    csv = _csv(["UF-9Y,Piso 9 Y,no-arroba"])
    r = client.post("/padron/importar", files=_upload(csv), headers=headers_admin)
    assert r.status_code == 200
    item = r.json()["resultados"][0]
    assert item["usuario_status"] == "error"
    assert item["error"] == "email_invalido"


def test_import_codigo_vacio_error(client, headers_admin):
    csv = _csv([",Sin código,x@t.local"])
    r = client.post("/padron/importar", files=_upload(csv), headers=headers_admin)
    assert r.status_code == 200
    item = r.json()["resultados"][0]
    assert item["depto_status"] == "error"
    assert item["error"] == "codigo_invalido"


def test_import_csv_sin_columnas_devuelve_400(client, headers_admin):
    r = client.post("/padron/importar", files=_upload(b"foo,bar\n1,2\n"), headers=headers_admin)
    assert r.status_code == 400


def test_import_csv_vacio_devuelve_400(client, headers_admin):
    r = client.post("/padron/importar", files=_upload(_csv([])), headers=headers_admin)
    assert r.status_code == 400


def test_import_scope_por_consorcio_activo(client, dos_consorcios, db_session):
    """Los deptos y usuarios se crean en el consorcio del X-Consorcio-Id."""
    from backend.models import Departamento
    csv = _csv(["UF-X1,Piso X 1,x1@t.local"])
    r = client.post(
        "/padron/importar",
        files=_upload(csv),
        headers=dos_consorcios["headers_admin_c2"],
    )
    assert r.status_code == 200
    deptos_c2 = db_session.query(Departamento).filter(
        Departamento.consorcio_id == 2, Departamento.codigo == "UF-X1"
    ).count()
    assert deptos_c2 == 1
    deptos_c1 = db_session.query(Departamento).filter(
        Departamento.consorcio_id == 1, Departamento.codigo == "UF-X1"
    ).count()
    assert deptos_c1 == 0

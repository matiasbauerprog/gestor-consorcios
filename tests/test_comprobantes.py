# ---------------------------------------------------------------------------
# GET /comprobantes
# ---------------------------------------------------------------------------


import pathlib
from datetime import date, timedelta
from backend.models import Comprobante, EstadoComprobante
from tests.conftest import VENC_1, VENC_2


def _crear_comprobante(db, departamento_id, fecha_pago, monto, estado):
    c = Comprobante(consorcio_id=1, departamento_id=departamento_id,
        fecha_pago=fecha_pago,
        monto=monto,
        archivo_path=None,
        estado=estado,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_listar_comprobantes_sin_token_devuelve_401(client):
    r = client.get("/comprobantes")
    assert r.status_code == 401


def test_listar_comprobantes_como_representante_devuelve_403(client, headers_representante):
    r = client.get("/comprobantes", headers=headers_representante)
    assert r.status_code == 403


def test_listar_comprobantes_admin_devuelve_todos(client, headers_admin, db_session):
    _crear_comprobante(db_session, 1, date(2026, 5, 5), 85000, EstadoComprobante.aprobado)
    _crear_comprobante(db_session, 2, date(2026, 5, 6), 92000, EstadoComprobante.pendiente_verificacion)

    r = client.get("/comprobantes", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_listar_comprobantes_admin_filtra_por_estado(client, headers_admin, db_session):
    _crear_comprobante(db_session, 1, date(2026, 5, 5), 85000, EstadoComprobante.aprobado)
    _crear_comprobante(db_session, 2, date(2026, 5, 6), 92000, EstadoComprobante.pendiente_verificacion)

    r = client.get("/comprobantes?estado=aprobado", headers=headers_admin)
    assert r.status_code == 200
    comprobantes = r.json()
    assert len(comprobantes) == 1
    assert comprobantes[0]["estado"] == "aprobado"


def test_listar_comprobantes_admin_filtra_por_departamento(client, headers_admin, db_session):
    _crear_comprobante(db_session, 1, date(2026, 5, 5), 85000, EstadoComprobante.aprobado)
    _crear_comprobante(db_session, 2, date(2026, 5, 6), 92000, EstadoComprobante.pendiente_verificacion)

    r = client.get("/comprobantes?departamento_id=1", headers=headers_admin)
    assert r.status_code == 200
    comprobantes = r.json()
    assert len(comprobantes) == 1
    assert comprobantes[0]["departamento_id"] == 1


def test_listar_comprobantes_departamento_solo_ve_los_suyos(client, headers_depto_a, db_session):
    _crear_comprobante(db_session, 1, date(2026, 5, 5), 85000, EstadoComprobante.aprobado)
    _crear_comprobante(db_session, 2, date(2026, 5, 6), 92000, EstadoComprobante.pendiente_verificacion)

    r = client.get("/comprobantes", headers=headers_depto_a)
    assert r.status_code == 200
    comprobantes = r.json()
    assert len(comprobantes) == 1
    assert comprobantes[0]["departamento_id"] == 1


def test_listar_comprobantes_departamento_ignora_query_de_otro_depto(client, headers_depto_a, db_session):
    _crear_comprobante(db_session, 1, date(2026, 5, 5), 85000, EstadoComprobante.aprobado)
    _crear_comprobante(db_session, 2, date(2026, 5, 6), 92000, EstadoComprobante.pendiente_verificacion)

    r = client.get("/comprobantes?departamento_id=2", headers=headers_depto_a)
    assert r.status_code == 200
    comprobantes = r.json()
    # Sigue devolviendo solo los de su propio depto.
    assert all(c["departamento_id"] == 1 for c in comprobantes)


# ---------------------------------------------------------------------------
# GET /expensas
# ---------------------------------------------------------------------------


def test_listar_expensas_sin_token_devuelve_401(client):
    r = client.get("/expensas")
    assert r.status_code == 401


def test_listar_expensas_como_representante_devuelve_403(client, headers_representante):
    r = client.get("/expensas", headers=headers_representante)
    assert r.status_code == 403


def test_listar_expensas_como_admin_devuelve_todas(client, headers_admin):
    r = client.get("/expensas", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    departamentos = {e["departamento_id"] for e in data}
    assert departamentos == {1, 2}


def test_listar_expensas_como_depto_a_devuelve_solo_propias(client, headers_depto_a):
    r = client.get("/expensas", headers=headers_depto_a)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert all(e["departamento_id"] == 1 for e in data)


def test_listar_expensas_como_depto_b_devuelve_solo_propias(client, headers_depto_b):
    r = client.get("/expensas", headers=headers_depto_b)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert all(e["departamento_id"] == 2 for e in data)


def test_listar_expensas_como_depto_filtros_no_atraviesan_aislamiento(client, headers_depto_a):
    # Aunque el depto A pida periodo=2026-05 (en el que existen 2 expensas en total),
    # solo debe ver la suya: el aislamiento no se puede saltar vía filtros.
    r = client.get("/expensas?periodo=2026-05", headers=headers_depto_a)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["departamento_id"] == 1


def test_listar_expensas_filtra_por_periodo(client, headers_admin):
    r = client.get("/expensas?periodo=2026-05", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 2

    r = client.get("/expensas?periodo=2026-01", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


def test_listar_expensas_paginacion_limit_offset(client, headers_admin):
    r = client.get("/expensas?limit=1&offset=0", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/expensas?limit=1&offset=1", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/expensas?limit=1&offset=2", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


def test_listar_expensas_periodo_invalido_devuelve_400(client, headers_admin):
    r = client.get("/expensas?periodo=2026/05", headers=headers_admin)
    assert r.status_code == 400


def test_listar_expensas_limit_fuera_de_rango_devuelve_400(client, headers_admin):
    r = client.get("/expensas?limit=0", headers=headers_admin)
    assert r.status_code == 400

    r = client.get("/expensas?limit=999", headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /expensas
# ---------------------------------------------------------------------------


_EXPENSA_NUEVA = {
    "departamento_id": 1,
    "periodo": VENC_1.strftime("%Y-%m"),
    "monto_primer_vencimiento": 87000.00,
    "fecha_primer_vencimiento": VENC_1.isoformat(),
    "monto_segundo_vencimiento": 93090.00,
    "fecha_segundo_vencimiento": VENC_2.isoformat(),
}


def test_crear_expensa_sin_token_devuelve_401(client):
    r = client.post("/expensas", json=_EXPENSA_NUEVA)
    assert r.status_code == 401


def test_crear_expensa_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.post("/expensas", json=_EXPENSA_NUEVA, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_expensa_como_representante_devuelve_403(client, headers_representante):
    r = client.post("/expensas", json=_EXPENSA_NUEVA, headers=headers_representante)
    assert r.status_code == 403


def test_crear_expensa_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/expensas", json=_EXPENSA_NUEVA, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["departamento_id"] == 1
    assert body["periodo"] == VENC_1.strftime("%Y-%m")
    assert body["monto_primer_vencimiento"] == 87000.00
    assert body["fecha_primer_vencimiento"] == VENC_1.isoformat()
    assert body["monto_segundo_vencimiento"] == 93090.00
    assert body["fecha_segundo_vencimiento"] == VENC_2.isoformat()
    # Sin pagos todavía y con vencimiento futuro, FIFO calcula "pendiente".
    assert body["estado_calculado"] == "pendiente"
    assert body["monto_pendiente"] == 87000.00
    assert isinstance(body["id"], int)


def test_crear_expensa_departamento_inexistente_devuelve_404(client, headers_admin):
    r = client.post(
        "/expensas",
        json={**_EXPENSA_NUEVA, "departamento_id": 9999},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_crear_expensa_duplicada_devuelve_409(client, headers_admin):
    # Expensa 100 (seed) ya existe para depto 1, periodo 2026-05.
    r = client.post(
        "/expensas",
        json={**_EXPENSA_NUEVA, "periodo": "2026-05"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_crear_expensa_periodo_invalido_devuelve_400(client, headers_admin):
    r = client.post(
        "/expensas",
        json={**_EXPENSA_NUEVA, "periodo": "2026/06"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_crear_expensa_monto_no_positivo_devuelve_400(client, headers_admin):
    r = client.post(
        "/expensas",
        json={**_EXPENSA_NUEVA, "monto_primer_vencimiento": 0},
        headers=headers_admin,
    )
    assert r.status_code == 400

    r = client.post(
        "/expensas",
        json={**_EXPENSA_NUEVA, "monto_primer_vencimiento": -1},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_crear_expensa_body_incompleto_devuelve_400(client, headers_admin):
    r = client.post(
        "/expensas",
        json={"departamento_id": 1, "periodo": "2026-06"},
        headers=headers_admin,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /expensas/{id}
# ---------------------------------------------------------------------------


def test_obtener_expensa_sin_token_devuelve_401(client):
    r = client.get("/expensas/100")
    assert r.status_code == 401


def test_obtener_expensa_admin_puede_ver_cualquiera(client, headers_admin):
    r = client.get("/expensas/100", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 100
    assert body["departamento_id"] == 1
    assert body["periodo"] == "2026-05"
    assert body["estado_calculado"] == "pendiente"


def test_obtener_expensa_representante_puede_ver_cualquiera(client, headers_representante):
    r = client.get("/expensas/101", headers=headers_representante)
    assert r.status_code == 200
    assert r.json()["departamento_id"] == 2


def test_obtener_expensa_propio_depto_devuelve_200(client, headers_depto_a):
    r = client.get("/expensas/100", headers=headers_depto_a)
    assert r.status_code == 200
    assert r.json()["departamento_id"] == 1


def test_obtener_expensa_otro_depto_devuelve_403(client, headers_depto_a):
    # Expensa 101 pertenece al depto B.
    r = client.get("/expensas/101", headers=headers_depto_a)
    assert r.status_code == 403


def test_obtener_expensa_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/expensas/9999", headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /comprobantes
# ---------------------------------------------------------------------------


_DATA_OK = {"fecha_pago": "2026-05-28", "monto": "85000.00"}


def _imagen_jpg_bytes(size: int = 256) -> bytes:
    """Devuelve `size` bytes que arrancan con el magic header JPEG.
    FastAPI solo mira el content_type del part, no inspecciona el contenido."""
    head = b"\xff\xd8\xff\xe0"  # SOI + APP0
    return head + (b"\x00" * max(size - len(head), 0))


def _files_con_imagen() -> dict:
    return {"archivo": ("comprobante.jpg", _imagen_jpg_bytes(), "image/jpeg")}


def test_presentar_comprobante_sin_token_devuelve_401(client):
    r = client.post("/comprobantes", data=_DATA_OK)
    assert r.status_code == 401


def test_presentar_comprobante_como_departamento_dueno_201(client, headers_depto_a):
    r = client.post(
        "/comprobantes",
        data=_DATA_OK,
        files=_files_con_imagen(),
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["departamento_id"] == 1
    assert body["monto"] == 85000.00
    assert body["fecha_pago"] == "2026-05-28"
    # `archivo_path` es la clave de almacenamiento, no una URL: los adjuntos ya
    # no se sirven publicos. Para abrirlo hay que pedir una URL firmada a
    # GET /comprobantes/{id}/archivo (ver tests/test_archivos.py).
    assert body["archivo_path"].startswith("comprobantes/")
    assert body["archivo_path"].endswith(".jpg")
    # Estado inicial siempre pendiente_verificacion, independiente del cuerpo.
    assert body["estado"] == "pendiente_verificacion"


def test_presentar_comprobante_sin_archivo_400(client, headers_depto_a):
    r = client.post(
        "/comprobantes",
        data=_DATA_OK,
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_presentar_comprobante_como_admin_devuelve_403(client, headers_admin):
    r = client.post(
        "/comprobantes",
        data=_DATA_OK,
        headers=headers_admin,
    )
    assert r.status_code == 403


def test_presentar_comprobante_como_representante_devuelve_403(client, headers_representante):
    r = client.post(
        "/comprobantes",
        data=_DATA_OK,
        headers=headers_representante,
    )
    assert r.status_code == 403


def test_presentar_comprobante_body_invalido_monto_negativo_devuelve_400(client, headers_depto_a):
    r = client.post(
        "/comprobantes",
        data={"fecha_pago": "2026-05-28", "monto": "-1"},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_presentar_comprobante_body_invalido_faltan_campos_devuelve_400(client, headers_depto_a):
    r = client.post(
        "/comprobantes",
        data={"monto": "1000"},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_presentar_comprobante_fecha_futura_devuelve_400(client, headers_depto_a):
    futura = (date.today() + timedelta(days=1)).isoformat()
    r = client.post(
        "/comprobantes",
        data={"fecha_pago": futura, "monto": "85000.00"},
        files=_files_con_imagen(),
        headers=headers_depto_a,
    )
    assert r.status_code == 400
    assert "futura" in r.json()["detail"].lower()


def test_presentar_comprobante_fecha_hoy_201(client, headers_depto_a):
    hoy = date.today().isoformat()
    r = client.post(
        "/comprobantes",
        data={"fecha_pago": hoy, "monto": "85000.00"},
        files=_files_con_imagen(),
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    assert r.json()["fecha_pago"] == hoy


def test_presentar_comprobante_genera_pendiente_verificacion(client, headers_depto_a):
    r = client.post(
        "/comprobantes",
        data={"fecha_pago": "2026-06-05", "monto": "85000.00"},
        files=_files_con_imagen(),
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["estado"] == "pendiente_verificacion"
    assert body["departamento_id"] == 1


def test_presentar_comprobante_persiste_imagen_en_disco(client, headers_depto_a, tmp_path):
    from backend.config import get_settings

    r = client.post(
        "/comprobantes",
        data=_DATA_OK,
        files=_files_con_imagen(),
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    archivo_url = r.json()["archivo_path"]
    rel = archivo_url.removeprefix("/uploads/")
    destino = pathlib.Path(get_settings().UPLOAD_DIR) / rel
    assert destino.exists()
    assert destino.read_bytes()[:4] == b"\xff\xd8\xff\xe0"


def test_presentar_comprobante_archivo_no_imagen_devuelve_400(client, headers_depto_a):
    files = {"archivo": ("comprobante.txt", b"hola mundo", "text/plain")}
    r = client.post(
        "/comprobantes",
        data=_DATA_OK,
        files=files,
        headers=headers_depto_a,
    )
    assert r.status_code == 400
    assert "imagen" in r.json()["detail"].lower()


def test_presentar_comprobante_archivo_demasiado_grande_devuelve_413(client, headers_depto_a):
    grande = _imagen_jpg_bytes(size=5 * 1024 * 1024 + 1)
    files = {"archivo": ("grande.jpg", grande, "image/jpeg")}
    r = client.post(
        "/comprobantes",
        data=_DATA_OK,
        files=files,
        headers=headers_depto_a,
    )
    assert r.status_code == 413
    assert "5 MB" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Movimiento generado al aprobar/rechazar (Fase 3.5)
# ---------------------------------------------------------------------------


def test_aprobar_comprobante_genera_movimiento_pago(client, headers_admin, headers_depto_a):
    files = {"archivo": ("r.pdf", b"%PDF-1.4", "application/pdf")}
    r = client.post(
        "/comprobantes",
        data={"fecha_pago": "2026-06-05", "monto": "30000"},
        files=files,
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    comp_id = r.json()["id"]

    r = client.patch(
        f"/comprobantes/{comp_id}",
        json={"estado": "aprobado", "caja_destino_id": 900},  # Fase 5: caja default
        headers=headers_admin,
    )
    assert r.status_code == 200

    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    assert r.status_code == 200
    movs = r.json()["movimientos"]
    pagos = [m for m in movs if m["tipo"] == "pago_recibido"]
    assert any(
        m["monto"] == 30000 and m["comprobante_id"] == comp_id for m in pagos
    )


def test_rechazar_comprobante_no_genera_movimiento(client, headers_admin, headers_depto_a):
    files = {"archivo": ("r.pdf", b"%PDF-1.4", "application/pdf")}
    r = client.post(
        "/comprobantes",
        data={"fecha_pago": "2026-06-05", "monto": "30000"},
        files=files,
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    comp_id = r.json()["id"]

    r = client.patch(
        f"/comprobantes/{comp_id}",
        json={"estado": "rechazado"},
        headers=headers_admin,
    )
    assert r.status_code == 200

    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    movs = r.json()["movimientos"]
    pagos = [
        m for m in movs
        if m["tipo"] == "pago_recibido" and m["comprobante_id"] == comp_id
    ]
    assert pagos == []


def test_aprobar_comprobante_genera_movimiento_caja(client, headers_admin, headers_depto_a, db_session):
    """Al aprobar, además del MovimientoCuenta también se genera un MovimientoCaja ingreso."""
    from backend.models import MovimientoCaja

    files = {"archivo": ("r.pdf", b"%PDF-1.4", "application/pdf")}
    r = client.post(
        "/comprobantes",
        data={"fecha_pago": "2026-06-05", "monto": "25000"},
        files=files,
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    comp_id = r.json()["id"]

    r = client.patch(
        f"/comprobantes/{comp_id}",
        json={"estado": "aprobado", "caja_destino_id": 900},
        headers=headers_admin,
    )
    assert r.status_code == 200

    # Verificar que se creó MovimientoCaja
    mov_caja = db_session.query(MovimientoCaja).filter_by(comprobante_id=comp_id).first()
    assert mov_caja is not None
    assert mov_caja.caja_id == 900
    assert mov_caja.tipo == "ingreso"
    assert mov_caja.monto == 25000
    assert mov_caja.fecha == date(2026, 6, 5)


# ---------------------------------------------------------------------------
# Soft-delete de comprobantes (DELETE)
# ---------------------------------------------------------------------------


def _crear_comprobante_depto_a(client, headers_depto_a) -> int:
    r = client.post(
        "/comprobantes",
        data={"fecha_pago": "2026-06-05", "monto": "1000"},
        files=_files_con_imagen(),
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_eliminar_comprobante_sin_token_401(client, headers_depto_a):
    comp_id = _crear_comprobante_depto_a(client, headers_depto_a)
    r = client.delete(f"/comprobantes/{comp_id}")
    assert r.status_code == 401


def test_eliminar_comprobante_depto_dueno_204(client, headers_depto_a):
    comp_id = _crear_comprobante_depto_a(client, headers_depto_a)

    r = client.delete(f"/comprobantes/{comp_id}", headers=headers_depto_a)
    assert r.status_code == 204

    # Tras soft-delete, ya no aparece en el listado.
    r = client.get("/comprobantes", headers=headers_depto_a)
    assert r.status_code == 200
    assert all(c["id"] != comp_id for c in r.json())


def test_eliminar_comprobante_admin_204(client, headers_admin, headers_depto_a):
    comp_id = _crear_comprobante_depto_a(client, headers_depto_a)

    r = client.delete(f"/comprobantes/{comp_id}", headers=headers_admin)
    assert r.status_code == 204


def test_eliminar_comprobante_depto_ajeno_403(client, headers_depto_a, headers_depto_b):
    comp_id = _crear_comprobante_depto_a(client, headers_depto_a)

    r = client.delete(f"/comprobantes/{comp_id}", headers=headers_depto_b)
    assert r.status_code == 403


def test_eliminar_comprobante_inexistente_404(client, headers_admin):
    r = client.delete("/comprobantes/9999", headers=headers_admin)
    assert r.status_code == 404


def test_eliminar_comprobante_ya_eliminado_404(client, headers_admin, headers_depto_a):
    comp_id = _crear_comprobante_depto_a(client, headers_depto_a)

    r = client.delete(f"/comprobantes/{comp_id}", headers=headers_admin)
    assert r.status_code == 204

    # Segundo DELETE sobre el mismo ID ya eliminado → 404 (idempotente desde la vista).
    r = client.delete(f"/comprobantes/{comp_id}", headers=headers_admin)
    assert r.status_code == 404


def test_eliminar_comprobante_apaga_el_pendiente_del_admin(client, headers_admin, headers_depto_a, db_session):
    """El comprobante_presentado no puede quedar prendido apuntando a un
    comprobante ya borrado -- ver backend/routers/comprobantes.py y el mismo
    arreglo ya aplicado en peticiones (backend/routers/peticiones.py:208)."""
    from backend.models import Notificacion

    comp_id = _crear_comprobante_depto_a(client, headers_depto_a)
    assert db_session.query(Notificacion).filter_by(
        tipo="comprobante_presentado", leida=False,
    ).count() == 1

    r = client.delete(f"/comprobantes/{comp_id}", headers=headers_depto_a)
    assert r.status_code == 204

    assert db_session.query(Notificacion).filter_by(
        tipo="comprobante_presentado", leida=False,
    ).count() == 0


def test_get_comprobantes_excluye_eliminados(client, headers_admin, headers_depto_a):
    comp_id = _crear_comprobante_depto_a(client, headers_depto_a)

    r = client.delete(f"/comprobantes/{comp_id}", headers=headers_depto_a)
    assert r.status_code == 204

    # Ni depto ni admin lo ven más.
    for headers in (headers_depto_a, headers_admin):
        r = client.get("/comprobantes", headers=headers)
        assert all(c["id"] != comp_id for c in r.json())


def test_patch_comprobante_eliminado_404(client, headers_admin, headers_depto_a):
    comp_id = _crear_comprobante_depto_a(client, headers_depto_a)

    r = client.delete(f"/comprobantes/{comp_id}", headers=headers_admin)
    assert r.status_code == 204

    # No se puede aprobar un comprobante soft-eliminado.
    r = client.patch(
        f"/comprobantes/{comp_id}",
        json={"estado": "aprobado", "caja_destino_id": 900},  # Fase 5: caja default
        headers=headers_admin,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# UX: descripciones humanas + código de depto en respuestas
# ---------------------------------------------------------------------------


def test_comprobante_out_incluye_departamento_codigo(client, headers_admin, headers_depto_a):
    """El listado expone el código UF-XX del depto, no solo el id numérico."""
    r = client.post(
        "/comprobantes", headers=headers_depto_a,
        data={"fecha_pago": "2026-05-15", "monto": 500.0},
        files={"archivo": ("p.png", bytes.fromhex("89504e470d0a1a0a"), "image/png")},
    )
    assert r.status_code == 201
    r2 = client.get("/comprobantes", headers=headers_admin)
    assert r2.status_code == 200
    assert len(r2.json()) >= 1
    comp = r2.json()[0]
    assert comp["departamento_codigo"] == "UF-1A"


def test_aprobar_comprobante_genera_descripcion_humana(client, headers_admin, headers_depto_a, db_session):
    """Al aprobar, la descripción del movimiento incluye el código del depto y
    la fecha de pago — no 'Pago comprobante #NNN'."""
    from backend.models import MovimientoCaja, MovimientoCuenta
    import io
    r = client.post(
        "/comprobantes",
        headers=headers_depto_a,
        data={"fecha_pago": "2026-05-15", "monto": 1000.0},
        files={"archivo": ("p.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert r.status_code == 201
    comp_id = r.json()["id"]

    r2 = client.patch(f"/comprobantes/{comp_id}", headers=headers_admin,
                      json={"estado": "aprobado"})
    assert r2.status_code == 200

    mov_cuenta = db_session.query(MovimientoCuenta).filter_by(comprobante_id=comp_id).first()
    mov_caja = db_session.query(MovimientoCaja).filter_by(comprobante_id=comp_id).first()
    assert mov_cuenta is not None and mov_caja is not None
    # Debe mencionar el código del depto y la fecha, no "#NNN"
    assert "UF-1A" in mov_cuenta.descripcion
    assert "2026-05-15" in mov_cuenta.descripcion
    assert "#" not in mov_cuenta.descripcion
    assert "UF-1A" in mov_caja.descripcion
    assert "#" not in mov_caja.descripcion


# ---------------------------------------------------------------------------
# Motivo del rechazo
# ---------------------------------------------------------------------------


def test_rechazar_guarda_el_motivo(client, headers_admin, db_session):
    """El motivo queda en el comprobante y lo devuelve el listado: el depto
    tiene que poder ver qué corregir antes de volver a presentar el pago."""
    c = _crear_comprobante(
        db_session, 1, date(2026, 6, 5), 30000, EstadoComprobante.pendiente_verificacion
    )
    r = client.patch(
        f"/comprobantes/{c.id}",
        json={"estado": "rechazado", "motivo_rechazo": "El monto no coincide con la transferencia."},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["motivo_rechazo"] == "El monto no coincide con la transferencia."

    r = client.get("/comprobantes", headers=headers_admin)
    guardado = next(x for x in r.json() if x["id"] == c.id)
    assert guardado["motivo_rechazo"] == "El monto no coincide con la transferencia."


def test_rechazar_con_motivo_en_blanco_queda_en_null(client, headers_admin, db_session):
    c = _crear_comprobante(
        db_session, 1, date(2026, 6, 5), 30000, EstadoComprobante.pendiente_verificacion
    )
    r = client.patch(
        f"/comprobantes/{c.id}",
        json={"estado": "rechazado", "motivo_rechazo": "  \n "},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["motivo_rechazo"] is None


def test_aprobar_ignora_el_motivo_de_rechazo(client, headers_admin, db_session):
    """Un motivo colado en una aprobación no se guarda: sólo tiene sentido
    cuando el comprobante quedó rechazado."""
    c = _crear_comprobante(
        db_session, 1, date(2026, 6, 5), 30000, EstadoComprobante.pendiente_verificacion
    )
    r = client.patch(
        f"/comprobantes/{c.id}",
        json={"estado": "aprobado", "motivo_rechazo": "no debería quedar"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["motivo_rechazo"] is None


def test_departamento_ve_el_motivo_de_su_comprobante_rechazado(
    client, headers_admin, headers_depto_a, db_session
):
    c = _crear_comprobante(
        db_session, 1, date(2026, 6, 5), 30000, EstadoComprobante.pendiente_verificacion
    )
    client.patch(
        f"/comprobantes/{c.id}",
        json={"estado": "rechazado", "motivo_rechazo": "El comprobante está ilegible."},
        headers=headers_admin,
    )
    r = client.get("/comprobantes", headers=headers_depto_a)
    assert r.status_code == 200
    visto = next(x for x in r.json() if x["id"] == c.id)
    assert visto["motivo_rechazo"] == "El comprobante está ilegible."


# ---------------------------------------------------------------------------
# Notificaciones al verificar un comprobante
# ---------------------------------------------------------------------------


def test_aprobar_comprobante_notifica_al_depto(client, headers_admin, headers_depto_a, db):
    from backend.models import Notificacion

    with open(__file__, "rb") as f:
        r = client.post(
            "/comprobantes",
            data={"fecha_pago": "2026-08-01", "monto": "1000"},
            files={"archivo": ("c.pdf", f.read(), "application/pdf")},
            headers=headers_depto_a,
        )
    assert r.status_code == 201
    cid_comp = r.json()["id"]

    r2 = client.patch(
        f"/comprobantes/{cid_comp}",
        json={"estado": "aprobado"},
        headers=headers_admin,
    )
    assert r2.status_code == 200

    ns = db.query(Notificacion).filter_by(tipo="comprobante_aprobado").all()
    assert [n.usuario_id for n in ns] == [2]


def test_rechazar_comprobante_incluye_el_motivo(client, headers_admin, headers_depto_a, db):
    from backend.models import Notificacion

    with open(__file__, "rb") as f:
        r = client.post(
            "/comprobantes",
            data={"fecha_pago": "2026-08-01", "monto": "1000"},
            files={"archivo": ("c.pdf", f.read(), "application/pdf")},
            headers=headers_depto_a,
        )
    cid_comp = r.json()["id"]

    client.patch(
        f"/comprobantes/{cid_comp}",
        json={"estado": "rechazado", "motivo_rechazo": "El monto no coincide"},
        headers=headers_admin,
    )

    n = db.query(Notificacion).filter_by(tipo="comprobante_rechazado").one()
    assert "El monto no coincide" in n.mensaje


def test_reverificar_comprobante_ya_verificado_devuelve_409_y_no_duplica_el_aviso(
    client, headers_admin, headers_depto_a, db
):
    """El 409 sobre un estado terminal es la única guarda que evita que
    aprobar dos veces el mismo comprobante dispare el aviso (y el mail) de
    nuevo. Si mañana alguien afloja esa guarda, este test tiene que
    romperse — por eso lo que importa no es sólo el 409, sino que después
    de él siga habiendo un único aviso y ningún pendiente revivido."""
    from backend.models import Notificacion

    with open(__file__, "rb") as f:
        r = client.post(
            "/comprobantes",
            data={"fecha_pago": "2026-08-01", "monto": "1000"},
            files={"archivo": ("c.pdf", f.read(), "application/pdf")},
            headers=headers_depto_a,
        )
    assert r.status_code == 201
    cid_comp = r.json()["id"]

    r2 = client.patch(
        f"/comprobantes/{cid_comp}",
        json={"estado": "aprobado"},
        headers=headers_admin,
    )
    assert r2.status_code == 200
    assert db.query(Notificacion).filter_by(tipo="comprobante_aprobado").count() == 1

    # Reintentar sobre el mismo comprobante, ya en estado terminal.
    r3 = client.patch(
        f"/comprobantes/{cid_comp}",
        json={"estado": "aprobado"},
        headers=headers_admin,
    )
    assert r3.status_code == 409

    # El 409 corta ANTES de llegar a resolver_pendiente/emitir: sigue
    # habiendo un solo aviso de aprobación (no dos)...
    assert db.query(Notificacion).filter_by(tipo="comprobante_aprobado").count() == 1
    # ...y ninguna notificación ligada a este comprobante quedó marcada
    # como no-leída de nuevo (el pendiente del admin no "revivió").
    revividos = db.query(Notificacion).filter_by(
        entidad_tipo="comprobante", entidad_id=cid_comp, leida=False,
    ).count()
    assert revividos == 0


def test_presentar_comprobante_avisa_al_admin_como_pendiente(client, headers_depto_a, db):
    from backend.models import Notificacion

    with open(__file__, "rb") as f:
        r = client.post(
            "/comprobantes",
            data={"fecha_pago": "2026-08-01", "monto": "1000"},
            files={"archivo": ("c.pdf", f.read(), "application/pdf")},
            headers=headers_depto_a,
        )
    assert r.status_code == 201

    n = db.query(Notificacion).filter_by(tipo="comprobante_presentado").one()
    assert n.usuario_id == 1
    assert n.entidad_tipo == "comprobante"
    assert n.entidad_id == r.json()["id"]
    assert "UF-1A" in n.mensaje

"""Tests del almacenamiento de archivos y de su control de acceso."""
import io
import time

import pytest
from fastapi import HTTPException, UploadFile

from backend import storage


def _upload(nombre: str, contenido: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        filename=nombre,
        file=io.BytesIO(contenido),
        headers={"content-type": content_type},
    )


def test_guardar_archivo_devuelve_clave_en_la_carpeta_pedida(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_directorio_base", lambda: tmp_path)

    clave = storage.guardar_archivo(
        _upload("recibo.jpg", b"contenido-falso", "image/jpeg"), "comprobantes"
    )

    assert clave.startswith("comprobantes/")
    assert clave.endswith(".jpg")
    assert (tmp_path / clave).read_bytes() == b"contenido-falso"


def test_guardar_archivo_rechaza_tipo_no_permitido(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_directorio_base", lambda: tmp_path)

    with pytest.raises(HTTPException) as e:
        storage.guardar_archivo(
            _upload("virus.exe", b"MZ", "application/x-msdownload"), "comprobantes"
        )

    assert e.value.status_code == 400


def test_guardar_archivo_corta_por_tamano_y_no_deja_basura(tmp_path, monkeypatch):
    """El archivo parcial se borra: si no, cada intento fallido deja residuo."""
    monkeypatch.setattr(storage, "_directorio_base", lambda: tmp_path)
    monkeypatch.setattr(storage, "_max_bytes", lambda: 10)

    with pytest.raises(HTTPException) as e:
        storage.guardar_archivo(
            _upload("grande.jpg", b"x" * 50, "image/jpeg"), "comprobantes"
        )

    assert e.value.status_code == 413
    assert list((tmp_path / "comprobantes").glob("*")) == []


def test_abrir_archivo_devuelve_contenido_y_tipo(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_directorio_base", lambda: tmp_path)
    clave = storage.guardar_archivo(
        _upload("recibo.png", b"png-falso", "image/png"), "comprobantes"
    )

    chunks, content_type = storage.abrir_archivo(clave)

    assert b"".join(chunks) == b"png-falso"
    assert content_type == "image/png"


def test_abrir_archivo_inexistente_levanta_filenotfound(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_directorio_base", lambda: tmp_path)

    with pytest.raises(FileNotFoundError):
        storage.abrir_archivo("comprobantes/no-existe.jpg")


def test_abrir_archivo_no_permite_salir_de_la_carpeta(tmp_path, monkeypatch):
    """Sin este chequeo, una clave con '..' leería cualquier archivo del disco."""
    monkeypatch.setattr(storage, "_directorio_base", lambda: tmp_path)

    with pytest.raises(FileNotFoundError):
        storage.abrir_archivo("../../.env")


# --- Firma de las URLs de descarga -----------------------------------------


def _partes(ruta_firmada: str) -> tuple[str, str]:
    """Extrae (exp, firma) de la ruta que devuelve `firmar_clave`."""
    query = ruta_firmada.split("?", 1)[1]
    partes = dict(p.split("=", 1) for p in query.split("&"))
    return partes["exp"], partes["firma"]


def test_firma_valida_se_verifica_ok():
    ruta = storage.firmar_clave("comprobantes/abc.jpg", segundos=60)
    assert ruta.startswith("/archivos/comprobantes/abc.jpg?")
    exp, firma = _partes(ruta)
    assert storage.verificar_firma("comprobantes/abc.jpg", exp, firma) is True


def test_firma_vencida_se_rechaza():
    ruta = storage.firmar_clave("comprobantes/abc.jpg", segundos=-1)
    exp, firma = _partes(ruta)
    assert storage.verificar_firma("comprobantes/abc.jpg", exp, firma) is False


def test_firma_de_otra_clave_no_sirve():
    """Sin esto, firmar un archivo propio daría acceso a cualquier otro."""
    ruta = storage.firmar_clave("comprobantes/mio.jpg", segundos=60)
    exp, firma = _partes(ruta)
    assert storage.verificar_firma("comprobantes/ajeno.jpg", exp, firma) is False


def test_firma_adulterada_se_rechaza():
    ruta = storage.firmar_clave("comprobantes/abc.jpg", segundos=60)
    exp, _ = _partes(ruta)
    assert storage.verificar_firma("comprobantes/abc.jpg", exp, "0" * 64) is False


def test_exp_adulterado_se_rechaza():
    """Estirar el vencimiento tiene que invalidar la firma, porque `exp` está
    dentro de lo firmado."""
    ruta = storage.firmar_clave("comprobantes/abc.jpg", segundos=60)
    _, firma = _partes(ruta)
    futuro = str(int(time.time()) + 999999)
    assert storage.verificar_firma("comprobantes/abc.jpg", futuro, firma) is False


# --- Endpoint público de descarga ------------------------------------------


def test_endpoint_de_archivos_sirve_con_firma_valida(client):
    clave = storage.guardar_archivo(
        _upload("r.png", b"png-falso", "image/png"), "comprobantes"
    )

    r = client.get(storage.firmar_clave(clave, segundos=60))

    assert r.status_code == 200
    assert r.content == b"png-falso"
    assert r.headers["content-type"].startswith("image/png")


def test_endpoint_de_archivos_rechaza_sin_firma(client):
    clave = storage.guardar_archivo(
        _upload("r.png", b"png-falso", "image/png"), "comprobantes"
    )

    assert client.get(f"/archivos/{clave}").status_code == 403


def test_endpoint_de_archivos_rechaza_firma_vencida(client):
    clave = storage.guardar_archivo(
        _upload("r.png", b"png-falso", "image/png"), "comprobantes"
    )

    assert client.get(storage.firmar_clave(clave, segundos=-1)).status_code == 403


def test_endpoint_de_archivos_404_si_la_clave_no_existe(client):
    assert client.get(storage.firmar_clave("comprobantes/fantasma.jpg")).status_code == 404


# --- Quien puede pedir la URL de un adjunto --------------------------------


@pytest.fixture()
def comprobante_de_a(client, headers_depto_a) -> int:
    """Comprobante presentado por el departamento A. Devuelve su id."""
    from datetime import date

    r = client.post(
        "/comprobantes",
        headers=headers_depto_a,
        data={"fecha_pago": date.today().isoformat(), "monto": "1000"},
        files={"archivo": ("recibo.png", b"png-falso", "image/png")},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_depto_obtiene_la_url_de_su_propio_comprobante(
    client, headers_depto_a, comprobante_de_a
):
    r = client.get(f"/comprobantes/{comprobante_de_a}/archivo", headers=headers_depto_a)

    assert r.status_code == 200
    assert r.json()["url"].startswith("/archivos/comprobantes/")
    assert r.json()["expira_en"] > 0


def test_depto_no_obtiene_la_url_del_comprobante_de_otro(
    client, headers_depto_b, comprobante_de_a
):
    """El agujero que se esta cerrando: son fotos de transferencias bancarias."""
    r = client.get(f"/comprobantes/{comprobante_de_a}/archivo", headers=headers_depto_b)

    assert r.status_code == 404


def test_sin_token_no_se_obtiene_ninguna_url(client, comprobante_de_a):
    assert client.get(f"/comprobantes/{comprobante_de_a}/archivo").status_code == 401


def test_admin_obtiene_la_url_de_cualquier_comprobante_de_su_consorcio(
    client, headers_admin, comprobante_de_a
):
    r = client.get(f"/comprobantes/{comprobante_de_a}/archivo", headers=headers_admin)
    assert r.status_code == 200


def test_comprobante_inexistente_devuelve_404(client, headers_admin):
    assert client.get("/comprobantes/999999/archivo", headers=headers_admin).status_code == 404


def test_la_url_entregada_sirve_para_bajar_el_archivo(
    client, headers_depto_a, comprobante_de_a
):
    """El circuito completo: pido la URL con mi token, y la uso sin token."""
    url = client.get(
        f"/comprobantes/{comprobante_de_a}/archivo", headers=headers_depto_a
    ).json()["url"]

    r = client.get(url)

    assert r.status_code == 200
    assert r.content == b"png-falso"


def test_comprobante_out_ya_no_fabrica_la_ruta_de_uploads(
    client, headers_depto_a, comprobante_de_a
):
    """archivo_path vuelve a ser la clave cruda: el frontend solo la usa para
    saber si hay adjunto, nunca para armar una URL."""
    r = client.get("/comprobantes", headers=headers_depto_a)

    comprobante = next(c for c in r.json() if c["id"] == comprobante_de_a)
    assert not comprobante["archivo_path"].startswith("/uploads/")
    assert comprobante["archivo_path"].startswith("comprobantes/")


# --- Backend S3-compatible --------------------------------------------------
#
# Nunca contra un bucket real: se verifica que se llame con el bucket y la
# clave correctos, no que Amazon funcione.


class _ClienteS3Falso:
    """Doble del cliente boto3: registra las llamadas en vez de salir a la red."""

    def __init__(self):
        self.objetos: dict[str, bytes] = {}
        self.puestos: list[dict] = []

    def put_object(self, **kwargs):
        self.puestos.append(kwargs)
        self.objetos[kwargs["Key"]] = kwargs["Body"].read()

    def get_object(self, Bucket, Key):  # noqa: N803 — firma de boto3
        if Key not in self.objetos:
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        contenido = self.objetos[Key]

        class _Cuerpo:
            def iter_chunks(self, chunk_size=8192):
                yield contenido

        return {"Body": _Cuerpo(), "ContentType": "image/png"}


@pytest.fixture()
def s3_falso(monkeypatch) -> _ClienteS3Falso:
    from backend import storage_s3

    falso = _ClienteS3Falso()
    monkeypatch.setattr(storage_s3, "_cliente", lambda: falso)
    monkeypatch.setattr(storage_s3, "_bucket", lambda: "comprobantes-test")
    return falso


def test_backend_s3_sube_con_el_bucket_y_la_clave_correctos(s3_falso):
    from backend import storage_s3

    storage_s3.subir(
        _upload("r.png", b"png-falso", "image/png"), "comprobantes/x.png", 1000
    )

    assert s3_falso.puestos[0]["Bucket"] == "comprobantes-test"
    assert s3_falso.puestos[0]["Key"] == "comprobantes/x.png"
    assert s3_falso.puestos[0]["ContentType"] == "image/png"


def test_backend_s3_rechaza_archivo_demasiado_grande(s3_falso):
    from backend import storage_s3

    with pytest.raises(HTTPException) as e:
        storage_s3.subir(_upload("g.png", b"x" * 50, "image/png"), "comprobantes/g.png", 10)

    assert e.value.status_code == 413
    assert s3_falso.puestos == [], "no debe subir nada si excede el limite"


def test_backend_s3_devuelve_contenido_y_tipo(s3_falso):
    from backend import storage_s3

    storage_s3.subir(_upload("r.png", b"png-falso", "image/png"), "comprobantes/x.png", 1000)
    chunks, content_type = storage_s3.abrir("comprobantes/x.png")

    assert b"".join(chunks) == b"png-falso"
    assert content_type == "image/png"


def test_backend_s3_clave_inexistente_levanta_filenotfound(s3_falso):
    from backend import storage_s3

    with pytest.raises(FileNotFoundError):
        storage_s3.abrir("comprobantes/no-existe.png")


def test_storage_delega_en_s3_cuando_el_backend_es_s3(s3_falso, monkeypatch):
    """La interfaz es la misma: los routers no saben cual backend esta activo."""
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "STORAGE_BACKEND", "s3")

    clave = storage.guardar_archivo(_upload("r.png", b"png-falso", "image/png"), "comprobantes")

    assert clave.startswith("comprobantes/")
    assert s3_falso.puestos[0]["Key"] == clave
    assert b"".join(storage.abrir_archivo(clave)[0]) == b"png-falso"


# --- Migracion de lo que ya esta en disco -----------------------------------


def test_migrar_archivos_sube_todo_lo_que_hay_en_disco(tmp_path, s3_falso):
    from backend import migrar_archivos

    (tmp_path / "comprobantes").mkdir()
    (tmp_path / "comprobantes" / "a.jpg").write_bytes(b"uno")
    (tmp_path / "presupuestos").mkdir()
    (tmp_path / "presupuestos" / "b.pdf").write_bytes(b"dos")

    resultado = migrar_archivos.migrar(tmp_path)

    assert resultado["subidos"] == 2
    assert resultado["fallados"] == []
    # La clave conserva la ruta relativa: es exactamente lo que quedo guardado
    # en archivo_path, asi que las filas de la base siguen resolviendo.
    assert s3_falso.objetos["comprobantes/a.jpg"] == b"uno"
    assert s3_falso.objetos["presupuestos/b.pdf"] == b"dos"


def test_migrar_archivos_ignora_directorios_vacios(tmp_path, s3_falso):
    from backend import migrar_archivos

    (tmp_path / "comprobantes").mkdir()

    assert migrar_archivos.migrar(tmp_path)["subidos"] == 0


def test_uploads_ya_no_esta_montado():
    """El montaje publico de /uploads era el agujero: cualquiera con la URL
    abria el comprobante de cualquier vecino sin estar logueado.

    Se asserta sobre las rutas registradas y no pidiendo un archivo por HTTP,
    porque el montaje estatico apunta al UPLOAD_DIR que habia al importar la
    app, no al temporal de los tests: un 404 por HTTP no probaria nada.
    """
    from backend.main import app

    montajes = [
        r.path for r in app.routes if r.__class__.__name__ == "Mount"
    ]

    assert "/uploads" not in montajes, (
        f"/uploads sigue montado como estatico publico: {montajes}"
    )

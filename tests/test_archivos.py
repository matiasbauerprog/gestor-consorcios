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

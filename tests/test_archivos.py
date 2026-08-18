"""Tests del almacenamiento de archivos y de su control de acceso."""
import io

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

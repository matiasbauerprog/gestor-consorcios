# Archivos fuera del servidor y con control de acceso — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que los comprobantes de pago y los presupuestos adjuntos sobrevivan a un despliegue y que sólo los pueda abrir quien tiene derecho a verlos.

**Architecture:** `backend/storage.py` pasa de ser "escribir en una carpeta" a una interfaz con dos implementaciones seleccionables por configuración: **local** (disco, para desarrollo y tests, sin red) y **S3-compatible** (producción, vía boto3 — sirve para Supabase Storage, Cloudflare R2 o AWS S3 sin cambiar código). El montaje público `/uploads` desaparece. En su lugar, cada recurso expone un endpoint autenticado que valida pertenencia mirando la fila en la base y devuelve una **URL firmada de vida corta**; el frontend pide esa URL con su token y recién después la usa como `src`.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · boto3 · HMAC-SHA256 (firma local) · React + Vite · pytest.

**Spec:** `docs/superpowers/specs/2026-08-17-listo-para-cliente-real.md` (Frente 2, hallazgos H1 y H2)

## Global Constraints

- **Los tests no tocan la red.** El backend local es el default y es el que corre en el suite y en CI. El backend S3 se testea con un doble, nunca contra un bucket real.
- La interfaz es la misma para los dos backends: ningún router ni schema debe saber cuál está activo.
- Los 1088 tests existentes siguen en verde al terminar cada tarea. Comando: `./.venv/Scripts/python.exe -m pytest -q`
- La demo pública **no se toca**: sus comprobantes son archivos estáticos servidos por Vercel bajo `/demo-comprobantes/` y no pasan por ninguna API. El frontend debe distinguir ese caso y no intentar firmarlo.
- Toda migración de esquema va como revisión de Alembic (ver `docs/superpowers/plans/2026-08-17-versionado-de-esquema-alembic.md`). Este plan **no** cambia el esquema, así que no debería hacer falta ninguna.
- Nombres, mensajes y comentarios en español.
- Un commit por tarea como mínimo.

## Contexto que el implementador necesita saber

**Dónde se guarda hoy.** Hay dos caminos duplicados que hacen lo mismo:
- `backend/storage.py:17` — `guardar_imagen_comprobante`, escribe en `UPLOAD_DIR/comprobantes/`, valida por `content_type`, corta por tamaño mientras escribe (streaming).
- `backend/routers/presupuestos.py:47` — `_guardar_archivo`, escribe en `UPLOAD_DIR/presupuestos/`, valida por extensión del filename, lee el archivo entero en memoria antes de chequear tamaño.

Los dos devuelven una clave relativa (`comprobantes/<uuid>.jpg`, `presupuestos/<uuid>.pdf`) que se persiste en `Comprobante.archivo_path` (`backend/models.py:286`) y `Presupuesto.archivo_path` (`backend/models.py:424`).

**Cómo se sirven hoy — el agujero.** `backend/main.py:178` monta `app.mount("/uploads", StaticFiles(directory=...))` **sin ninguna dependencia de autenticación**. Cualquiera con la URL abre el archivo sin estar logueado. Los nombres son UUID hex (no adivinables), pero la URL queda en el historial del navegador, se puede reenviar y no hay ningún control de quién mira el comprobante de quién. Son fotos de transferencias bancarias de los vecinos.

**Cómo lo consume el frontend.** `ComprobanteOut` (`backend/schemas.py:179-183`) serializa `archivo_path` a `/uploads/<clave>`; `PresupuestoOut` (`backend/schemas.py:1114`) devuelve la clave cruda. De ahí las dos formas distintas en el frontend:
- `${API_BASE}${c.archivo_path}` en `screens/Comprobantes.jsx:257,259,353,355`, `screens/MiCuenta.jsx:299,304` y `components/ModalComprobantesExpensa.jsx:101,106`
- `${API_BASE}/uploads/${p.archivo_path}` en `components/ModalDetalleTrabajo.jsx:167`

**La restricción que decide el diseño.** El frontend renderiza esos archivos con `<img src=...>` y `<a href=...>`. **Ni `img` ni `a` mandan el header `Authorization`**, así que un endpoint protegido por Bearer token no se puede usar directo como `src`. Por eso el flujo es en dos pasos: el frontend pide la URL con su token (petición normal, autenticada) y recibe una URL firmada de vida corta que sí funciona como `src` sin header.

**Por qué la firma también en local.** Podría servirse el archivo directo desde el endpoint autenticado en desarrollo, pero entonces el frontend tendría dos caminos distintos según el entorno. Con firma local (HMAC sobre `SECRET_KEY`) el contrato es idéntico en desarrollo y en producción, y el camino que se prueba en los tests es el mismo que corre en el cliente.

**Aislamiento existente.** `tests/test_idor_multitenant.py` ya cubre que un departamento no lea comprobantes de otro por la API. Este plan extiende esa cobertura a los archivos.

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `backend/storage.py` (reescribir) | Interfaz única: guardar, abrir, firmar. Elige implementación por configuración. Validación de tipo y tamaño en un solo lugar. |
| `backend/storage_s3.py` (crear) | Implementación S3-compatible con boto3. Sin lógica de negocio: sólo put/get/presign. |
| `backend/routers/archivos.py` (crear) | Endpoint **público** que valida la firma y entrega el archivo. Es la contracara de `url_firmada`. |
| `backend/routers/comprobantes.py` (modificar) | Nuevo `GET /comprobantes/{id}/archivo`: valida pertenencia y devuelve URL firmada. |
| `backend/routers/presupuestos.py` (modificar: borrar 47-62) | Usa `storage.guardar_archivo`. Nuevo `GET /trabajos/{trabajo_id}/presupuestos/{id}/archivo`. |
| `backend/main.py` (modificar: 175-178) | Se va el `mount("/uploads", StaticFiles(...))`. Entra el router de archivos. |
| `backend/config.py` (modificar) | `STORAGE_BACKEND`, `S3_*`, `URL_FIRMADA_SEGUNDOS`. |
| `backend/schemas.py` (modificar: 179-183) | `ComprobanteOut` deja de fabricar `/uploads/...`. Nuevo `ArchivoUrlOut`. |
| `backend/migrar_archivos.py` (crear) | Script de una sola vez: sube al almacén externo lo que hoy está en disco. |
| `frontend/src/api/archivos.js` (crear) | `urlDeArchivo(ruta)`: pide la URL firmada; deja pasar derecho las rutas de la demo. |
| `frontend/src/components/ArchivoAdjunto.jsx` (crear) | Miniatura + enlace que resuelven la URL solos. Reemplaza los 8 usos sueltos. |
| `tests/test_archivos.py` (crear) | Firma válida/vencida/adulterada, aislamiento por rol y por consorcio, backend S3 con doble. |

## Task Right-Sizing

Siete tareas. Las 1-3 dejan el sistema **entero y seguro** con el backend local: si el trabajo se cortara ahí, el agujero de privacidad ya está tapado. La 4 agrega el almacén externo, la 5 el frontend, la 6 la migración de lo existente y la 7 la documentación.

---

### Task 1: Interfaz de almacenamiento única, con backend local

**Files:**
- Modify: `backend/storage.py` (reescritura completa)
- Modify: `backend/config.py`
- Modify: `backend/routers/presupuestos.py` (borrar `_guardar_archivo`, líneas 47-62)
- Modify: `backend/routers/comprobantes.py` (cambiar el import y la llamada)
- Create: `tests/test_archivos.py`

**Interfaces:**
- Consumes: `backend.config.get_settings()`.
- Produces, para las tareas siguientes:
  - `guardar_archivo(archivo: UploadFile, carpeta: str) -> str` — devuelve la clave relativa (`"comprobantes/<hex>.jpg"`).
  - `abrir_archivo(clave: str) -> tuple[Iterator[bytes], str]` — `(chunks, content_type)`. Levanta `FileNotFoundError` si no existe.
  - `EXTENSIONES_PERMITIDAS: dict[str, str]` — mapa content_type → extensión.

- [ ] **Step 1: Escribir los tests (fallan)**

Crear `tests/test_archivos.py`:

```python
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
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_archivos.py -q`
Expected: FAIL — `storage.guardar_archivo` no existe todavía.

- [ ] **Step 3: Agregar la configuración**

En `backend/config.py`, dentro de `Settings`, debajo de `MAX_UPLOAD_SIZE_BYTES`:

```python
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    URL_FIRMADA_SEGUNDOS: int = 300
    S3_ENDPOINT_URL: str = ""
    S3_REGION: str = "auto"
    S3_BUCKET: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
```

Y el validator que impide arrancar mal configurado, junto a los otros validators:

```python
    @model_validator(mode="after")
    def _s3_exige_credenciales(self) -> "Settings":
        """Con STORAGE_BACKEND=s3 faltando credenciales, cada subida fallaría
        recién en tiempo de request y con un error de boto3 incomprensible.
        Mejor no arrancar."""
        if self.STORAGE_BACKEND == "s3":
            faltan = [
                nombre
                for nombre in ("S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
                if not getattr(self, nombre)
            ]
            if faltan:
                raise ValueError(
                    f"STORAGE_BACKEND=s3 exige {', '.join(faltan)}."
                )
        elif self.STORAGE_BACKEND != "local":
            raise ValueError(
                f"STORAGE_BACKEND invalido: {self.STORAGE_BACKEND!r}. "
                "Valores validos: 'local', 's3'."
            )
        return self
```

- [ ] **Step 4: Reescribir `backend/storage.py`**

Reemplazar el contenido completo por:

```python
"""Almacenamiento de archivos subidos.

Una sola interfaz con dos implementaciones detrás:

- **local** — escribe en `UPLOAD_DIR`. Es el default, es lo que corre en los
  tests y en CI, y no toca la red.
- **s3** — cualquier almacén S3-compatible (Supabase Storage, Cloudflare R2,
  AWS S3). Ver `backend/storage_s3.py`.

Ningún router sabe cuál está activo: piden `guardar_archivo` y `abrir_archivo`
y listo.

La validación de tipo y de tamaño vive acá y sólo acá. Antes estaba duplicada
entre este módulo y `routers/presupuestos.py`, con dos criterios distintos
(content_type contra extensión del filename) y dos límites que podían
desincronizarse.
"""
import uuid
from collections.abc import Iterator
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from .config import get_settings

# content_type -> extensión con la que se persiste. La extensión del filename
# que manda el cliente no se usa nunca: es atacante-controlada.
EXTENSIONES_PERMITIDAS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}

_TIPOS_POR_EXTENSION = {v: k for k, v in EXTENSIONES_PERMITIDAS.items()}

_TAMANO_CHUNK = 64 * 1024


def _directorio_base() -> Path:
    """Raíz del almacenamiento local. Función y no constante para que los
    tests la puedan sustituir por un tmp_path."""
    return Path(get_settings().UPLOAD_DIR)


def _max_bytes() -> int:
    return get_settings().MAX_UPLOAD_SIZE_BYTES


def _extension_valida(archivo: UploadFile) -> str:
    ext = EXTENSIONES_PERMITIDAS.get(archivo.content_type or "")
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser una imagen JPG/PNG/WebP o un PDF.",
        )
    return ext


def guardar_archivo(archivo: UploadFile, carpeta: str) -> str:
    """Persiste `archivo` bajo `carpeta` y devuelve la clave relativa.

    La clave (p. ej. `comprobantes/9f3a....jpg`) es lo que se guarda en la
    base; nunca una ruta absoluta ni una URL, para que mover el almacén no
    obligue a reescribir filas.

    Eleva `HTTPException` 400 si el tipo no está permitido y 413 si supera el
    tamaño máximo.
    """
    ext = _extension_valida(archivo)
    nombre = f"{uuid.uuid4().hex}{ext}"
    clave = f"{carpeta}/{nombre}"

    if get_settings().STORAGE_BACKEND == "s3":
        from . import storage_s3

        storage_s3.subir(archivo, clave, _max_bytes())
        return clave

    destino = _directorio_base() / carpeta
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / nombre

    leidos = 0
    try:
        with ruta.open("wb") as out:
            while True:
                chunk = archivo.file.read(_TAMANO_CHUNK)
                if not chunk:
                    break
                leidos += len(chunk)
                if leidos > _max_bytes():
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=(
                            "El archivo supera el máximo permitido "
                            f"({_max_bytes() // (1024 * 1024)} MB)."
                        ),
                    )
                out.write(chunk)
    except Exception:
        # Un parcial en disco es peor que nada: ocupa lugar y ninguna fila lo
        # referencia, así que nadie lo va a limpiar nunca.
        ruta.unlink(missing_ok=True)
        raise

    return clave


def _ruta_local(clave: str) -> Path:
    """Resuelve la clave dentro del directorio base, rechazando cualquier
    intento de salirse (`..`, rutas absolutas)."""
    base = _directorio_base().resolve()
    ruta = (base / clave).resolve()
    if not ruta.is_relative_to(base):
        raise FileNotFoundError(clave)
    return ruta


def abrir_archivo(clave: str) -> tuple[Iterator[bytes], str]:
    """Devuelve `(chunks, content_type)` para servir el archivo.

    Eleva `FileNotFoundError` si no existe o si la clave intenta salirse del
    directorio base.
    """
    if get_settings().STORAGE_BACKEND == "s3":
        from . import storage_s3

        return storage_s3.abrir(clave)

    ruta = _ruta_local(clave)
    if not ruta.is_file():
        raise FileNotFoundError(clave)

    content_type = _TIPOS_POR_EXTENSION.get(
        ruta.suffix.lower(), "application/octet-stream"
    )

    def _chunks() -> Iterator[bytes]:
        with ruta.open("rb") as f:
            while True:
                chunk = f.read(_TAMANO_CHUNK)
                if not chunk:
                    break
                yield chunk

    return _chunks(), content_type
```

- [ ] **Step 5: Correr los tests nuevos**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_archivos.py -q`
Expected: PASS (6 tests).

- [ ] **Step 6: Apuntar los dos routers a la interfaz nueva**

En `backend/routers/comprobantes.py`, cambiar el import:

```python
from ..storage import guardar_archivo
```

y la llamada de `presentar_comprobante` (línea ~109):

```python
    archivo_path = guardar_archivo(archivo, "comprobantes")
```

En `backend/routers/presupuestos.py`, borrar `_guardar_archivo` completa (líneas 47-62) junto con las constantes `ALLOWED_EXTS` y `MAX_ARCHIVO_BYTES` (líneas 29-30) si no se usan en otro lado — verificar con `grep -n "ALLOWED_EXTS\|MAX_ARCHIVO_BYTES" backend/routers/presupuestos.py`. Agregar el import:

```python
from ..storage import guardar_archivo
```

y reemplazar cada llamada a `_guardar_archivo(archivo)` por `guardar_archivo(archivo, "presupuestos")`.

**Ojo con el cambio de criterio:** `_guardar_archivo` validaba por extensión del filename y `guardar_archivo` valida por `content_type`. Los tests de `tests/test_presupuestos.py` que suben archivos tienen que mandar el `content_type` correcto en la tupla del multipart; si alguno falla con 400, ese es el motivo y el arreglo va en el test, no en `storage.py` — confiar en la extensión que manda el cliente es justamente lo que se está sacando.

- [ ] **Step 7: Correr el suite completo**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: todo verde. Si fallan tests de presupuestos, ver la nota del paso anterior.

- [ ] **Step 8: Commit**

```bash
git add backend/storage.py backend/config.py backend/routers/comprobantes.py backend/routers/presupuestos.py tests/test_archivos.py
git commit -m "refactor: una sola interfaz de almacenamiento para comprobantes y presupuestos"
```

---

### Task 2: URLs firmadas y endpoint público que las valida

**Files:**
- Modify: `backend/storage.py` (agregar firma y verificación)
- Create: `backend/routers/archivos.py`
- Modify: `backend/main.py` (sacar el mount de `/uploads`, agregar el router)
- Modify: `tests/test_archivos.py`

**Interfaces:**
- Consumes: `abrir_archivo(clave)` de la Tarea 1; `Settings.SECRET_KEY` y `Settings.URL_FIRMADA_SEGUNDOS`.
- Produces:
  - `firmar_clave(clave: str, segundos: int | None = None) -> str` — devuelve la ruta relativa firmada, `"/archivos/<clave>?exp=<epoch>&firma=<hex>"`.
  - `verificar_firma(clave: str, exp: str, firma: str) -> bool`.
  - Endpoint público `GET /archivos/{clave:path}?exp=&firma=`.

- [ ] **Step 1: Escribir los tests (fallan)**

Agregar a `tests/test_archivos.py`:

```python
import time


def test_firma_valida_se_verifica_ok():
    ruta = storage.firmar_clave("comprobantes/abc.jpg", segundos=60)
    assert ruta.startswith("/archivos/comprobantes/abc.jpg?")
    exp = ruta.split("exp=")[1].split("&")[0]
    firma = ruta.split("firma=")[1]
    assert storage.verificar_firma("comprobantes/abc.jpg", exp, firma) is True


def test_firma_vencida_se_rechaza():
    ruta = storage.firmar_clave("comprobantes/abc.jpg", segundos=-1)
    exp = ruta.split("exp=")[1].split("&")[0]
    firma = ruta.split("firma=")[1]
    assert storage.verificar_firma("comprobantes/abc.jpg", exp, firma) is False


def test_firma_de_otra_clave_no_sirve():
    """Sin esto, firmar un archivo propio daría acceso a cualquier otro."""
    ruta = storage.firmar_clave("comprobantes/mio.jpg", segundos=60)
    exp = ruta.split("exp=")[1].split("&")[0]
    firma = ruta.split("firma=")[1]
    assert storage.verificar_firma("comprobantes/ajeno.jpg", exp, firma) is False


def test_firma_adulterada_se_rechaza():
    ruta = storage.firmar_clave("comprobantes/abc.jpg", segundos=60)
    exp = ruta.split("exp=")[1].split("&")[0]
    assert storage.verificar_firma("comprobantes/abc.jpg", exp, "0" * 64) is False


def test_exp_adulterado_se_rechaza():
    """Estirar el vencimiento tiene que invalidar la firma, porque `exp` está
    dentro de lo firmado."""
    ruta = storage.firmar_clave("comprobantes/abc.jpg", segundos=60)
    firma = ruta.split("firma=")[1]
    futuro = str(int(time.time()) + 999999)
    assert storage.verificar_firma("comprobantes/abc.jpg", futuro, firma) is False


def test_endpoint_de_archivos_sirve_con_firma_valida(client, tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_directorio_base", lambda: tmp_path)
    clave = storage.guardar_archivo(
        _upload("r.png", b"png-falso", "image/png"), "comprobantes"
    )

    r = client.get(storage.firmar_clave(clave, segundos=60))

    assert r.status_code == 200
    assert r.content == b"png-falso"
    assert r.headers["content-type"].startswith("image/png")


def test_endpoint_de_archivos_rechaza_sin_firma(client, tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_directorio_base", lambda: tmp_path)
    clave = storage.guardar_archivo(
        _upload("r.png", b"png-falso", "image/png"), "comprobantes"
    )

    assert client.get(f"/archivos/{clave}").status_code == 403


def test_uploads_ya_no_se_sirve_estatico(client):
    """El montaje publico de /uploads era el agujero: cualquiera con la URL
    abria el comprobante de cualquier vecino sin estar logueado."""
    assert client.get("/uploads/comprobantes/loquesea.jpg").status_code == 404
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_archivos.py -q`
Expected: FAIL — `firmar_clave` no existe y `/uploads` todavía responde.

- [ ] **Step 3: Agregar firma y verificación a `backend/storage.py`**

Al final del módulo:

```python
def firmar_clave(clave: str, segundos: int | None = None) -> str:
    """Devuelve una ruta de descarga con firma y vencimiento.

    Se firma `clave:exp` juntos: firmar sólo la clave permitiría estirar el
    vencimiento, y firmar sólo el exp permitiría reusar la firma para otro
    archivo.
    """
    import hashlib
    import hmac
    import time

    settings = get_settings()
    if segundos is None:
        segundos = settings.URL_FIRMADA_SEGUNDOS
    exp = int(time.time()) + segundos
    firma = hmac.new(
        settings.SECRET_KEY.encode(),
        f"{clave}:{exp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"/archivos/{clave}?exp={exp}&firma={firma}"


def verificar_firma(clave: str, exp: str, firma: str) -> bool:
    """True si la firma corresponde a esa clave y todavía no venció."""
    import hashlib
    import hmac
    import time

    try:
        vencimiento = int(exp)
    except (TypeError, ValueError):
        return False
    if vencimiento < time.time():
        return False

    esperada = hmac.new(
        get_settings().SECRET_KEY.encode(),
        f"{clave}:{vencimiento}".encode(),
        hashlib.sha256,
    ).hexdigest()
    # compare_digest y no ==: la comparación normal corta en el primer byte
    # distinto y filtra la firma correcta byte a byte por tiempo de respuesta.
    return hmac.compare_digest(esperada, firma or "")
```

- [ ] **Step 4: Crear `backend/routers/archivos.py`**

```python
"""Entrega de archivos subidos contra una URL firmada.

Este router es **público a propósito**: no puede exigir `Authorization` porque
lo consumen `<img src>` y `<a href>`, que no mandan headers. La autorización ya
ocurrió antes, cuando el usuario pidió la URL a un endpoint autenticado que
verificó que el archivo le correspondía; acá sólo se comprueba que la firma sea
auténtica y que no haya vencido.
"""
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ..storage import abrir_archivo, verificar_firma

router = APIRouter(prefix="/archivos", tags=["Archivos"])


@router.get(
    "/{clave:path}",
    summary="Descargar un archivo con URL firmada",
    response_class=StreamingResponse,
)
def descargar_archivo(
    clave: str,
    exp: str = Query(default=""),
    firma: str = Query(default=""),
) -> StreamingResponse:
    if not verificar_firma(clave, exp, firma):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enlace invalido o vencido.",
        )

    try:
        chunks, content_type = abrir_archivo(clave)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado."
        )

    return StreamingResponse(
        chunks,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=60"},
    )
```

- [ ] **Step 5: Sacar el mount público y registrar el router**

En `backend/main.py`, borrar el bloque de las líneas 175-178:

```python
_uploads_path = Path(get_settings().UPLOAD_DIR)
_uploads_path.mkdir(parents=True, exist_ok=True)
(_uploads_path / "comprobantes").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_path)), name="uploads")
```

Borrar también `from fastapi.staticfiles import StaticFiles` (línea 9) y el import de `Path` si queda sin uso — verificar con `grep -n "StaticFiles\|Path(" backend/main.py`.

Agregar `archivos` a la lista de imports de `.routers` y registrarlo junto a los demás:

```python
app.include_router(archivos.router)
```

- [ ] **Step 6: Correr los tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_archivos.py -q`
Expected: PASS (14 tests).

- [ ] **Step 7: Correr el suite completo**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: verde. Si algún test esperaba `/uploads/...`, actualizarlo: ese camino ya no existe.

- [ ] **Step 8: Commit**

```bash
git add backend/storage.py backend/routers/archivos.py backend/main.py tests/test_archivos.py
git commit -m "feat: los archivos se sirven con URL firmada y se cierra el montaje publico"
```

---

### Task 3: Endpoints autenticados que entregan la URL, con aislamiento

**Files:**
- Modify: `backend/schemas.py` (sacar el serializer de `ComprobanteOut`, agregar `ArchivoUrlOut`)
- Modify: `backend/routers/comprobantes.py`
- Modify: `backend/routers/presupuestos.py`
- Modify: `tests/test_archivos.py`

**Interfaces:**
- Consumes: `firmar_clave(clave)` de la Tarea 2.
- Produces:
  - `ArchivoUrlOut(BaseModel)` con campos `url: str` y `expira_en: int`.
  - `GET /comprobantes/{comprobante_id}/archivo` → `ArchivoUrlOut`
  - `GET /trabajos/{trabajo_id}/presupuestos/{presupuesto_id}/archivo` → `ArchivoUrlOut`

- [ ] **Step 1: Escribir los tests (fallan)**

Agregar a `tests/test_archivos.py`. Usar los fixtures de usuarios que ya existen en `tests/conftest.py` (mismo patrón que `tests/test_idor_multitenant.py` — revisarlo antes para copiar los nombres exactos de los fixtures de token por rol):

```python
def test_depto_obtiene_la_url_de_su_propio_comprobante(client, token_depto_a, comprobante_de_a):
    r = client.get(
        f"/comprobantes/{comprobante_de_a.id}/archivo",
        headers={"Authorization": f"Bearer {token_depto_a}", "X-Consorcio-Id": "1"},
    )

    assert r.status_code == 200
    assert r.json()["url"].startswith("/archivos/comprobantes/")
    assert r.json()["expira_en"] > 0


def test_depto_no_obtiene_la_url_del_comprobante_de_otro(client, token_depto_b, comprobante_de_a):
    """El agujero que se esta cerrando: son fotos de transferencias bancarias."""
    r = client.get(
        f"/comprobantes/{comprobante_de_a.id}/archivo",
        headers={"Authorization": f"Bearer {token_depto_b}", "X-Consorcio-Id": "1"},
    )

    assert r.status_code == 404


def test_sin_token_no_se_obtiene_ninguna_url(client, comprobante_de_a):
    r = client.get(f"/comprobantes/{comprobante_de_a.id}/archivo")
    assert r.status_code == 401


def test_admin_obtiene_la_url_de_cualquier_comprobante_de_su_consorcio(
    client, token_admin, comprobante_de_a
):
    r = client.get(
        f"/comprobantes/{comprobante_de_a.id}/archivo",
        headers={"Authorization": f"Bearer {token_admin}", "X-Consorcio-Id": "1"},
    )
    assert r.status_code == 200


def test_comprobante_sin_archivo_devuelve_404(client, token_admin, comprobante_sin_archivo):
    r = client.get(
        f"/comprobantes/{comprobante_sin_archivo.id}/archivo",
        headers={"Authorization": f"Bearer {token_admin}", "X-Consorcio-Id": "1"},
    )
    assert r.status_code == 404
```

Los fixtures `comprobante_de_a` y `comprobante_sin_archivo` hay que agregarlos en `tests/conftest.py` si no existen equivalentes; revisar primero qué comprobantes siembra `_seed`.

- [ ] **Step 2: Correr y verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_archivos.py -q -k "url or comprobante"`
Expected: FAIL — el endpoint devuelve 404 porque no existe.

- [ ] **Step 3: Agregar el schema de salida**

En `backend/schemas.py`, junto a los demás `*Out`:

```python
class ArchivoUrlOut(BaseModel):
    """URL de vida corta para abrir un archivo adjunto.

    Se entrega por separado del recurso porque `<img src>` no manda headers:
    el frontend pide esto con su token y usa la URL resultante como src.
    """

    url: str
    expira_en: int
```

Y **sacar** el serializer de `ComprobanteOut` (líneas 179-183), que fabricaba `/uploads/...`:

```python
    @field_serializer("archivo_path")
    def _archivo_path_to_url(self, v: str | None) -> str | None:
        if v is None:
            return None
        return f"/uploads/{v}"
```

`archivo_path` pasa a devolver la clave cruda, igual que ya hacía `PresupuestoOut`. El frontend no la usa para armar URLs: sólo para saber **si hay** archivo.

Verificar que `field_serializer` siga importado y usado por otros schemas; si queda sin uso, sacar el import.

- [ ] **Step 4: Agregar el endpoint de comprobantes**

En `backend/routers/comprobantes.py`, después de `listar_comprobantes`:

```python
@router.get(
    "/{comprobante_id}/archivo",
    response_model=ArchivoUrlOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener la URL firmada del comprobante",
)
def url_del_comprobante(
    comprobante_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.departamento)),
    cid: int = Depends(get_consorcio_activo),
) -> ArchivoUrlOut:
    comprobante = db.get(Comprobante, comprobante_id)
    # Un 403 distinguido de un 404 le confirmaría al que prueba ids que ese
    # comprobante existe. Todo lo que no le corresponde es 404.
    if (
        comprobante is None
        or comprobante.consorcio_id != cid
        or comprobante.eliminado_at is not None
        or not comprobante.archivo_path
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comprobante no encontrado."
        )
    if (
        user.rol == Rol.departamento
        and comprobante.departamento_id != user.departamento_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comprobante no encontrado."
        )

    return ArchivoUrlOut(
        url=firmar_clave(comprobante.archivo_path),
        expira_en=get_settings().URL_FIRMADA_SEGUNDOS,
    )
```

Agregar los imports que falten: `ArchivoUrlOut` desde `..schemas`, `firmar_clave` desde `..storage`, `get_settings` desde `..config`.

- [ ] **Step 5: Agregar el endpoint de presupuestos**

En `backend/routers/presupuestos.py`, con el mismo criterio de rol que `listar_presupuestos` (cualquier usuario autenticado del consorcio; el aislamiento lo da `_validar_trabajo`):

```python
@router.get(
    "/{trabajo_id}/presupuestos/{presupuesto_id}/archivo",
    response_model=ArchivoUrlOut,
    summary="Obtener la URL firmada del presupuesto",
)
def url_del_presupuesto(
    trabajo_id: int,
    presupuesto_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> ArchivoUrlOut:
    _validar_trabajo(db, cid, trabajo_id)
    presupuesto = db.get(Presupuesto, presupuesto_id)
    if (
        presupuesto is None
        or presupuesto.trabajo_id != trabajo_id
        or not presupuesto.archivo_path
    ):
        raise HTTPException(404, "Presupuesto no encontrado.")

    return ArchivoUrlOut(
        url=firmar_clave(presupuesto.archivo_path),
        expira_en=get_settings().URL_FIRMADA_SEGUNDOS,
    )
```

- [ ] **Step 6: Correr el suite completo**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: verde.

- [ ] **Step 7: Actualizar el contrato OpenAPI**

El proyecto es OpenAPI-first (`.claude/rules/openapi-first.md`). Agregar a `openapi.yaml` los dos endpoints nuevos y el schema `ArchivoUrlOut`, y sacar cualquier referencia a `/uploads`.

- [ ] **Step 8: Commit**

```bash
git add backend/schemas.py backend/routers/comprobantes.py backend/routers/presupuestos.py tests/ openapi.yaml
git commit -m "feat: la URL de un adjunto se pide autenticada y solo la da quien tiene derecho"
```

---

### Task 4: Backend S3-compatible

**Files:**
- Create: `backend/storage_s3.py`
- Modify: `requirements.txt`
- Modify: `tests/test_archivos.py`

**Interfaces:**
- Consumes: `Settings.S3_*`.
- Produces, usadas por `backend/storage.py` (Tarea 1):
  - `subir(archivo: UploadFile, clave: str, max_bytes: int) -> None`
  - `abrir(clave: str) -> tuple[Iterator[bytes], str]`

**No se testea contra un bucket real.** Los tests usan un doble del cliente boto3: lo que se verifica es que se llame con el bucket y la clave correctos, no que Amazon funcione.

- [ ] **Step 1: Agregar la dependencia**

En `requirements.txt`, debajo de `psycopg2-binary>=2.9`:

```
boto3>=1.34
```

Instalar: `./.venv/Scripts/python.exe -m pip install -r requirements.txt`

- [ ] **Step 2: Escribir los tests (fallan)**

Agregar a `tests/test_archivos.py`:

```python
class _ClienteS3Falso:
    """Doble del cliente boto3: registra las llamadas en vez de salir a la red."""

    def __init__(self):
        self.objetos: dict[str, bytes] = {}
        self.puestos: list[dict] = []

    def put_object(self, **kwargs):
        self.puestos.append(kwargs)
        self.objetos[kwargs["Key"]] = kwargs["Body"].read()

    def get_object(self, Bucket, Key):
        if Key not in self.objetos:
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        contenido = self.objetos[Key]

        class _Cuerpo:
            def iter_chunks(self, chunk_size=8192):
                yield contenido

        return {"Body": _Cuerpo(), "ContentType": "image/png"}


def test_backend_s3_sube_con_el_bucket_y_la_clave_correctos(monkeypatch):
    from backend import storage_s3

    falso = _ClienteS3Falso()
    monkeypatch.setattr(storage_s3, "_cliente", lambda: falso)
    monkeypatch.setattr(storage_s3, "_bucket", lambda: "comprobantes-test")

    storage_s3.subir(_upload("r.png", b"png-falso", "image/png"), "comprobantes/x.png", 1000)

    assert falso.puestos[0]["Bucket"] == "comprobantes-test"
    assert falso.puestos[0]["Key"] == "comprobantes/x.png"
    assert falso.puestos[0]["ContentType"] == "image/png"


def test_backend_s3_rechaza_archivo_demasiado_grande(monkeypatch):
    from backend import storage_s3

    falso = _ClienteS3Falso()
    monkeypatch.setattr(storage_s3, "_cliente", lambda: falso)
    monkeypatch.setattr(storage_s3, "_bucket", lambda: "b")

    with pytest.raises(HTTPException) as e:
        storage_s3.subir(_upload("g.png", b"x" * 50, "image/png"), "comprobantes/g.png", 10)

    assert e.value.status_code == 413
    assert falso.puestos == [], "no debe subir nada si excede el limite"


def test_backend_s3_clave_inexistente_levanta_filenotfound(monkeypatch):
    from backend import storage_s3

    monkeypatch.setattr(storage_s3, "_cliente", lambda: _ClienteS3Falso())
    monkeypatch.setattr(storage_s3, "_bucket", lambda: "b")

    with pytest.raises(FileNotFoundError):
        storage_s3.abrir("comprobantes/no-existe.png")
```

- [ ] **Step 3: Correr y verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_archivos.py -q -k s3`
Expected: FAIL — `backend.storage_s3` no existe.

- [ ] **Step 4: Crear `backend/storage_s3.py`**

```python
"""Almacenamiento en un servicio S3-compatible.

Sirve igual para Supabase Storage, Cloudflare R2 y AWS S3: los tres hablan el
mismo protocolo. Lo único que cambia es `S3_ENDPOINT_URL`.

Este módulo no tiene lógica de negocio: valida tamaño y mueve bytes. La
validación de tipo, la generación de la clave y la firma viven en
`backend/storage.py`, que es la interfaz que ven los routers.
"""
from collections.abc import Iterator
from functools import lru_cache

from fastapi import HTTPException, UploadFile, status

from .config import get_settings

_TAMANO_CHUNK = 64 * 1024


@lru_cache(maxsize=1)
def _cliente():
    import boto3

    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.S3_ENDPOINT_URL or None,
        region_name=s.S3_REGION,
        aws_access_key_id=s.S3_ACCESS_KEY_ID,
        aws_secret_access_key=s.S3_SECRET_ACCESS_KEY,
    )


def _bucket() -> str:
    return get_settings().S3_BUCKET


def subir(archivo: UploadFile, clave: str, max_bytes: int) -> None:
    """Sube el archivo bajo `clave`.

    Se lee entero en memoria antes de subir para poder cortar por tamaño sin
    dejar un objeto parcial arriba. Con el límite en 5 MB es aceptable; si
    algún día sube, hay que pasar a subida multiparte con corte por chunk.
    """
    contenido = archivo.file.read(max_bytes + 1)
    if len(contenido) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"El archivo supera el máximo permitido ({max_bytes // (1024 * 1024)} MB).",
        )

    import io

    _cliente().put_object(
        Bucket=_bucket(),
        Key=clave,
        Body=io.BytesIO(contenido),
        ContentType=archivo.content_type or "application/octet-stream",
    )


def abrir(clave: str) -> tuple[Iterator[bytes], str]:
    """Devuelve `(chunks, content_type)`. Eleva `FileNotFoundError` si no está."""
    from botocore.exceptions import ClientError

    try:
        respuesta = _cliente().get_object(Bucket=_bucket(), Key=clave)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404", "NotFound"):
            raise FileNotFoundError(clave) from e
        raise

    cuerpo = respuesta["Body"]
    content_type = respuesta.get("ContentType", "application/octet-stream")
    return cuerpo.iter_chunks(chunk_size=_TAMANO_CHUNK), content_type
```

- [ ] **Step 5: Correr los tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_archivos.py -q`
Expected: PASS.

- [ ] **Step 6: Correr el suite completo**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: verde. El backend por defecto sigue siendo `local`, así que nada más cambia.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt backend/storage_s3.py tests/test_archivos.py
git commit -m "feat: backend de almacenamiento S3-compatible detras de la misma interfaz"
```

---

### Task 5: El frontend pide la URL antes de mostrar el archivo

**Files:**
- Create: `frontend/src/api/archivos.js`
- Create: `frontend/src/components/ArchivoAdjunto.jsx`
- Modify: `frontend/src/screens/Comprobantes.jsx` (líneas ~256, ~352)
- Modify: `frontend/src/screens/MiCuenta.jsx` (línea ~297)
- Modify: `frontend/src/components/ModalComprobantesExpensa.jsx` (línea ~99)
- Modify: `frontend/src/components/ModalDetalleTrabajo.jsx` (línea ~165)
- Create: `frontend/src/api/archivos.test.js`

**Interfaces:**
- Consumes: `GET /comprobantes/{id}/archivo` y `GET /trabajos/{t}/presupuestos/{p}/archivo` (Tarea 3); `apiFetch` de `frontend/src/api/client.js`.
- Produces: `<ArchivoAdjunto ruta={...} alt={...} />`, donde `ruta` es la ruta del endpoint que devuelve la URL firmada.

- [ ] **Step 1: Escribir el test del helper (falla)**

Crear `frontend/src/api/archivos.test.js`:

```javascript
import { describe, expect, it, vi, beforeEach } from "vitest";

import { urlDeArchivo } from "./archivos";

describe("urlDeArchivo", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("devuelve la ruta tal cual si es un archivo estatico de la demo", async () => {
    // La demo no tiene backend: sus comprobantes son archivos servidos por
    // Vercel. Pedirle una firma al servidor colgaria la pantalla entera.
    const url = await urlDeArchivo("/demo-comprobantes/uf01.png");
    expect(url).toBe("/demo-comprobantes/uf01.png");
  });

  it("pide la url firmada al backend y la prefija con el host de la api", async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      ok: true,
      data: { url: "/archivos/comprobantes/abc.jpg?exp=1&firma=ff", expira_en: 300 },
    });

    const url = await urlDeArchivo("/comprobantes/7/archivo", { apiFetch });

    expect(apiFetch).toHaveBeenCalledWith("/comprobantes/7/archivo");
    expect(url).toContain("/archivos/comprobantes/abc.jpg?exp=1&firma=ff");
  });

  it("devuelve null si el backend no da la url", async () => {
    const apiFetch = vi.fn().mockResolvedValue({ ok: false, status: 404 });
    expect(await urlDeArchivo("/comprobantes/7/archivo", { apiFetch })).toBeNull();
  });
});
```

- [ ] **Step 2: Correr y verificar que falla**

Run (desde `frontend/`): `npm test -- archivos`
Expected: FAIL — el módulo no existe.

- [ ] **Step 3: Crear `frontend/src/api/archivos.js`**

```javascript
import { API_BASE, apiFetch as apiFetchReal } from "./client";

/**
 * Resuelve la URL con la que se puede mostrar o descargar un adjunto.
 *
 * Hace falta este paso extra porque `<img src>` y `<a href>` no mandan el
 * header de autorizacion: el permiso se verifica en esta llamada, y lo que
 * vuelve es una URL firmada de vida corta que ya sirve sin token.
 *
 * @param {string} ruta - ruta del endpoint que devuelve la URL firmada, o una
 *   ruta estatica de la demo (`/demo-comprobantes/...`), que se usa directo.
 * @returns {Promise<string|null>} la URL, o null si no se pudo obtener.
 */
export async function urlDeArchivo(ruta, { apiFetch = apiFetchReal } = {}) {
  if (!ruta) return null;
  if (ruta.startsWith("/demo-comprobantes/")) return ruta;

  const res = await apiFetch(ruta);
  if (!res.ok || !res.data?.url) return null;
  return `${API_BASE}${res.data.url}`;
}
```

- [ ] **Step 4: Correr el test**

Run (desde `frontend/`): `npm test -- archivos`
Expected: PASS (3 tests).

- [ ] **Step 5: Crear `frontend/src/components/ArchivoAdjunto.jsx`**

```jsx
import { useEffect, useState } from "react";

import { urlDeArchivo } from "../api/archivos";

/**
 * Miniatura clickeable de un adjunto. Resuelve la URL firmada al montarse.
 *
 * Mientras resuelve muestra un placeholder en vez de un `img` sin src: un src
 * vacio dispara un pedido al documento actual y ensucia la consola.
 */
export default function ArchivoAdjunto({ ruta, alt, className = "comprobante-thumb" }) {
  const [url, setUrl] = useState(null);
  const [fallo, setFallo] = useState(false);

  useEffect(() => {
    let vigente = true;
    setUrl(null);
    setFallo(false);
    urlDeArchivo(ruta).then((u) => {
      if (!vigente) return;
      if (u) setUrl(u);
      else setFallo(true);
    });
    return () => {
      vigente = false;
    };
  }, [ruta]);

  if (fallo) return <span className="adjunto-error">No disponible</span>;
  if (!url) return <span className="adjunto-cargando" aria-busy="true">…</span>;

  return (
    <a href={url} target="_blank" rel="noopener noreferrer">
      <img src={url} alt={alt} className={className} />
    </a>
  );
}
```

- [ ] **Step 6: Reemplazar los cinco usos**

En `frontend/src/screens/Comprobantes.jsx` (~256 y ~352), `frontend/src/screens/MiCuenta.jsx` (~297) y `frontend/src/components/ModalComprobantesExpensa.jsx` (~99), reemplazar el bloque `<a href={...}><img src={...} /></a>` por:

```jsx
<ArchivoAdjunto
  ruta={c.archivo_path?.startsWith("/demo-comprobantes/") ? c.archivo_path : `/comprobantes/${c.id}/archivo`}
  alt={`Comprobante del ${formatFecha(c.fecha_pago)}`}
/>
```

En `frontend/src/components/ModalDetalleTrabajo.jsx` (~165), con la ruta anidada del presupuesto:

```jsx
<ArchivoAdjunto
  ruta={`/trabajos/${trabajo.id}/presupuestos/${p.id}/archivo`}
  alt={`Presupuesto de ${p.proveedor_nombre ?? "proveedor"}`}
/>
```

Verificar el nombre de la variable del trabajo en ese componente antes de escribirlo. Agregar el import de `ArchivoAdjunto` en los cinco archivos y sacar los de `API_BASE` que queden sin uso.

- [ ] **Step 7: Agregar el estilo de los dos estados nuevos**

En la hoja de estilos donde vive `.comprobante-thumb`, agregar `.adjunto-cargando` y `.adjunto-error` con el mismo alto que la miniatura, para que la fila no salte cuando la imagen aparece.

- [ ] **Step 8: Que el servidor simulado de la demo responda el endpoint nuevo**

En `frontend/src/demo/servidor.js`, agregar el manejo de `GET /comprobantes/{id}/archivo` devolviendo `{url: <archivo_path del comprobante>, expira_en: 300}`. Sin esto, la demo muestra "No disponible" en cada comprobante.

Verificar contra `frontend/src/demo/recorrido.test.js:115-118`, que ya asserta que los `archivo_path` del dataset empiezan con `/demo-comprobantes/`.

- [ ] **Step 9: Correr los tests del frontend**

Run (desde `frontend/`): `npm test`
Expected: verde.

- [ ] **Step 10: Verificar a ojo**

Levantar backend y frontend y comprobar, logueado como departamento, que la miniatura del comprobante se ve y que el enlace abre el archivo. Después copiar esa URL, cerrar sesión, esperar a que venza y confirmar que ya no abre.

- [ ] **Step 11: Commit**

```bash
git add frontend/src
git commit -m "feat: el frontend pide la url firmada antes de mostrar un adjunto"
```

---

### Task 6: Migrar los archivos que ya están en disco

**Files:**
- Create: `backend/migrar_archivos.py`
- Modify: `tests/test_archivos.py`

**Interfaces:**
- Consumes: `backend.storage_s3.subir` (Tarea 4).
- Produces: `python -m backend.migrar_archivos` — sube al almacén externo todo lo que haya bajo `UPLOAD_DIR`.

- [ ] **Step 1: Escribir el test (falla)**

```python
def test_migrar_archivos_sube_todo_lo_que_hay_en_disco(tmp_path, monkeypatch):
    from backend import migrar_archivos, storage_s3

    (tmp_path / "comprobantes").mkdir()
    (tmp_path / "comprobantes" / "a.jpg").write_bytes(b"uno")
    (tmp_path / "presupuestos").mkdir()
    (tmp_path / "presupuestos" / "b.pdf").write_bytes(b"dos")

    subidos = {}
    monkeypatch.setattr(
        storage_s3, "_cliente", lambda: type("C", (), {
            "put_object": lambda self, **kw: subidos.update({kw["Key"]: kw["Body"].read()})
        })()
    )
    monkeypatch.setattr(storage_s3, "_bucket", lambda: "b")

    resultado = migrar_archivos.migrar(tmp_path)

    assert resultado["subidos"] == 2
    assert subidos["comprobantes/a.jpg"] == b"uno"
    assert subidos["presupuestos/b.pdf"] == b"dos"
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_archivos.py -q -k migrar`
Expected: FAIL.

- [ ] **Step 3: Crear `backend/migrar_archivos.py`**

```python
"""Sube al almacén externo los archivos que hoy viven en el disco local.

Se corre una sola vez, al mover un entorno de `STORAGE_BACKEND=local` a `s3`.
Es idempotente en el sentido que importa: subir dos veces el mismo objeto lo
sobrescribe con contenido idéntico.

Uso:
    STORAGE_BACKEND=s3 S3_BUCKET=... python -m backend.migrar_archivos
"""
import io
import sys
from pathlib import Path

from .config import get_settings


def migrar(directorio: Path) -> dict:
    """Sube todos los archivos bajo `directorio`, usando su ruta relativa como
    clave. Devuelve un resumen."""
    from . import storage_s3

    subidos = 0
    fallados: list[str] = []

    for ruta in sorted(directorio.rglob("*")):
        if not ruta.is_file():
            continue
        clave = ruta.relative_to(directorio).as_posix()
        try:
            storage_s3._cliente().put_object(
                Bucket=storage_s3._bucket(),
                Key=clave,
                Body=io.BytesIO(ruta.read_bytes()),
            )
            subidos += 1
            print(f"[migrar] {clave}")
        except Exception as e:  # noqa: BLE001 — se reporta y se sigue
            fallados.append(f"{clave}: {e}")

    return {"subidos": subidos, "fallados": fallados}


def main() -> int:
    settings = get_settings()
    if settings.STORAGE_BACKEND != "s3":
        print("STORAGE_BACKEND debe ser 's3' para migrar.", file=sys.stderr)
        return 1

    directorio = Path(settings.UPLOAD_DIR)
    if not directorio.is_dir():
        print(f"No existe {directorio}: nada que migrar.")
        return 0

    resultado = migrar(directorio)
    print(f"\n[migrar] subidos: {resultado['subidos']}")
    for f in resultado["fallados"]:
        print(f"[migrar] FALLO {f}", file=sys.stderr)
    return 1 if resultado["fallados"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Correr los tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_archivos.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/migrar_archivos.py tests/test_archivos.py
git commit -m "feat: script para migrar al almacen externo los archivos ya subidos"
```

---

### Task 7: Documentación y variables de entorno

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Documentar las variables**

Agregar a `.env.example`:

```
# --- Almacenamiento de archivos subidos ---
# local: disco (desarrollo y tests). s3: cualquier almacen S3-compatible.
STORAGE_BACKEND=local
# Segundos que vive la URL firmada de un adjunto.
URL_FIRMADA_SEGUNDOS=300
# Solo con STORAGE_BACKEND=s3. Ejemplos de endpoint:
#   Supabase:   https://<PROJECT_REF>.supabase.co/storage/v1/s3
#   Cloudflare: https://<ACCOUNT_ID>.r2.cloudflarestorage.com
#   AWS S3:     dejar vacio
S3_ENDPOINT_URL=
S3_REGION=auto
S3_BUCKET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
```

- [ ] **Step 2: Documentar el circuito en el README**

Agregar una sección "Archivos adjuntos" explicando: que los adjuntos no se sirven públicamente; el flujo de dos pasos y por qué (`<img>` no manda headers); que `local` es el default y no necesita configuración; y los pasos para pasar a `s3` — crear el bucket **privado**, cargar las cinco variables, correr `python -m backend.migrar_archivos`, y recién ahí cambiar `STORAGE_BACKEND`.

Incluir la advertencia: **el bucket tiene que ser privado.** Si queda público, la firma no protege nada porque el objeto es accesible por su URL directa.

- [ ] **Step 3: Verificación final del frente**

```bash
./.venv/Scripts/python.exe -m pytest -q
grep -rn "StaticFiles\|/uploads" backend/ frontend/src/
```

Expected: suite completo verde; ninguna referencia viva a `/uploads` ni a `StaticFiles`.

- [ ] **Step 4: Commit**

```bash
git add .env.example README.md
git commit -m "docs: documentar el almacenamiento de adjuntos y como pasar al almacen externo"
```

---

## Self-Review

**Cobertura de la spec (Frente 2):**

| Requisito de la spec | Tarea |
|---|---|
| Reescribir `storage.py` como interfaz con backend local y S3 | 1 y 4 |
| Unificar `_guardar_archivo` de presupuestos contra esa interfaz | 1 |
| Quitar el `mount("/uploads", StaticFiles(...))` | 2 |
| Endpoint autenticado que valida rol y pertenencia | 3 |
| Redirección/entrega vía URL firmada de corta vida | 2 y 3 |
| Mantener el frontend con cambio mínimo, emparejando `ModalDetalleTrabajo` | 5 |
| Script de migración de archivos existentes | 6 |
| Tests: aislamiento entre departamentos, expiración de la firma, camino local sin red | 1, 2, 3, 4 |

**Desvío consciente respecto de la spec:** la spec anticipaba "una redirección a una URL firmada". Se entrega en su lugar un JSON con la URL, porque una redirección desde un endpoint con `Authorization` no resuelve el problema de fondo — `<img src>` nunca habría llegado a mandar ese header. El resultado para el usuario es el mismo y el contrato es explícito.

**Riesgo residual conocido:** una URL firmada válida es transferible durante su ventana de vida (cinco minutos por defecto). Es el mismo modelo que usan todos los almacenes de objetos y es aceptable para este caso; si alguna vez hiciera falta más, la firma tendría que atarse también al usuario que la pidió.

**Verificación de tipos y nombres:** `guardar_archivo(archivo, carpeta)` se define en la Tarea 1 y se usa con esa firma en las Tareas 1 y 4. `abrir_archivo(clave) -> (Iterator[bytes], str)` se define en la 1 y se consume en la 2. `firmar_clave`/`verificar_firma` se definen en la 2 y se consumen en la 2 y la 3. `ArchivoUrlOut{url, expira_en}` se define en la 3 y es lo que consume `urlDeArchivo` en la 5. `storage_s3.subir/abrir` se definen en la 4 con las firmas que la Tarea 1 ya invoca.

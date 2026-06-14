# Comprobante con foto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el campo "link al comprobante" por la subida de una imagen (cámara o galería), persistida en `backend/uploads/comprobantes/` y servida como recurso estático.

**Architecture:** El `POST /expensas/{id}/comprobantes` pasa de `application/json` a `multipart/form-data`. La columna `Comprobante.archivo_url` se renombra a `archivo_path` (relativo al `UPLOAD_DIR`). `ComprobanteOut` serializa ese path como URL pública `/uploads/comprobantes/<uuid>.<ext>`. El frontend usa `<input type="file" accept="image/*">` con preview y manda `FormData`.

**Tech Stack:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 + SQLite (in-memory en tests). React + Vite. Sin nuevas dependencias.

**Spec:** [docs/superpowers/specs/2026-06-14-comprobante-foto-design.md](../specs/2026-06-14-comprobante-foto-design.md)

---

## Setup inicial

- [ ] **Step 0: Confirmar rama**

Run: `git status && git branch --show-current`
Expected: rama `feature/expensas-frontend`, working tree limpio.

---

## Fase A — Backend foundation

### Task 1: Config + carpeta uploads + .gitignore

**Files:**
- Modify: `backend/config.py`
- Create: `backend/uploads/comprobantes/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: Sumar `UPLOAD_DIR` y `MAX_UPLOAD_SIZE_BYTES` a `Settings`**

En `backend/config.py`, agregar antes del `@field_validator`:

```python
    UPLOAD_DIR: str = "backend/uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024
```

- [ ] **Step 2: Crear `.gitkeep` para que la carpeta exista en clones**

Crear el archivo vacío `backend/uploads/comprobantes/.gitkeep`.

- [ ] **Step 3: Editar `.gitignore` para ignorar archivos subidos**

Agregar al final de `.gitignore` (verificar primero que no esté ya):

```
# Archivos subidos por usuarios (las imágenes de comprobantes)
backend/uploads/comprobantes/*
!backend/uploads/comprobantes/.gitkeep
```

- [ ] **Step 4: Verificar que el módulo importa**

Run: `./.venv/Scripts/python.exe -c "from backend.config import get_settings; s = get_settings(); print(s.UPLOAD_DIR, s.MAX_UPLOAD_SIZE_BYTES)"`
Expected: imprime `backend/uploads 5242880`.

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/uploads/comprobantes/.gitkeep .gitignore
git commit -m "feat(config): UPLOAD_DIR y MAX_UPLOAD_SIZE_BYTES + carpeta uploads"
```

---

### Task 2: Mount StaticFiles en main.py

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Sumar el mount al final del archivo**

En `backend/main.py`, sumar el import al tope:

```python
from pathlib import Path

from fastapi.staticfiles import StaticFiles
```

Y al final del archivo (después de los `include_router`), agregar:

```python
_uploads_path = Path(get_settings().UPLOAD_DIR)
_uploads_path.mkdir(parents=True, exist_ok=True)
(_uploads_path / "comprobantes").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_path)), name="uploads")
```

- [ ] **Step 2: Smoke test del mount**

Run: `./.venv/Scripts/python.exe -c "from backend.main import app; print([r.path for r in app.routes if 'uploads' in r.path])"`
Expected: imprime `['/uploads']` (o similar).

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat(api): mount StaticFiles en /uploads"
```

---

## Fase B — OpenAPI primero (regla del proyecto)

### Task 3: Documentar el cambio del endpoint y los schemas

**Files:**
- Modify: `openapi.yaml`

- [ ] **Step 1: Cambiar el request body del POST a multipart**

En `openapi.yaml`, ubicar `/expensas/{expensa_id}/comprobantes` → `post:` → `requestBody:` (líneas ~317-322). Reemplazar:

```yaml
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ComprobanteCrear'
```

por:

```yaml
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [fecha_pago, monto]
              properties:
                fecha_pago:
                  type: string
                  format: date
                monto:
                  type: number
                  format: double
                  minimum: 0
                  exclusiveMinimum: true
                archivo:
                  type: string
                  format: binary
                  description: Imagen del comprobante (JPG/PNG/WebP, máx 5 MB).
```

- [ ] **Step 2: Sumar respuesta 413 en el mismo endpoint**

Dentro de `responses:` del mismo endpoint, después de `'404':`, agregar:

```yaml
        '413':
          $ref: '#/components/responses/PayloadGrande'
```

- [ ] **Step 3: Sumar el componente `PayloadGrande`**

En `openapi.yaml`, ubicar `components.responses` (buscar `PedidoInvalido` para encontrar la sección). Agregar al lado de los otros:

```yaml
    PayloadGrande:
      description: Archivo demasiado grande.
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorOut'
```

- [ ] **Step 4: Renombrar `archivo_url` → `archivo_path` en el schema `Comprobante`**

En `components.schemas.Comprobante` (líneas ~1430-1457), reemplazar:

```yaml
        archivo_url:
          type: string
          format: uri
          description: URL del comprobante adjunto.
```

por:

```yaml
        archivo_path:
          type: string
          description: URL pública relativa de la imagen (`/uploads/comprobantes/<uuid>.<ext>`) o `null` si no se adjuntó archivo.
          nullable: true
```

- [ ] **Step 5: Eliminar el schema `ComprobanteCrear`**

En `components.schemas`, borrar el bloque entero `ComprobanteCrear:` (líneas ~1459-1472). Ya no se referencia desde ningún endpoint.

- [ ] **Step 6: Validar YAML**

Run: `./.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml', encoding='utf-8')); print('OK')"`
Expected: imprime `OK`.

- [ ] **Step 7: Commit**

```bash
git add openapi.yaml
git commit -m "docs(openapi): POST comprobante pasa a multipart, archivo_url → archivo_path"
```

---

## Fase C — Modelo + Schemas (precondicional para el router)

### Task 4: Renombrar columna `archivo_url` → `archivo_path` y actualizar schemas

**Files:**
- Modify: `backend/models.py:217`
- Modify: `backend/schemas.py:128-155`

- [ ] **Step 1: Renombrar la columna en `models.py`**

En `backend/models.py` línea 217, reemplazar:

```python
    archivo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
```

por:

```python
    archivo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 2: Borrar `ComprobanteCrear` en `schemas.py`**

En `backend/schemas.py`, borrar el bloque (líneas ~128-131):

```python
class ComprobanteCrear(BaseModel):
    fecha_pago: date
    monto: float = Field(..., gt=0)
    archivo_url: str | None = Field(default=None, max_length=2048)
```

- [ ] **Step 3: Actualizar `ComprobanteOut`: rename + serializer**

En `backend/schemas.py`, ubicar `ComprobanteOut` (líneas ~146-156). Reemplazar el bloque entero por:

```python
class ComprobanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    expensa_id: int
    fecha_pago: date
    monto: float
    archivo_path: str | None
    estado: EstadoComprobante
    expensa: ExpensaResumen | None = None

    @field_serializer("archivo_path")
    def _archivo_path_to_url(self, v: str | None) -> str | None:
        if v is None:
            return None
        return f"/uploads/{v}"
```

- [ ] **Step 4: Sumar el import de `field_serializer`**

En el header de `backend/schemas.py` (línea 4), modificar:

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator
```

por:

```python
from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator
```

- [ ] **Step 5: Limpiar imports muertos en el router**

En `backend/routers/expensas.py` línea 15, reemplazar:

```python
from ..schemas import ComprobanteCrear, ComprobanteOut, ExpensaCrear, ExpensaOut
```

por:

```python
from ..schemas import ComprobanteOut, ExpensaCrear, ExpensaOut
```

(El router se reescribe en Task 8; este paso evita que el archivo no importe en el medio.)

- [ ] **Step 6: Verificar import**

Run: `./.venv/Scripts/python.exe -c "from backend.schemas import ComprobanteOut; from backend.models import Comprobante; print('ok')"`
Expected: imprime `ok`.

- [ ] **Step 7: NO commitear todavía**

En este punto el router está roto (referencia `ComprobanteCrear` interno). Se commitea junto con Task 8.

---

## Fase D — Storage helper

### Task 5: Crear `backend/storage.py`

**Files:**
- Create: `backend/storage.py`

- [ ] **Step 1: Crear el módulo**

Crear `backend/storage.py` con:

```python
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from .config import get_settings


_ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def guardar_imagen_comprobante(archivo: UploadFile) -> str:
    """Persiste una imagen de comprobante en `UPLOAD_DIR/comprobantes/`.

    Devuelve el path relativo al `UPLOAD_DIR` (p. ej. `comprobantes/abc123.jpg`).

    Eleva `HTTPException`:
      - 400 si el `content_type` no es una imagen soportada.
      - 413 si el archivo supera `MAX_UPLOAD_SIZE_BYTES`.
    """
    ext = _ALLOWED_IMAGE_TYPES.get(archivo.content_type or "")
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser una imagen JPG, PNG o WebP.",
        )

    settings = get_settings()
    max_bytes = settings.MAX_UPLOAD_SIZE_BYTES
    upload_dir = Path(settings.UPLOAD_DIR) / "comprobantes"
    upload_dir.mkdir(parents=True, exist_ok=True)

    nombre = f"{uuid.uuid4().hex}{ext}"
    destino = upload_dir / nombre

    leidos = 0
    with destino.open("wb") as out:
        while True:
            chunk = archivo.file.read(64 * 1024)
            if not chunk:
                break
            leidos += len(chunk)
            if leidos > max_bytes:
                out.close()
                destino.unlink(missing_ok=True)
                mb = max_bytes // (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"El archivo supera el máximo permitido ({mb} MB).",
                )
            out.write(chunk)

    return f"comprobantes/{nombre}"
```

- [ ] **Step 2: Verificar import**

Run: `./.venv/Scripts/python.exe -c "from backend.storage import guardar_imagen_comprobante; print('ok')"`
Expected: imprime `ok`.

- [ ] **Step 3: NO commitear todavía**

Se commitea junto con Task 8 (router que lo usa).

---

## Fase E — Conftest + migración de tests

### Task 6: Sumar fixture de UPLOAD_DIR temporal + helper de bytes JPG

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Sumar fixture autouse al final de `conftest.py`**

Antes de `@pytest.fixture()` de `client`, agregar:

```python
@pytest.fixture(autouse=True)
def _temp_upload_dir(tmp_path, monkeypatch) -> Iterator[None]:
    """Apunta `Settings.UPLOAD_DIR` a tmp_path para que los tests no escriban
    en el filesystem real del repo."""
    from backend.config import get_settings as _gs

    upload_root = tmp_path / "uploads"
    (upload_root / "comprobantes").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_gs(), "UPLOAD_DIR", str(upload_root))
    yield
```

- [ ] **Step 2: Verificar que el suite sigue corriendo**

Run: `./.venv/Scripts/python.exe -m pytest -q 2>&1 | tail -5`
Expected: 238 passed (no regresiones).

- [ ] **Step 3: NO commitear todavía**

Se commitea junto con Task 7.

---

### Task 7: Migrar los tests existentes del POST `/comprobantes` a multipart

**Files:**
- Modify: `tests/test_comprobantes.py`

- [ ] **Step 1: Renombrar `archivo_url` → `archivo_path` en el helper `_crear_comprobante`**

Al tope de `tests/test_comprobantes.py`, reemplazar:

```python
def _crear_comprobante(db, expensa_id, fecha_pago, monto, estado):
    c = Comprobante(
        expensa_id=expensa_id,
        fecha_pago=fecha_pago,
        monto=monto,
        archivo_url=None,
        estado=estado,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c
```

por:

```python
def _crear_comprobante(db, expensa_id, fecha_pago, monto, estado):
    c = Comprobante(
        expensa_id=expensa_id,
        fecha_pago=fecha_pago,
        monto=monto,
        archivo_path=None,
        estado=estado,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c
```

- [ ] **Step 2: Reemplazar el `_PAYLOAD_OK` por helpers de multipart**

En `tests/test_comprobantes.py`, ubicar la sección `# POST /expensas/{id}/comprobantes` (~línea 327). Reemplazar:

```python
_PAYLOAD_OK = {
    "fecha_pago": "2026-05-28",
    "monto": 85000.00,
    "archivo_url": "https://files.local/comprobante.pdf",
}
```

por:

```python
_DATA_OK = {"fecha_pago": "2026-05-28", "monto": "85000.00"}


def _imagen_jpg_bytes(size: int = 256) -> bytes:
    """Devuelve `size` bytes que arrancan con el magic header JPEG.
    FastAPI solo mira el content_type del part, no inspecciona el contenido."""
    head = b"\xff\xd8\xff\xe0"  # SOI + APP0
    return head + (b"\x00" * max(size - len(head), 0))


def _files_con_imagen() -> dict:
    return {"archivo": ("comprobante.jpg", _imagen_jpg_bytes(), "image/jpeg")}
```

- [ ] **Step 3: Migrar `test_presentar_comprobante_sin_token_devuelve_401`**

Reemplazar:

```python
def test_presentar_comprobante_sin_token_devuelve_401(client):
    r = client.post("/expensas/100/comprobantes", json=_PAYLOAD_OK)
    assert r.status_code == 401
```

por:

```python
def test_presentar_comprobante_sin_token_devuelve_401(client):
    r = client.post("/expensas/100/comprobantes", data=_DATA_OK)
    assert r.status_code == 401
```

- [ ] **Step 4: Migrar `test_presentar_comprobante_como_departamento_dueno_201`**

Reemplazar:

```python
def test_presentar_comprobante_como_departamento_dueno_201(client, headers_depto_a):
    r = client.post(
        "/expensas/100/comprobantes",
        json=_PAYLOAD_OK,
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["expensa_id"] == 100
    assert body["monto"] == 85000.00
    assert body["fecha_pago"] == "2026-05-28"
    assert body["archivo_url"] == _PAYLOAD_OK["archivo_url"]
    # Estado inicial siempre pendiente_verificacion, independiente del cuerpo.
    assert body["estado"] == "pendiente_verificacion"
```

por:

```python
def test_presentar_comprobante_como_departamento_dueno_201(client, headers_depto_a):
    r = client.post(
        "/expensas/100/comprobantes",
        data=_DATA_OK,
        files=_files_con_imagen(),
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["expensa_id"] == 100
    assert body["monto"] == 85000.00
    assert body["fecha_pago"] == "2026-05-28"
    assert body["archivo_path"].startswith("/uploads/comprobantes/")
    assert body["archivo_path"].endswith(".jpg")
    # Estado inicial siempre pendiente_verificacion, independiente del cuerpo.
    assert body["estado"] == "pendiente_verificacion"
```

- [ ] **Step 5: Renombrar y migrar `test_presentar_comprobante_sin_archivo_url_201`**

Reemplazar el test entero por:

```python
def test_presentar_comprobante_sin_archivo_201(client, headers_depto_a):
    r = client.post(
        "/expensas/100/comprobantes",
        data=_DATA_OK,
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    assert r.json()["archivo_path"] is None
```

- [ ] **Step 6: Migrar los tests de error que usaban `json=_PAYLOAD_OK`**

Reemplazar las 4 funciones siguientes (`_depto_ajeno_devuelve_403`, `_como_admin_devuelve_403`, `_como_representante_devuelve_403`, `_expensa_inexistente_devuelve_404`):

```python
def test_presentar_comprobante_depto_ajeno_devuelve_403(client, headers_depto_a):
    # Expensa 101 pertenece al depto B; depto A no puede acceder.
    r = client.post(
        "/expensas/101/comprobantes",
        data=_DATA_OK,
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_presentar_comprobante_como_admin_devuelve_403(client, headers_admin):
    r = client.post(
        "/expensas/100/comprobantes",
        data=_DATA_OK,
        headers=headers_admin,
    )
    assert r.status_code == 403


def test_presentar_comprobante_como_representante_devuelve_403(client, headers_representante):
    r = client.post(
        "/expensas/100/comprobantes",
        data=_DATA_OK,
        headers=headers_representante,
    )
    assert r.status_code == 403


def test_presentar_comprobante_expensa_inexistente_devuelve_404(client, headers_depto_a):
    r = client.post(
        "/expensas/9999/comprobantes",
        data=_DATA_OK,
        headers=headers_depto_a,
    )
    assert r.status_code == 404
```

- [ ] **Step 7: Migrar los tests 400 (`monto_negativo` y `faltan_campos`)**

Reemplazar:

```python
def test_presentar_comprobante_body_invalido_monto_negativo_devuelve_400(client, headers_depto_a):
    r = client.post(
        "/expensas/100/comprobantes",
        json={"fecha_pago": "2026-05-28", "monto": -1},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_presentar_comprobante_body_invalido_faltan_campos_devuelve_400(client, headers_depto_a):
    r = client.post(
        "/expensas/100/comprobantes",
        json={"monto": 1000},
        headers=headers_depto_a,
    )
    assert r.status_code == 400
```

por:

```python
def test_presentar_comprobante_body_invalido_monto_negativo_devuelve_400(client, headers_depto_a):
    r = client.post(
        "/expensas/100/comprobantes",
        data={"fecha_pago": "2026-05-28", "monto": "-1"},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_presentar_comprobante_body_invalido_faltan_campos_devuelve_400(client, headers_depto_a):
    r = client.post(
        "/expensas/100/comprobantes",
        data={"monto": "1000"},
        headers=headers_depto_a,
    )
    assert r.status_code == 400
```

- [ ] **Step 8: Migrar `test_presentar_comprobante_devuelve_expensa_resumen`**

Reemplazar el test entero por:

```python
def test_presentar_comprobante_devuelve_expensa_resumen(client, headers_depto_a):
    r = client.post(
        "/expensas/100/comprobantes",
        data={"fecha_pago": "2026-06-05", "monto": "85000.00"},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    body = r.json()
    assert "expensa" in body
    assert body["expensa"] is not None
    assert body["expensa"]["departamento_id"] == 1
    assert body["expensa"]["periodo"] == "2026-05"
```

- [ ] **Step 9: Migrar los dos tests de fecha (`fecha_futura` y `fecha_hoy`)**

Reemplazar:

```python
def test_presentar_comprobante_fecha_futura_devuelve_400(client, headers_depto_a):
    futura = (date.today() + timedelta(days=1)).isoformat()
    r = client.post(
        "/expensas/100/comprobantes",
        json={"fecha_pago": futura, "monto": 85000.00},
        headers=headers_depto_a,
    )
    assert r.status_code == 400
    assert "futura" in r.json()["detail"].lower()


def test_presentar_comprobante_fecha_hoy_201(client, headers_depto_a):
    hoy = date.today().isoformat()
    r = client.post(
        "/expensas/100/comprobantes",
        json={"fecha_pago": hoy, "monto": 85000.00},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    assert r.json()["fecha_pago"] == hoy
```

por:

```python
def test_presentar_comprobante_fecha_futura_devuelve_400(client, headers_depto_a):
    futura = (date.today() + timedelta(days=1)).isoformat()
    r = client.post(
        "/expensas/100/comprobantes",
        data={"fecha_pago": futura, "monto": "85000.00"},
        headers=headers_depto_a,
    )
    assert r.status_code == 400
    assert "futura" in r.json()["detail"].lower()


def test_presentar_comprobante_fecha_hoy_201(client, headers_depto_a):
    hoy = date.today().isoformat()
    r = client.post(
        "/expensas/100/comprobantes",
        data={"fecha_pago": hoy, "monto": "85000.00"},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    assert r.json()["fecha_pago"] == hoy
```

- [ ] **Step 10: Correr la sección migrada y constatar que falla**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comprobantes.py -q 2>&1 | tail -15`
Expected: muchos fallos (el router todavía espera JSON `ComprobanteCrear`). Esto es esperado — los arregla Task 8.

- [ ] **Step 11: NO commitear todavía**

Se commitea junto con Task 8.

---

## Fase F — Router + tests TDD

### Task 8: Reescribir el handler POST a multipart

**Files:**
- Modify: `backend/routers/expensas.py`

- [ ] **Step 1: Sumar imports**

En `backend/routers/expensas.py`, al tope (después de los imports existentes), modificar la línea:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
```

por:

```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
```

Y sumar:

```python
from ..storage import guardar_imagen_comprobante
```

junto a los otros imports relativos.

- [ ] **Step 2: Reescribir el handler `presentar_comprobante`**

Ubicar la función `presentar_comprobante` (líneas ~153-186). Reemplazar el bloque entero por:

```python
@router.post(
    "/{expensa_id}/comprobantes",
    response_model=ComprobanteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Presentar comprobante de pago de una expensa",
)
def presentar_comprobante(
    expensa_id: int,
    fecha_pago: date = Form(...),
    monto: float = Form(..., gt=0),
    archivo: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.departamento)),
) -> Comprobante:
    expensa = db.get(Expensa, expensa_id)
    if expensa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La expensa solicitada no existe.",
        )

    if expensa.departamento_id != user.departamento_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a este recurso.",
        )

    if fecha_pago > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de pago no puede ser futura.",
        )

    archivo_path = None
    if archivo is not None and archivo.filename:
        archivo_path = guardar_imagen_comprobante(archivo)

    comprobante = Comprobante(
        expensa_id=expensa.id,
        fecha_pago=fecha_pago,
        monto=monto,
        archivo_path=archivo_path,
        estado=EstadoComprobante.pendiente_verificacion,
    )
    db.add(comprobante)
    db.commit()
    db.refresh(comprobante)
    return comprobante
```

- [ ] **Step 3: Correr los tests migrados**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comprobantes.py -q 2>&1 | tail -5`
Expected: todos pasan (incluidos los nuevos del bug de fecha).

- [ ] **Step 4: Correr suite completa para descartar regresiones**

Run: `./.venv/Scripts/python.exe -m pytest -q 2>&1 | tail -5`
Expected: 238 passed.

- [ ] **Step 5: Commit (incluye Tasks 4, 5, 6, 7, 8 juntas — son una refactor atómica)**

```bash
git add backend/models.py backend/schemas.py backend/storage.py backend/routers/expensas.py tests/conftest.py tests/test_comprobantes.py
git commit -m "feat(comprobantes): POST acepta multipart con imagen, archivo_url → archivo_path"
```

---

### Task 9 (TDD): Test imagen persiste en disco

**Files:**
- Modify: `tests/test_comprobantes.py`

- [ ] **Step 1: Sumar el test al final del archivo**

```python
def test_presentar_comprobante_persiste_imagen_en_disco(client, headers_depto_a, tmp_path):
    from backend.config import get_settings

    r = client.post(
        "/expensas/100/comprobantes",
        data=_DATA_OK,
        files=_files_con_imagen(),
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    archivo_url = r.json()["archivo_path"]
    # `archivo_url` es del estilo `/uploads/comprobantes/<uuid>.jpg`
    rel = archivo_url.removeprefix("/uploads/")
    destino = pathlib.Path(get_settings().UPLOAD_DIR) / rel
    assert destino.exists()
    assert destino.read_bytes()[:4] == b"\xff\xd8\xff\xe0"
```

Y sumar al tope del archivo (si no está ya):

```python
import pathlib
```

- [ ] **Step 2: Correr el test**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comprobantes.py::test_presentar_comprobante_persiste_imagen_en_disco -v 2>&1 | tail -10`
Expected: PASS (el router ya lo soporta — este test "documenta" la persistencia).

- [ ] **Step 3: Commit**

```bash
git add tests/test_comprobantes.py
git commit -m "test(comprobantes): imagen subida persiste en disco bajo UPLOAD_DIR"
```

---

### Task 10 (TDD): Validación de content-type no-imagen

**Files:**
- Modify: `tests/test_comprobantes.py`

- [ ] **Step 1: Escribir el test (falla)**

Agregar al final del archivo:

```python
def test_presentar_comprobante_archivo_no_imagen_devuelve_400(client, headers_depto_a):
    files = {"archivo": ("comprobante.txt", b"hola mundo", "text/plain")}
    r = client.post(
        "/expensas/100/comprobantes",
        data=_DATA_OK,
        files=files,
        headers=headers_depto_a,
    )
    assert r.status_code == 400
    assert "imagen" in r.json()["detail"].lower()
```

- [ ] **Step 2: Correr el test**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comprobantes.py::test_presentar_comprobante_archivo_no_imagen_devuelve_400 -v 2>&1 | tail -10`
Expected: PASS — la validación ya está implementada en `storage.guardar_imagen_comprobante`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_comprobantes.py
git commit -m "test(comprobantes): rechazar archivo no-imagen con 400"
```

---

### Task 11 (TDD): Validación de tamaño > 5 MB

**Files:**
- Modify: `tests/test_comprobantes.py`

- [ ] **Step 1: Escribir el test**

Agregar al final del archivo:

```python
def test_presentar_comprobante_archivo_demasiado_grande_devuelve_413(client, headers_depto_a):
    # 5 MB + 1 byte = excede el cap
    grande = _imagen_jpg_bytes(size=5 * 1024 * 1024 + 1)
    files = {"archivo": ("grande.jpg", grande, "image/jpeg")}
    r = client.post(
        "/expensas/100/comprobantes",
        data=_DATA_OK,
        files=files,
        headers=headers_depto_a,
    )
    assert r.status_code == 413
    assert "5 MB" in r.json()["detail"]
```

- [ ] **Step 2: Correr el test**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comprobantes.py::test_presentar_comprobante_archivo_demasiado_grande_devuelve_413 -v 2>&1 | tail -10`
Expected: PASS (storage ya implementa el cap).

- [ ] **Step 3: Correr suite completa**

Run: `./.venv/Scripts/python.exe -m pytest -q 2>&1 | tail -5`
Expected: 241 passed (238 + 3 nuevos).

- [ ] **Step 4: Commit**

```bash
git add tests/test_comprobantes.py
git commit -m "test(comprobantes): rechazar archivo > 5MB con 413"
```

---

## Fase G — Frontend

### Task 12: `apiFetch` soporta `FormData`

**Files:**
- Modify: `frontend/src/api/client.js:14-31`

- [ ] **Step 1: Reescribir el bloque que arma headers + body**

En `frontend/src/api/client.js`, reemplazar las líneas 14-31 (la función `apiFetch` desde el `export async` hasta el `});` del fetch). Reemplazar:

```javascript
export async function apiFetch(path, { token, body, method = "GET", headers = {}, ...rest } = {}) {
  const tokenToUse = token !== undefined ? token : _authToken;
  const finalHeaders = { ...headers };

  if (body !== undefined && !finalHeaders["Content-Type"]) {
    finalHeaders["Content-Type"] = "application/json";
  }

  if (tokenToUse) {
    finalHeaders["Authorization"] = `Bearer ${tokenToUse}`;
  }

  const res = await fetch(API_BASE + path, {
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...rest,
  });
```

por:

```javascript
export async function apiFetch(path, { token, body, method = "GET", headers = {}, ...rest } = {}) {
  const tokenToUse = token !== undefined ? token : _authToken;
  const finalHeaders = { ...headers };
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

  if (body !== undefined && !isFormData && !finalHeaders["Content-Type"]) {
    finalHeaders["Content-Type"] = "application/json";
  }

  if (tokenToUse) {
    finalHeaders["Authorization"] = `Bearer ${tokenToUse}`;
  }

  const res = await fetch(API_BASE + path, {
    method,
    headers: finalHeaders,
    body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
    ...rest,
  });
```

- [ ] **Step 2: NO commitear todavía**

Se commitea con Task 13.

---

### Task 13: `presentarComprobante` arma `FormData`

**Files:**
- Modify: `frontend/src/api/expensas.js:23-28`

- [ ] **Step 1: Reescribir la función**

En `frontend/src/api/expensas.js`, reemplazar:

```javascript
export function presentarComprobante(expensa_id, payload) {
  return apiFetch(`/expensas/${expensa_id}/comprobantes`, {
    method: "POST",
    body: payload,
  });
}
```

por:

```javascript
export function presentarComprobante(expensa_id, { fecha_pago, monto, archivo }) {
  const fd = new FormData();
  fd.append("fecha_pago", fecha_pago);
  fd.append("monto", String(monto));
  if (archivo) fd.append("archivo", archivo);
  return apiFetch(`/expensas/${expensa_id}/comprobantes`, {
    method: "POST",
    body: fd,
  });
}
```

- [ ] **Step 2: Commit (apiFetch + api/expensas juntos)**

```bash
git add frontend/src/api/client.js frontend/src/api/expensas.js
git commit -m "feat(frontend/api): apiFetch soporta FormData; presentarComprobante manda imagen"
```

---

### Task 14: Modal "Presentar comprobante" con file input + preview

**Files:**
- Modify: `frontend/src/screens/Expensas.jsx:403-500`

- [ ] **Step 1: Reescribir `FormularioPresentarComprobante`**

En `frontend/src/screens/Expensas.jsx`, ubicar `function FormularioPresentarComprobante` (línea ~403). Reemplazar el componente entero (desde `function FormularioPresentarComprobante` hasta el cierre `}` antes del próximo `function`) por:

```jsx
function FormularioPresentarComprobante({ expensa, onPresentado, onCancelar }) {
  const hoy = new Date().toISOString().slice(0, 10);
  const [fechaPago, setFechaPago] = useState("");
  const [monto, setMonto] = useState(String(expensa.monto));
  const [archivo, setArchivo] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!archivo) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(archivo);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setEnviando(true);

    const r = await presentarComprobante(expensa.id, {
      fecha_pago: fechaPago,
      monto: Number(monto),
      archivo,
    });
    setEnviando(false);

    if (r.status === 201) {
      onPresentado(r.data);
      return;
    }
    if (r.status === 400) {
      setError(r.data?.detail || "Revisá los campos del formulario.");
      return;
    }
    if (r.status === 403) {
      setError("No tenés permisos para presentar este comprobante.");
      return;
    }
    if (r.status === 404) {
      setError("La expensa solicitada no existe.");
      return;
    }
    if (r.status === 413) {
      setError(r.data?.detail || "El archivo es demasiado grande.");
      return;
    }
    if (r.status !== 401) {
      setError("Ocurrió un error inesperado. Intentá de nuevo.");
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <p className="meta">
        Expensa: {expensa.periodo} — ${expensa.monto.toLocaleString("es-AR")}
      </p>
      <label>
        Fecha de pago
        <input
          type="date"
          value={fechaPago}
          onChange={(e) => setFechaPago(e.target.value)}
          max={hoy}
          required
          autoFocus
        />
      </label>
      <label>
        Monto pagado
        <input
          type="number"
          value={monto}
          onChange={(e) => setMonto(e.target.value)}
          min="1"
          step="0.01"
          required
        />
      </label>
      <label>
        Foto del comprobante (opcional)
        <input
          type="file"
          accept="image/*"
          onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
        />
      </label>

      {previewUrl && (
        <img src={previewUrl} alt="Vista previa del comprobante" className="comprobante-img" />
      )}

      {error && <p role="alert" className="error-banner">{error}</p>}

      <div className="modal-acciones">
        <button type="button" className="boton-secundario" onClick={onCancelar} disabled={enviando}>
          Cancelar
        </button>
        <button type="submit" disabled={enviando}>
          {enviando ? "Enviando…" : "Presentar"}
        </button>
      </div>
    </form>
  );
}
```

- [ ] **Step 2: Verificar que `useEffect` está importado al tope**

Revisar el `import { useEffect, useState } from "react";` en la línea 1. Ya está — no hace falta cambiarlo.

- [ ] **Step 3: NO commitear todavía**

Se commitea con Tasks 15-17.

---

### Task 15: Render `<img>` en los modales Ver/Confirmar de `Expensas.jsx`

**Files:**
- Modify: `frontend/src/screens/Expensas.jsx` (modales Confirmar y Ver)

- [ ] **Step 1: Modal Confirmar — reemplazar el link por img**

En `frontend/src/screens/Expensas.jsx` ubicar el bloque del modal Confirmar (buscar `modalConfirmar.comprobante.archivo_url`, ~líneas 243-247). Reemplazar:

```jsx
{modalConfirmar.comprobante.archivo_url && (
  <p>
    <a href={modalConfirmar.comprobante.archivo_url} target="_blank" rel="noopener noreferrer">
      Ver archivo
    </a>
  </p>
)}
```

por:

```jsx
{modalConfirmar.comprobante.archivo_path && (
  <a
    href={modalConfirmar.comprobante.archivo_path}
    target="_blank"
    rel="noopener noreferrer"
  >
    <img
      src={modalConfirmar.comprobante.archivo_path}
      alt="Comprobante"
      className="comprobante-img"
    />
  </a>
)}
```

- [ ] **Step 2: Modal Ver — reemplazar el link por img**

En `frontend/src/screens/Expensas.jsx`, líneas 295-303. Reemplazar:

```jsx
{modalVer.archivo_url ? (
  <p>
    <a href={modalVer.archivo_url} target="_blank" rel="noopener noreferrer">
      Ver archivo adjunto
    </a>
  </p>
) : (
  <p className="meta">Sin archivo adjunto.</p>
)}
```

por:

```jsx
{modalVer.archivo_path ? (
  <a href={modalVer.archivo_path} target="_blank" rel="noopener noreferrer">
    <img src={modalVer.archivo_path} alt="Comprobante" className="comprobante-img" />
  </a>
) : (
  <p className="meta">Sin archivo adjunto.</p>
)}
```

- [ ] **Step 3: NO commitear todavía**

Se commitea con Tasks 16-17.

---

### Task 16: Render `<img>` en `Comprobantes.jsx`

**Files:**
- Modify: `frontend/src/screens/Comprobantes.jsx`

- [ ] **Step 1: Reemplazar el link de archivo por img**

En `frontend/src/screens/Comprobantes.jsx`, ubicar el bloque:

```jsx
{c.archivo_url && (
  <p>
    <a href={c.archivo_url} target="_blank" rel="noopener noreferrer">
      Ver archivo
    </a>
  </p>
)}
```

Reemplazarlo por:

```jsx
{c.archivo_path && (
  <a href={c.archivo_path} target="_blank" rel="noopener noreferrer">
    <img src={c.archivo_path} alt="Comprobante" className="comprobante-img" />
  </a>
)}
```

- [ ] **Step 2: NO commitear todavía**

Se commitea con Task 17.

---

### Task 17: CSS para `.comprobante-img`

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Sumar la regla al final del archivo, antes del primer `@media`**

Ubicar la sección de "Listas de expensas y comprobantes" (o cualquier punto antes del primer `@media (min-width: 600px)`). Agregar:

```css
/* ---------- Imagen de comprobante ---------- */

.comprobante-img {
  max-width: 100%;
  max-height: 240px;
  margin: 0.5rem 0;
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
  object-fit: contain;
  cursor: zoom-in;
}
```

- [ ] **Step 2: Build del frontend**

Run (desde `frontend/`): `npx vite build 2>&1 | tail -5`
Expected: build pasa sin errores.

- [ ] **Step 3: Commit (frontend completo)**

```bash
git add frontend/src/screens/Expensas.jsx frontend/src/screens/Comprobantes.jsx frontend/src/index.css
git commit -m "feat(frontend/comprobantes): subir foto con preview y renderizar imagen en lugar de link"
```

---

## Fase H — Verificación

### Task 18: Smoke test end-to-end + reset DB local

- [ ] **Step 1: Borrar la DB local para que el schema nuevo se cree limpio**

Como el rename de columna no incluye migración ALTER, hay que recrear la DB local. Esto borra los 1-2 comprobantes de prueba (acuerdo del usuario).

Run (en Windows PowerShell): `Remove-Item .\consorcio.db -ErrorAction SilentlyContinue`
O en Bash: `rm -f consorcio.db`

- [ ] **Step 2: Correr toda la suite backend**

Run: `./.venv/Scripts/python.exe -m pytest -q 2>&1 | tail -5`
Expected: 241 passed.

- [ ] **Step 3: Validar OpenAPI**

Run: `./.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml', encoding='utf-8')); print('OK')"`
Expected: imprime `OK`.

- [ ] **Step 4: Smoke visual (manual del usuario)**

Levantar backend (`uvicorn backend.main:app --reload`) y frontend (desde `frontend/`: `npm run dev`).

1. Login como Depto A (`a@test.local` / `test-pass-1234`).
2. Ir a `/expensas`, en una expensa pendiente clic "Presentar comprobante".
3. Tomar/elegir foto, ver preview, completar fecha + monto, clic Presentar → la tarjeta refresca a "Comprobante pendiente de verificación".
4. Ir a `/comprobantes` (vista del depto) → ver la imagen.
5. Logout, login como Admin.
6. Ir a `/comprobantes`, ver imagen del depto, clic Aprobar → la tarjeta cambia a "Aprobado".
7. Probar caso de archivo > 5 MB (cualquier imagen grande) → modal muestra "El archivo supera el máximo permitido (5 MB)."
8. Probar archivo no-imagen (si el OS permite saltearse `accept`) → modal muestra "El archivo debe ser una imagen JPG, PNG o WebP."

- [ ] **Step 5: Listo**

Si los chequeos visuales pasan, el módulo está completo. La integración a `master` está fuera del scope del plan (la decide el usuario).

# Comprobante con foto — diseño

Fecha: 2026-06-14
Estado: aprobado por el usuario, pendiente de plan de implementación.

## Objetivo

Reemplazar el campo "link al comprobante" del flujo de presentar comprobante de pago por una **subida de imagen** desde el dispositivo del depto (cámara o galería). El backend pasa a almacenar el archivo en disco y a servirlo como recurso estático; el frontend muestra la imagen embebida en lugar de un link externo.

## Reglas del proyecto aplicables

- `business-rules.md`: Departamentos presentan comprobantes sobre expensas de su propia unidad; Administración los verifica.
- `backend.md`: routers en `backend/routers/`, modelos en `backend/models.py`, schemas en `backend/schemas.py`, tests por router cubriendo 401/403/404/409 (más 400/413 acá).
- `openapi-first.md`: el cambio de `application/json` a `multipart/form-data` se documenta primero en `openapi.yaml`.
- `frontend.md`: HTML semántico, paleta vía variables CSS, estado en hooks, mobile-first, targets táctiles ≥44px.
- `security.md`: identidad y rol salen del JWT, nunca del body.

## Decisiones de diseño

| Decisión | Elegida | Alternativas descartadas | Razón |
|---|---|---|---|
| Convivencia foto / URL | Reemplazar el link | Coexistir foto + URL; mantener URLs legacy | Una sola forma de presentar el comprobante, menos UI y menos casos a probar. |
| Storage | Filesystem local (`backend/uploads/comprobantes/`) servido con `StaticFiles` | BLOB en DB; base64 en DB | Estándar, fácil de inspeccionar, sin inflar SQLite. |
| Tipos aceptados | Imágenes (JPG/PNG/WebP), cámara o galería | Solo cámara forzada; imágenes + PDF | Más flexible; PDF agrega complejidad de preview sin pedido explícito. |
| Migración de DB | Renombrar `archivo_url` → `archivo_path` y limpiar datos | Sumar columna nueva manteniendo `archivo_url` legacy; reutilizar el nombre `archivo_url` con semántica nueva | Solo hay 1-2 comprobantes de prueba; arrancar limpio evita estado mixto. |
| Tamaño máximo | 5 MB; 413 si excede | Auto-resize en frontend con canvas; 10 MB sin restricción | Cubre fotos típicas de mobile (2-4 MB), sin dependencias nuevas. |
| Endpoint | Modificar el `POST` existente a multipart | Endpoint separado de upload en dos pasos | Un solo round-trip, atómico (sin estado intermedio "comprobante creado sin archivo"). |
| Autenticación del archivo servido | URL no enumerable (UUID) + sin auth en el static | Endpoint custom `GET /comprobantes/{id}/archivo` con auth + FileResponse; URLs firmadas | Para un proyecto educativo el modelo "URL solo accesible a quien la conoce, conocida solo vía API autenticada" es suficiente; el endpoint con auth obligaría a hacer `fetch + blob` en el frontend. |

## Cambios en modelo y schemas

`backend/models.py`:

- `Comprobante.archivo_url: Mapped[str | None]` → renombrar a `Comprobante.archivo_path: Mapped[str | None]`, tipo `String(255)`.
- Guarda el path **relativo al `UPLOAD_DIR`**, p. ej. `comprobantes/abc123.jpg`. La URL pública (`/uploads/comprobantes/abc123.jpg`) la arma la capa de schema al serializar.

`backend/schemas.py`:

- `ComprobanteCrear` deja de existir como tal (los campos pasan a leerse del form-data). Se reemplaza por parámetros directos en la firma del endpoint.
- `ComprobanteOut.archivo_url: str | None` → `archivo_path: str | None`. El valor que viaja al frontend es la URL relativa completa (`/uploads/comprobantes/abc123.jpg`), no solo el nombre.

`ComprobanteResumen` no cambia (no incluye `archivo_url` actualmente, ver `schemas.py`).

## Endpoint: `POST /expensas/{expensa_id}/comprobantes`

Pasa de:

```yaml
requestBody:
  content:
    application/json:
      schema: { $ref: '#/components/schemas/ComprobanteCrear' }
```

a:

```yaml
requestBody:
  content:
    multipart/form-data:
      schema:
        type: object
        required: [fecha_pago, monto]
        properties:
          fecha_pago: { type: string, format: date }
          monto: { type: number }
          archivo:
            type: string
            format: binary
            description: Imagen del comprobante (JPG/PNG/WebP, máx 5 MB).
```

Firma del handler:

```python
def presentar_comprobante(
    expensa_id: int,
    fecha_pago: date = Form(...),
    monto: float = Form(..., gt=0),
    archivo: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.departamento)),
) -> Comprobante: ...
```

Orden de validaciones (cortando en el primer error):

1. Expensa existe (404).
2. Expensa pertenece al departamento del user (403).
3. `fecha_pago <= date.today()` (400, ya implementado).
4. Si `archivo` está presente: `content_type` empieza con `image/` (400 con detail). Lectura streaming con cap de 5 MB → si supera, 413 con detail.
5. Guardar archivo: `uuid4().hex + ext` (ext derivada del content_type: `image/jpeg` → `.jpg`, etc.). Path final relativo (`comprobantes/abc123.jpg`).
6. Crear `Comprobante` con `archivo_path` poblado o `NULL`.

## Storage y serving

- Carpeta: `backend/uploads/comprobantes/`. Se crea en boot si no existe.
- Mounting en `backend/main.py`:
  ```python
  app.mount("/uploads", StaticFiles(directory="backend/uploads"), name="uploads")
  ```
- Las imágenes son accesibles vía `GET /uploads/comprobantes/{nombre}` sin token. Seguridad: el nombre es un UUID v4 (122 bits de entropía), no enumerable.
- `ComprobanteOut.archivo_path` devuelve la URL relativa completa para que el frontend la use directo en `<img src>`.

## Frontend

### Modal "Presentar comprobante" (`frontend/src/screens/Expensas.jsx`, componente `FormularioPresentarComprobante`)

- Reemplazar `<input type="url">` por `<input type="file" accept="image/*">`. Sin `capture="environment"` para no forzar cámara; el OS de mobile ofrece "tomar foto" o "elegir de galería" en el picker nativo.
- Estado `archivo: File | null` en vez de `archivoUrl: string`. Preview con `URL.createObjectURL(archivo)`: `<img src={previewUrl}>` con `max-width: 100%; max-height: 240px`, dentro del modal. Liberar el blob URL con `URL.revokeObjectURL` cuando cambia o se desmonta.
- `presentarComprobante(expensaId, datos)` cambia de `JSON.stringify` a `FormData`:
  ```js
  const fd = new FormData();
  fd.append("fecha_pago", fechaPago);
  fd.append("monto", String(monto));
  if (archivo) fd.append("archivo", archivo);
  ```
- `apiFetch` (`frontend/src/api/client.js`) hoy asume JSON: detectar `body instanceof FormData` y omitir el `Content-Type` (lo pone el browser con el boundary).
- Manejo de respuestas: sumar caso 413 → `"El archivo supera el máximo permitido (5 MB)."`. 400 sigue mostrando el `detail` del backend.

### Render del comprobante (en 3 lugares)

1. Modal "Ver comprobante" (Expensas, depto y admin): `<a href={archivo_path} target="_blank"><img src={archivo_path} alt="Comprobante" /></a>`.
2. Modal "Confirmar comprobante" (Expensas, admin): igual.
3. Pantalla `/comprobantes` (admin y depto): mismo patrón en la tarjeta, en lugar del `<a>Ver archivo</a>` actual.

CSS nueva regla `.comprobante-img` en `frontend/src/index.css`: `max-width: 100%; max-height: 240px; border-radius: var(--radius); border: 1px solid var(--color-border)`.

## Tests

`tests/test_comprobantes.py`:

- Migrar los tests existentes del POST que mandan JSON a multipart (helper `_multipart_payload(fecha, monto, archivo=None)`).
- Sumar:
  - `test_presentar_comprobante_con_imagen_201`: jpg de pocos bytes → 201, `archivo_path` no-null, archivo existe en disco.
  - `test_presentar_comprobante_archivo_demasiado_grande_devuelve_413`: archivo > 5 MB → 413.
  - `test_presentar_comprobante_content_type_no_imagen_devuelve_400`: subir `text/plain` o similar → 400.
  - Confirmar que los tests previos (sin archivo) siguen verdes con el nuevo contrato.
- Fixture para apuntar `UPLOAD_DIR` a `tmp_path` durante los tests (evitar ensuciar `backend/uploads/` real). Implementación: el path se lee de `config.Settings` para poder monkeypatch en tests.

OpenAPI: validar YAML al final (`python -c "import yaml; yaml.safe_load(open('openapi.yaml', encoding='utf-8'))"`).

## Cambios fuera del core (chicos)

- `.gitignore`: agregar `backend/uploads/comprobantes/*` (con excepción para `.gitkeep`).
- `backend/uploads/comprobantes/.gitkeep` para que la carpeta exista en clones nuevos.
- Borrar `consorcio.db` local antes de correr la app por primera vez con el schema nuevo (o el dev re-seeded). El plan de implementación documenta el paso.
- `backend/config.py`: agregar `UPLOAD_DIR` (default `backend/uploads`) y `MAX_UPLOAD_SIZE_BYTES` (default `5 * 1024 * 1024`).

## Fuera de scope

- Compresión / resize server-side (Pillow).
- Generación de thumbnails.
- Auth en el static serving (URLs firmadas, endpoint con FileResponse + auth).
- Soporte de PDF u otros tipos.
- Limpieza de archivos huérfanos (si un comprobante se borra, su archivo queda en disco).
- Migración de URLs existentes: se borran (acuerdo explícito del usuario, solo había 1-2 de prueba).

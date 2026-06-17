---
paths:
  - "backend/**/*.py"
  - "tests/**/*.py"
---

# Convenciones del backend

- **Endpoints / controladores** viven estrictamente en `backend/routers/`. Un archivo por recurso (ej. `expensas.py`, `gastos.py`, `liquidaciones.py`).
- **Modelos de datos** centralizados en `backend/models.py`. Usar SQLAlchemy 2.0 con `Mapped[...]` y `mapped_column`.
- **Integridad relacional** mediante foreign keys en SQLite. Las tablas del modelo central incluyen: departamentos, usuarios, peticiones, trabajos, presupuestos, comunicados, expensas, comprobantes, amenities, reservas, clases_prorrateo, coeficientes_departamento, proveedores, configuracion_consorcio, gastos, gastos_habituales, empleados, haberes, conceptos_liquidacion, liquidaciones_empleado, liquidaciones_haber, liquidaciones_detalle.
- **Schemas Pydantic** en `backend/schemas.py`, separados por entrada (`*Crear`, `*Actualizar`) y salida (`*Out`).
- **Dependencias FastAPI:** `get_db` para sesión SQLAlchemy y `get_current_user` (o el wrapper `require_roles(Rol.administracion, ...)` cuando hay gating por rol) para autenticación. Patrón: `db: Session = Depends(get_db)` y `_user: CurrentUser = Depends(require_roles(...))`.
- **Tests:** un archivo por router en `tests/test_<recurso>.py`. Cubrir happy path y errores 400 / 401 / 403 / 404 / 409. El proyecto convierte `RequestValidationError` de Pydantic a HTTP 400 (ver `backend/main.py`), así que validaciones de schema se asertan con 400, no 422.
- **Comando de desarrollo:** `uvicorn backend.main:app --reload`.
- **Tests:** `pytest -v` (o `./.venv/Scripts/python.exe -m pytest -v` en Windows con venv).

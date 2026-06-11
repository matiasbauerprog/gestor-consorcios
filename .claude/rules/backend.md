---
paths:
  - "backend/**/*.py"
  - "tests/**/*.py"
---

# Convenciones del backend

- **Endpoints / controladores** viven estrictamente en `backend/routers/`. Un archivo por recurso (ej. `expensas.py`, `peticiones.py`, `comunicados.py`).
- **Modelos de datos** centralizados en `backend/models.py`. Usar SQLAlchemy 2.0 con `Mapped[...]` y `mapped_column`.
- **Integridad relacional** mediante foreign keys en SQLite — entre departamentos, expensas, comprobantes, peticiones, trabajos, presupuestos, reservas.
- **Schemas Pydantic** en `backend/schemas.py`, separados por entrada (`*Crear`, `*Actualizar`) y salida.
- **Dependencias FastAPI:** `get_db` para sesión SQLAlchemy y `get_current_user` para autenticación. La función debe declarar `db: Session = Depends(get_db)` y `user: CurrentUser = Depends(get_current_user)`.
- **Tests:** un archivo por router en `tests/test_<recurso>.py`. Cubrir happy path y errores 401 / 403 / 404 / 409.
- **Comando de desarrollo:** `uvicorn backend.main:app --reload`.
- **Tests:** `pytest -v` (o `./.venv/Scripts/python.exe -m pytest -v` en Windows con venv).

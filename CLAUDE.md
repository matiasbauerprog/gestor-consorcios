# Sistema Integral de Gestión de Consorcios

## Propósito
Sistema para gestionar consorcios. Consta de un Frontend (interfaz), un Backend (servidor) y persistencia de datos (base de datos relacional).

## Mapa de carpetas
- `frontend/` — aplicación React + Vite (SPA).
- `backend/` — servidor FastAPI.
- `backend/routers/` — controladores / endpoints.
- `backend/models.py` — esquemas de la base de datos.
- `.claude/` — configuración del agente (rules, skills, settings).

## Stack tecnológico
- **Backend:** Python + FastAPI + SQLite.
- **Frontend:** React + Vite. Consume la API vía `fetch` con `Authorization: Bearer <token>`.
- **Ejecutar backend:** `uvicorn backend.main:app --reload`
- **Ejecutar frontend (dev):** `npm run dev` desde `frontend/`
- **Tests backend:** `pytest -v`

## Reglas modulares
Las convenciones específicas viven en `.claude/rules/`:
- `business-rules.md` — permisos por rol y reglas de negocio por módulo (siempre activa).
- `openapi-first.md` — contrato OpenAPI-first (activa al tocar `openapi.yaml` o routers).
- `security.md` — manejo de auth, tokens y datos sensibles (activa en código de seguridad).
- `backend.md` — convenciones del backend (activa en `backend/` y `tests/`).
- `frontend.md` — convenciones del frontend (activa en `frontend/`).

---
paths:
  - "backend/auth.py"
  - "backend/security.py"
  - "backend/config.py"
  - "backend/seed.py"
  - "backend/routers/**/*.py"
---

# Seguridad

- **Nunca** dejar tokens, credenciales ni contraseñas hardcodeadas en el código fuente. Usar variables de entorno (`backend/config.py` con `pydantic-settings`).
- **Identidad y rol vienen del JWT, no del body** — ignorar campos como `usuario_id`, `departamento_id` o `autor_id` que aparezcan en payloads de entrada.
- Devolver 401 ante token ausente / inválido / revocado; 403 ante rol sin permisos para el recurso.
- Comparar contraseñas siempre con `verify_password` (passlib) — nunca con `==`.
- En login, evitar enumeración de usuarios: respuesta genérica `"Credenciales inválidas."` y tiempo de respuesta constante (ver `_DUMMY_HASH` en `backend/routers/auth.py`).
- `SECRET_KEY` debe venir del entorno; el validator de `Settings` falla si está vacía.

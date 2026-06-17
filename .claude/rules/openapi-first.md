---
paths:
  - "openapi.yaml"
  - "backend/routers/**/*.py"
---

# Contrato OpenAPI-first

Cualquier nuevo endpoint **debe documentarse primero en `openapi.yaml`** antes de implementarse en el código.

- Los path parameters usan el nombre completo del recurso: `{expensa_id}`, `{peticion_id}`, `{trabajo_id}`, `{amenity_id}`, `{reserva_id}`, `{comprobante_id}`, `{departamento_id}`, `{usuario_id}`, `{clase_prorrateo_id}`, `{proveedor_id}`, `{gasto_id}`, `{gasto_habitual_id}`, `{empleado_id}`, `{haber_id}`, `{concepto_id}`, `{liquidacion_id}` — no `{id}` genérico.
- Cada operación debe declarar `response_model` y `status_code` explícitos en el router de FastAPI.
- No duplicar claves de path en `openapi.yaml`: si un mismo path tiene varios verbos, deben estar agrupados bajo una sola entrada (ej. `get:` y `patch:` bajo `/peticiones/{peticion_id}:`).
- Para agregar un endpoint, usar la skill `add-endpoint` (sigue las 6 fases definidas en `.claude/skills/add-endpoint/SKILL.md`).

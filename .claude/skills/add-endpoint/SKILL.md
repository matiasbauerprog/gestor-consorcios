---
name: add-endpoint
description: Use when the user asks to add a new REST endpoint to the backend.
---

# Procedimiento para agregar un nuevo endpoint REST

Sigue estas fases estrictamente en orden:

## Fases
1. **Confirmar contrato:** Confirma con el usuario el verbo HTTP, el path, el schema de entrada y el schema de salida antes de escribir código.
2. **OpenAPI:** Documenta el nuevo contrato en `openapi.yaml` antes de tocar el código (regla OpenAPI-first definida en `CLAUDE.md`).
3. **Modelos:** Agrega o actualiza los schemas necesarios en el archivo de modelos correspondiente.
4. **Router/Controller:** Crea la función del endpoint en el router adecuado asegurando que tenga `response_model` y `status_code` explícitos.
5. **Tests:** Escribe las pruebas automatizadas (happy path y el error esperado) para este nuevo endpoint.
6. **Verificación:** Ejecuta los tests para confirmar que el nuevo endpoint funciona correctamente y no rompe nada más.

## Anti-patrones (Qué NO hacer)
- NO escribas código antes de actualizar `openapi.yaml`.
- NO crees el endpoint sin escribir su test correspondiente.
- NO dejes el endpoint sin `response_model` ni `status_code` explícitos.
- NO hardcodees constantes que deban ir en variables de entorno o en la base de datos.
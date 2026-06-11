# Reglas de negocio y permisos por rol

Roles fijos del sistema: **Administración**, **Departamentos** (Inquilinos/Propietarios) y **Representantes**. El backend debe respetar esta jerarquía y devolver 401/403 si un rol intenta acceder a un recurso no autorizado. El frontend debe ocultar/deshabilitar elementos según el rol del usuario autenticado.

## 1. Auth y Usuarios
- Autenticación vía `POST /auth/login` (público): recibe `{email, password}` y devuelve JWT HS256 + datos del usuario.
- Todo endpoint subsiguiente exige `Authorization: Bearer <token>`.
- **La identidad y el rol se extraen exclusivamente del token** — nunca confiar en `usuario_id`, `departamento_id` o `autor_id` que vengan en el body.

## 2. Expensas
- **Administración:** crea expensas y ve el historial general.
- **Departamentos:** presentan comprobantes de pago y ven solo su propio historial.

## 3. Tareas y Presupuestos
- **Departamentos:** solo crean peticiones y ven su estado.
- **Administración / Representantes:** convierten peticiones en tareas a realizar y aprueban presupuestos de proveedores.

## 4. Comunicación
- **Administración:** crea y gestiona comunicados (`POST /comunicados`).
- **Departamentos:** acceso de solo lectura (`GET /comunicados`).

## 5. Reserva de espacios
- Todos los roles pueden consultar disponibilidad y reservar amenities (SUM, Laundry, etc.).

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

## 6. Gastos del consorcio
- **Administración:** carga gastos puntuales (`POST /gastos`), planes en cuotas (`POST /gastos/plan-cuotas`), plantillas recurrentes (`/gastos-habituales`) y materializa habituales del mes (`POST /gastos/cargar-habituales`). Edita y elimina con CRUD admin-only.
- Cada gasto va a una clase de prorrateo **o** a un departamento particular (excluyentes, validado en schema).
- **Departamentos / Representantes:** sin acceso a gastos (admin-only).

## 7. Configuración del consorcio
- **Administración:** crea/edita clases de prorrateo, proveedores, coeficientes por departamento, datos del consorcio (singleton).
- **Departamentos:** solo lectura de `/configuracion` (necesitan los datos bancarios para pagar). Sin acceso al resto de los catálogos.
- **Representantes:** sin acceso.

## 8. Personal y liquidaciones
- **Administración:** gestiona empleados (CRUD), haberes (catálogo), conceptos de liquidación (descuentos + contribuciones) y carga liquidaciones mensuales por empleado. Cada liquidación calcula bruto desde haberes (snapshot), aplica conceptos vigentes (snapshot), y genera N Gastos del Rubro `sueldos_y_cargas_sociales` con `liquidacion_id` apuntando atrás.
- Editar una liquidación recálcula y regenera los gastos asociados. Eliminar borra los gastos en cascada manual.
- **Departamentos / Representantes:** sin acceso.

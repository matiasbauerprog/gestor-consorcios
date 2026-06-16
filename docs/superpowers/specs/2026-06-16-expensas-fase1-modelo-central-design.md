# Expensas — Fase 1: modelo de datos central — diseño

Fecha: 2026-06-16
Estado: aprobado por el usuario, pendiente de plan de implementación.
Roadmap: [2026-06-16-expensas-completas-roadmap.md](2026-06-16-expensas-completas-roadmap.md)

## Objetivo

Sentar las bases para la réplica fiel del modelo real de liquidación de expensas (Ley 941 CABA). Esta fase introduce los conceptos transversales que todas las fases posteriores (gastos, encargado, cierre, reportes) van a consumir: **rubros**, **clases de prorrateo**, **coeficientes múltiples por departamento**, **proveedores**, y **configuración global del consorcio**.

No introduce gastos, cierre, ni cambia el modelo actual de `Expensa` / `Comprobante`. Esos quedan congelados hasta la Fase 4.

## Reglas del proyecto aplicables

- `business-rules.md`: Administración es quien gestiona configuración, clases, proveedores y coeficientes; Departamento solo puede consultar configuración del consorcio (para mostrar datos bancarios al pagar).
- `backend.md`: routers en `backend/routers/`, modelos en `backend/models.py`, schemas en `backend/schemas.py`, tests por router cubriendo 401/403/404/409/422.
- `openapi-first.md`: todos los endpoints nuevos se documentan primero en `openapi.yaml` siguiendo la skill `add-endpoint`.
- `frontend.md`: HTML semántico, paleta vía variables CSS, estado en hooks, mobile-first, targets táctiles ≥44px.
- `security.md`: identidad y rol vienen del JWT; los endpoints validan rol con `require_roles`.

## Decisiones de diseño

| Decisión | Elegida | Alternativas descartadas | Razón |
|---|---|---|---|
| Rubros | Catálogo fijo en código (Enum) | CRUD de rubros | Los 9 rubros de Ley 941 son estándar; nadie inventa rubros propios. Sumar uno = agregar al enum. |
| Clases de prorrateo | CRUD (admin configura por consorcio) | Catálogo fijo A/B/C/D | Cada reglamento define sus clases; el costo de hacer CRUD es bajo y da flexibilidad real. |
| Coeficientes | Tabla N:M `(departamento, clase, porcentaje)` con `UniqueConstraint` | Coeficiente único en `Departamento` | El primer PDF muestra que cada depto tiene un % distinto por clase. |
| Formato del coeficiente | Porcentaje float 0..100, hasta 4 decimales | Decimal 0..1; entero × 100 | Los PDFs usan porcentaje con 2-4 decimales; el operador lo carga así, sin conversión mental. |
| Validación suma 100% | Solo Fase 4 (al cerrar), no en Fase 1 | Validar en cada guardado | Carga incremental: admin no carga el último depto y la suma queda en 90%; bloquearlo trabaría la carga. |
| Coeficiente faltante para una clase | Significa 0% (no participa) | Forzar fila con 0 explícita | Cocheras u otros deptos especiales no participan de algunas clases (caso del segundo PDF). |
| Proveedores: CUIT | Único, validado con regex `\d{2}-\d{8}-\d{1}` | Validación con dígito verificador | El DV no aporta valor pedagógico y suma código. |
| Proveedores: borrado | Soft-delete (`activo=false`) | Hard delete | El histórico de gastos referencia proveedores; borrar rompe integridad. |
| Configuración del consorcio | Singleton (tabla con `id=1`) | Tabla de pares clave-valor; archivo JSON | Schema fuertemente tipado, validado por Pydantic, sin parsing manual. |
| Acceso de Depto a configuración | Solo `GET /configuracion` | Bloquear total | Depto necesita ver datos bancarios al pagar — son públicos dentro del consorcio. |
| Migración de datos existentes | Borrar todo y empezar limpio | Migrar en lugar; seed automático con valores ficticios | 1-2 deptos de prueba y nada productivo; ya hicimos clean start antes. |
| Alcance de Fase 1 | Backend completo + 4 pantallas admin | Solo backend; backend + frontend mínimo | Para horizonte comercial, Fase 1 debe ser demo-able y mergeable de punta a punta. |
| Migraciones formales (Alembic) | No por ahora; seguimos con `create_all` + seed | Introducir Alembic en Fase 1 | DB sin datos productivos; sumar Alembic cuando la app tenga uso real. |

## Modelo de datos

### `Rubro` (enum estático en `backend/models.py`)

```python
class Rubro(str, enum.Enum):
    sueldos_y_cargas_sociales = "sueldos_y_cargas_sociales"
    servicios_publicos = "servicios_publicos"
    abonos_y_servicios = "abonos_y_servicios"
    mantenimiento_partes_comunes = "mantenimiento_partes_comunes"
    trabajos_reparaciones_unidades = "trabajos_reparaciones_unidades"
    gastos_bancarios = "gastos_bancarios"
    gastos_administracion = "gastos_administracion"
    seguros = "seguros"
    gastos_generales = "gastos_generales"
```

### `ClaseProrrateo`

```python
class ClaseProrrateo(Base):
    __tablename__ = "clases_prorrateo"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500))
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    coeficientes: Mapped[list["CoeficienteDepartamento"]] = relationship(
        back_populates="clase"
    )
```

### `CoeficienteDepartamento` (N:M)

```python
class CoeficienteDepartamento(Base):
    __tablename__ = "coeficientes_departamento"
    __table_args__ = (
        UniqueConstraint(
            "departamento_id", "clase_prorrateo_id", name="uq_coef_depto_clase"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    clase_prorrateo_id: Mapped[int] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="CASCADE"), index=True, nullable=False
    )
    porcentaje: Mapped[float] = mapped_column(Float, nullable=False)  # 0..100, 4 decimales

    departamento: Mapped["Departamento"] = relationship(back_populates="coeficientes")
    clase: Mapped["ClaseProrrateo"] = relationship(back_populates="coeficientes")
```

Y a `Departamento` se le agrega:
```python
coeficientes: Mapped[list["CoeficienteDepartamento"]] = relationship(
    back_populates="departamento", cascade="all, delete-orphan"
)
```

### `Proveedor`

```python
class Proveedor(Base):
    __tablename__ = "proveedores"
    id: Mapped[int] = mapped_column(primary_key=True)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_fantasia: Mapped[str | None] = mapped_column(String(255))
    cuit: Mapped[str] = mapped_column(String(13), unique=True, nullable=False)  # "XX-XXXXXXXX-X"
    direccion: Mapped[str | None] = mapped_column(String(500))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

### `ConfiguracionConsorcio` (singleton)

```python
class ConfiguracionConsorcio(Base):
    __tablename__ = "configuracion_consorcio"
    id: Mapped[int] = mapped_column(primary_key=True)  # siempre 1

    # consorcio
    consorcio_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    consorcio_domicilio: Mapped[str] = mapped_column(String(500), nullable=False)
    consorcio_cuit: Mapped[str] = mapped_column(String(13), nullable=False)
    consorcio_convenio_suterh: Mapped[str | None] = mapped_column(String(50))

    # administración
    admin_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_domicilio: Mapped[str] = mapped_column(String(500), nullable=False)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_telefono: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_cuit: Mapped[str] = mapped_column(String(13), nullable=False)
    admin_rpa: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_situacion_fiscal: Mapped[str] = mapped_column(String(100), nullable=False)

    # banco
    banco_titular: Mapped[str] = mapped_column(String(255), nullable=False)
    banco_nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    banco_sucursal: Mapped[str | None] = mapped_column(String(50))
    banco_numero_cuenta: Mapped[str] = mapped_column(String(50), nullable=False)
    banco_cbu: Mapped[str] = mapped_column(String(22), nullable=False)
    banco_alias: Mapped[str | None] = mapped_column(String(50))
```

Singleton enforcement: en el router, GET y PUT siempre operan sobre `id=1`. El seed inicial crea la fila con placeholders (`"PENDIENTE"` en strings, `"00-00000000-0"` en CUITs, etc.).

## Endpoints

Todos requieren JWT y son **admin-only** salvo aclaración. Documentación primero en `openapi.yaml` por cada uno.

### Clases de prorrateo — `backend/routers/clases_prorrateo.py`

| Método | Path | Rol | Notas |
|---|---|---|---|
| GET | `/clases-prorrateo` | admin | Listar todas (incluye inactivas). Filtro `?activa={bool}` opcional. |
| POST | `/clases-prorrateo` | admin | Crear; 409 si `codigo` duplicado. |
| GET | `/clases-prorrateo/{clase_prorrateo_id}` | admin | Detalle; 404 si no existe. |
| PATCH | `/clases-prorrateo/{clase_prorrateo_id}` | admin | Editar `nombre`, `descripcion`, `activa`. **No** se puede editar `codigo`. |
| DELETE | `/clases-prorrateo/{clase_prorrateo_id}` | admin | Si tiene coeficientes asociados → soft-delete (set `activa=false`). Si no → hard delete. |

### Proveedores — `backend/routers/proveedores.py`

| Método | Path | Rol | Notas |
|---|---|---|---|
| GET | `/proveedores?activo={bool}` | admin | Listar; sin filtro devuelve solo activos por default. |
| POST | `/proveedores` | admin | 409 si CUIT duplicado; 422 si CUIT inválido. |
| GET | `/proveedores/{proveedor_id}` | admin | 404 si no existe. |
| PATCH | `/proveedores/{proveedor_id}` | admin | Editar `razon_social`, `nombre_fantasia`, `direccion`, `activo`. **No** edita CUIT. |
| DELETE | `/proveedores/{proveedor_id}` | admin | Soft-delete siempre (`activo=false`). Nunca hard delete. |

### Configuración — `backend/routers/configuracion.py`

| Método | Path | Rol | Notas |
|---|---|---|---|
| GET | `/configuracion` | admin, depto | Singleton; siempre devuelve la fila `id=1`. Depto lee para mostrar datos bancarios al pagar. |
| PUT | `/configuracion` | admin | Actualiza todos los campos. Validaciones laxas (regex CUIT, max_length). |

### Coeficientes de departamento — extender `backend/routers/departamentos.py`

| Método | Path | Rol | Notas |
|---|---|---|---|
| GET | `/departamentos/{departamento_id}/coeficientes` | admin | Lista `[{clase_prorrateo_id, codigo, nombre, porcentaje}, ...]`. |
| PUT | `/departamentos/{departamento_id}/coeficientes` | admin | Reemplaza la lista completa: `[{clase_prorrateo_id, porcentaje}, ...]`. Validaciones: porcentaje 0..100, todas las clases referenciadas existen, no se repite `clase_prorrateo_id`. |

### Códigos de error

| Código | Cuándo |
|---|---|
| 401 | Token ausente / inválido |
| 403 | Rol sin permisos |
| 404 | Recurso no existe |
| 409 | Duplicado (CUIT proveedor, código de clase) |
| 422 | Validación pydantic falla |

## Frontend

Sidebar — nueva sección "Configuración" admin-only:

```
Configuración
  · Datos del consorcio   →  /configuracion
  · Clases de prorrateo   →  /clases-prorrateo
  · Proveedores            →  /proveedores
  · Departamentos          →  /departamentos        (movida acá si no estaba)
```

### `/configuracion` — `frontend/src/screens/Configuracion.jsx`

- Un solo `<form>` con 3 `<fieldset>`: "Consorcio", "Administración", "Banco".
- Inputs/textareas según campo. Botón "Guardar" abajo.
- Carga inicial: `GET /configuracion`. Submit: `PUT /configuracion`.
- Toast inline en éxito; mensajes de error pydantic mapeados a cada campo.

### `/clases-prorrateo` — `frontend/src/screens/ClasesProrrateo.jsx`

- Tabla: `Código | Nombre | Descripción | Activa | Acciones`.
- Botón "Nueva clase" arriba → modal con form (código, nombre, descripción).
- Por fila: Editar (modal sin `código` editable), botón toggle Activar/Desactivar.

### `/proveedores` — `frontend/src/screens/Proveedores.jsx`

- Tabla: `Razón social | Nombre fantasía | CUIT | Dirección | Activo | Acciones`.
- Toggle "Mostrar inactivos" (off por default).
- Botón "Nuevo proveedor" → modal con form (validación CUIT inline).
- Por fila: Editar (sin CUIT editable), Desactivar/Activar.

### `/departamentos` — extender `frontend/src/screens/Departamentos.jsx`

- Sumar columna `Coeficientes` con resumen `A: 2.17% · B: 2.26% · D: 2.17%`.
- Botón "Editar coeficientes" por fila → modal con tabla de clases **activas**, input numérico por clase (0..100, 4 decimales). Guarda con PUT replace-all.

### Comunes a todas las pantallas

- Mobile-first; modales fullscreen en mobile.
- Botón "Guardando..." mientras hay fetch en vuelo.
- Errores 422 mapeados inline en el campo.

## Tests

Un archivo por router. Cubren happy path + 401/403/404/409/422.

| Archivo | Cobertura específica |
|---|---|
| `tests/test_clases_prorrateo.py` | CRUD; duplicado de código (409); depto recibe 403 en todos los endpoints; soft vs hard delete según existencia de coeficientes; no se puede editar `codigo`. |
| `tests/test_proveedores.py` | CRUD; duplicado CUIT (409); CUIT inválido (422); soft-delete; filtro `?activo`; no se puede editar CUIT. |
| `tests/test_configuracion.py` | GET admin y depto (200); PUT admin (200), depto (403); singleton enforcement; validación de CUIT. |
| `tests/test_departamentos.py` (extender) | GET/PUT coeficientes; porcentaje fuera de rango (422); clase inexistente (404); clase duplicada en payload (422); depto recibe 403. |

## Seed inicial (`backend/seed.py`)

Pre-condición: la DB se recrea (clean start), consistente con la decisión de migración.

1. Crea 1 fila de `ConfiguracionConsorcio` con placeholders (strings = `"PENDIENTE"`, CUITs = `"00-00000000-0"`).
2. Crea 4 clases de prorrateo: A, B, C, D con nombres genéricos.
3. Crea 5 proveedores de ejemplo (limpieza, ascensor, seguros, banco, administración).
4. Mantiene los deptos existentes del seed previo.
5. Por cada depto, crea filas en `CoeficienteDepartamento` para clase A con porcentajes que sumen ~100%.
6. Mantiene los usuarios admin/representante/depto existentes.
7. **No** crea expensas ni comprobantes (limpio para que Fase 4 los introduzca con el modelo nuevo).

## Fuera de scope (Fase 1)

- Cualquier cambio al modelo `Expensa` o `Comprobante` (Fase 4).
- Modelo `Gasto` (Fase 2).
- Cálculo de sueldo del encargado y cargas sociales (Fase 3).
- Validación de suma de coeficientes (Fase 4, al cerrar período).
- Pantalla de Gastos (Fase 2).
- Cierre de período y generación automática de expensas (Fase 4).
- PDF de liquidación y reportes Ley 941 (Fase 6).
- Migraciones formales con Alembic.
- Búsqueda / filtros avanzados, bulk operations, histórico de cambios en CRUDs.

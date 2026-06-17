# Sistema Integral de Gestión de Consorcios

Aplicación web para administrar un consorcio: expensas, cuenta corriente por departamento, gastos, sueldos del personal, comunicación interna y reserva de amenities. Modelado sobre el formato de liquidación real de la **Ley 941 CABA**.

---

## Stack

| Capa | Tecnologías |
|---|---|
| Backend | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · SQLite |
| Frontend | React 18 · Vite · React Router |
| Auth | JWT HS256 con 3 roles fijos (Administración, Departamento, Representante) |
| Tests | pytest (**453 tests**) |
| Contrato | OpenAPI 3.1 (`openapi.yaml`) — documentación-primero |

---

## Cómo correrlo desde cero

> **Pre-requisitos:** Python 3.11+ y Node.js 18+.

### 1. Configurar variables de entorno

Copiá el template y completalo:

**Windows PowerShell**
```powershell
Copy-Item .env.example .env
```

**Linux / Mac**
```bash
cp .env.example .env
```

Editá el archivo `.env` y completá al menos estas dos variables:

```env
SECRET_KEY=<una cadena aleatoria de al menos 32 caracteres>
SEED_DEFAULT_PASSWORD=<la password con la que querés loguearte como demo>
```

Para generar una `SECRET_KEY` aleatoria:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Si `SEED_DEFAULT_PASSWORD` queda vacío, el seed genera una password aleatoria al vuelo y la imprime en consola — útil pero menos cómodo para probar.

### 2. Levantar el backend

```bash
python -m venv .venv

# Activar el venv:
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / Mac:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn backend.main:app --reload
```

API en `http://localhost:8000` · Swagger UI en `http://localhost:8000/docs`.

La primera vez, si la base está vacía, se siembra automáticamente con:

| Email | Rol | Password |
|---|---|---|
| `admin@consorcio.local` | Administración | `SEED_DEFAULT_PASSWORD` del `.env` |
| `depto-a@consorcio.local` | Departamento (UF-1A) | idem |
| `depto-b@consorcio.local` | Departamento (UF-2B) | idem |

También se cargan expensas de muestra, movimientos de cuenta corriente y un par de notas crédito/débito para que se vea algo desde el primer login.

### 3. Levantar el frontend (en otra terminal)

```bash
cd frontend
npm install
npm run dev
```

Frontend en `http://localhost:5173`. Ahí podés loguearte con cualquiera de los tres usuarios del seed.

### 4. (Opcional) Correr los tests

```bash
pytest -v
```

Debería pasar **453 tests**. Los tests usan SQLite en memoria, no tocan tu DB local.

### Reset rápido de datos

Si querés volver a sembrar desde cero:

```powershell
# Bajá el backend (Ctrl+C en la terminal de uvicorn)
Remove-Item -Force consorcio.db    # Windows
# rm -f consorcio.db               # Linux/Mac
# Volvé a levantar uvicorn — vuelve a sembrar
```

---

## Roles y permisos

| Rol | Resumen |
|---|---|
| **Administración** | Crea/edita todo: expensas, gastos, proveedores, empleados, liquidaciones, comunicados. Aprueba comprobantes y crea notas crédito/débito. |
| **Departamento** | Ve sus expensas y su cuenta corriente; presenta comprobantes de pago; lectura de comunicados y configuración del consorcio. |
| **Representante** | Lectura técnica + gestiona tareas y aprueba presupuestos. |

La identidad y el rol siempre se extraen del JWT — el backend nunca confía en `usuario_id`/`departamento_id` del body.

---

## Estructura del proyecto

```
backend/
  main.py                 # FastAPI app, lifespan, middlewares
  models.py               # SQLAlchemy 2.0 (Mapped[...])
  schemas.py              # Pydantic v2
  cuenta_corriente.py     # Módulo FIFO (puro, sin side effects)
  routers/                # Un router por recurso
  seed.py                 # Datos demo inicial
frontend/
  src/
    api/                  # Clientes fetch tipados
    auth/                 # Context + token + roles
    components/           # Modal, Tarjeta, BadgeEstado, Sidebar
    screens/              # Una pantalla por recurso
openapi.yaml              # Contrato API (fuente de verdad)
tests/                    # pytest, un archivo por router
docs/superpowers/
  specs/                  # Diseños de cada fase (brainstorming → spec)
  plans/                  # Planes TDD por tarea
```

---

## Roadmap

El proyecto se entrega en fases independientes:

| # | Fase | Estado |
|---|---|---|
| 1 | Modelo de datos central (rubros, clases de prorrateo, coeficientes, proveedores, configuración) | ✅ |
| 2 | Gastos del consorcio (carga, plan de cuotas, habituales, particulares) | ✅ |
| 3 | Encargado y cargas sociales (empleados, haberes, conceptos, liquidaciones mensuales) | ✅ |
| 3.5 | **Cuenta corriente por departamento** (movimientos contables + FIFO) | ✅ |
| 4 | Cierre de período y liquidación (saldo anterior, intereses, vencimientos) | pendiente |
| 5 | Caja, fondo de reparación, estado financiero | pendiente |
| 6 | Reportes Ley 941 + PDF de liquidación | pendiente |

Cada fase tiene su propio ciclo `brainstorming → spec → plan → implementación TDD` documentado en `docs/superpowers/`.

---

## Pieza destacada — Cuenta corriente con FIFO

Cada departamento tiene un libro de movimientos contables (`expensa_emitida`, `pago_recibido`, `nota_credito`, `nota_debito`, `interes_punitorio`). El monto es siempre positivo; el `tipo` decide el signo.

El estado de cada expensa (`pendiente | parcial | pagada | vencida`) **no se persiste** — se calcula al vuelo aplicando **First-In-First-Out**: los créditos disponibles cubren primero las expensas más viejas.

Ventajas:
- Cero riesgo de desincronización entre el estado y los movimientos reales.
- Soporta pagos parciales, sobre-pagos, notas de crédito/débito y devoluciones sin schema dedicado.
- Base sólida para que Fase 4 modele intereses punitorios sobre mora.

Implementación en `backend/cuenta_corriente.py` (~80 líneas, función pura, testeada en `tests/test_cuenta_corriente.py`).

---

## Decisiones de diseño que vale destacar

- **OpenAPI-first**: cada endpoint se documenta en `openapi.yaml` antes de implementarse.
- **Snapshot pattern** en liquidaciones: cuando se calcula una liquidación mensual, se congelan los valores de haberes y conceptos vigentes. Cambios futuros a esas tablas no rompen historial.
- **Estados terminales inmutables**: un comprobante aprobado no se puede "des-aprobar"; el admin compensa con nota crédito.
- **Soft-delete** en comprobantes y comunicados: oculta de la vista sin perder el registro contable subyacente.
- **Aislamiento por unidad** en backend: los departamentos solo ven sus propios datos, validado server-side incluso si el frontend manda otro `departamento_id` en el query.

---

## Autor

Matías Bauer — capacitación IISAIA 2026 · matiasbauer@gmail.com

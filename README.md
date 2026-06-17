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

## Cómo correrlo

### Backend

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows PowerShell
# source .venv/bin/activate       # Linux/Mac
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

API disponible en `http://localhost:8000` · Docs interactivas en `http://localhost:8000/docs`.

Al levantar por primera vez, si la base está vacía, se siembra con usuarios demo:

| Email | Rol |
|---|---|
| `admin@consorcio.local` | Administración |
| `depto-a@consorcio.local` | Departamento (UF-1A) |
| `depto-b@consorcio.local` | Departamento (UF-2B) |

La password se imprime en consola al sembrar (o se toma de `SEED_DEFAULT_PASSWORD` si está en `.env`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Disponible en `http://localhost:5173`.

### Tests

```bash
pytest -v
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

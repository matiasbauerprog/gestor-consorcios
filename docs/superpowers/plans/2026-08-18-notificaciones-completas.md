# Notificaciones completas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir la campanita en un sistema de notificaciones real: catálogo declarativo de doce eventos, avisos hacia la administración, pendientes que se apagan solos, preferencias de mail por usuario y bandeja completa.

**Architecture:** Un paquete `backend/notificaciones/` con un catálogo declarativo (una entrada por evento) y un emisor único. Los routers pasan de llamar funciones a medida a llamar `emitir("clave", ...)`. El correo sale por `BackgroundTasks`, después de la respuesta. Los avisos que representan trabajo pendiente guardan a qué entidad apuntan y se apagan para todos cuando esa entidad se resuelve.

**Tech Stack:** Python 3 + FastAPI + SQLAlchemy 2.0 + Alembic + SQLite. Frontend React + Vite. Tests con pytest y vitest.

**Spec:** `docs/superpowers/specs/2026-08-18-notificaciones-completas-design.md`

## Global Constraints

- **OpenAPI-first**: todo endpoint nuevo o modificado se documenta en `openapi.yaml` **antes** de tocar el router. Path params con nombre completo del recurso (`{notificacion_id}`). Cada operación declara `response_model` y `status_code` explícitos.
- **Identidad siempre del token**: `usuario_id`, `departamento_id` y `actor_usuario_id` salen de `CurrentUser`, nunca del body.
- **Aislamiento por consorcio**: toda query de notificaciones filtra por el `cid` de `get_consorcio_activo`.
- **Tests**: un archivo por router en `tests/test_<recurso>.py`. Validaciones de schema se asertan con **400**, no 422 (el proyecto convierte `RequestValidationError`).
- **Comando de tests**: `./.venv/Scripts/python.exe -m pytest -v` (Windows con venv) o `pytest -v`.
- **Los helpers viejos desaparecen**: al terminar el plan no debe existir ninguna referencia a `crear_notificacion`, `notificar_cambio_estado_peticion`, `notificar_reserva_creada` ni `notificar_reserva_cancelada_por_admin`.
- **Restricciones que imponen tests existentes** (no negociables):
  - el mensaje de `peticion_estado_cambiado` debe seguir conteniendo el valor crudo del estado (`convertida_en_trabajo`), porque `tests/test_trabajos.py` filtra por ese texto;
  - un departamento que cancela su propia reserva no genera **ninguna** notificación, porque `tests/test_reservas.py::test_depto_cancela_su_reserva_no_genera_notificacion` cuenta filas totales.
- **La campanita nunca se puede apagar.** El interruptor de preferencias apaga sólo el mail.

---

### Task 1: Modelo de datos y migración

**Files:**
- Modify: `backend/models.py:1041-1058` (clase `Notificacion`)
- Create: `backend/migrations/versions/<hash>_notificaciones_completas.py`
- Test: `tests/test_notificaciones.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Notificacion.tipo: str`, `Notificacion.entidad_tipo: str | None`, `Notificacion.entidad_id: int | None`; clase `PreferenciaNotificacion(id, usuario_id, tipo, email_activo)`.

- [ ] **Step 1: Write the failing test**

Agregar al final de `tests/test_notificaciones.py`:

```python
def test_notificacion_guarda_tipo_y_entidad(db):
    from backend.models import Notificacion

    n = Notificacion(
        consorcio_id=1,
        usuario_id=2,
        tipo="peticion_nueva",
        mensaje="X",
        link="/peticiones",
        entidad_tipo="peticion",
        entidad_id=10,
    )
    db.add(n)
    db.commit()
    assert n.tipo == "peticion_nueva"
    assert n.entidad_tipo == "peticion"
    assert n.entidad_id == 10


def test_preferencia_notificacion_unica_por_usuario_y_tipo(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from backend.models import PreferenciaNotificacion

    db.add(PreferenciaNotificacion(usuario_id=2, tipo="comunicado_publicado", email_activo=False))
    db.commit()

    db.add(PreferenciaNotificacion(usuario_id=2, tipo="comunicado_publicado", email_activo=True))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones.py::test_notificacion_guarda_tipo_y_entidad tests/test_notificaciones.py::test_preferencia_notificacion_unica_por_usuario_y_tipo -v`
Expected: FAIL — `TypeError: 'tipo' is an invalid keyword argument for Notificacion` y `ImportError: cannot import name 'PreferenciaNotificacion'`.

- [ ] **Step 3: Modificar la clase `Notificacion`**

En `backend/models.py`, dentro de `class Notificacion(Base)`, después de `usuario_id` y antes de `mensaje`:

```python
    tipo: Mapped[str] = mapped_column(
        String(60), nullable=False, server_default="legacy", index=True,
    )
```

Y después de `link`:

```python
    # Entero suelto a propósito, NO foreign key: la notificación tiene que
    # sobrevivir al borrado de la cosa que la originó (una petición borrada
    # por el depto deja su aviso en el historial del administrador).
    entidad_tipo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entidad_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

Al final de la clase, antes del cierre:

```python
    __table_args__ = (
        Index(
            "ix_notificaciones_pendiente",
            "consorcio_id", "entidad_tipo", "entidad_id", "leida",
        ),
    )
```

Verificar que `Index` e `Integer` estén en el import de `sqlalchemy` al tope del archivo; agregarlos si faltan.

- [ ] **Step 4: Agregar la clase `PreferenciaNotificacion`**

Inmediatamente después de `class Notificacion(Base)`:

```python
class PreferenciaNotificacion(Base):
    """Diferencia contra el default del catálogo, no la tabla completa.

    Un usuario que nunca tocó un interruptor no tiene fila y le vale
    `email_por_defecto` del evento. Eso permite cambiar un default más
    adelante y que alcance a todos los que no opinaron, respetando a los
    que sí. Poner un interruptor en su valor por defecto borra la fila.
    """
    __tablename__ = "preferencias_notificacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    email_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        UniqueConstraint("usuario_id", "tipo", name="uq_preferencia_usuario_tipo"),
    )
```

Verificar que `UniqueConstraint` esté importado de `sqlalchemy`; agregarlo si falta.

- [ ] **Step 5: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones.py -v`
Expected: PASS (los dos nuevos y los seis que ya estaban).

- [ ] **Step 6: Generar la migración**

Run: `./.venv/Scripts/python.exe -m alembic revision --autogenerate -m "notificaciones completas"`

Abrir el archivo generado en `backend/migrations/versions/` y verificar:
- `down_revision` es `'b4375d00a25c'` (la cabeza actual);
- el `upgrade()` crea `preferencias_notificacion` con su unique;
- las tres columnas nuevas de `notificaciones` se agregan con `batch_alter_table` (SQLite lo exige) y `tipo` con `server_default="legacy"`.

Si el autogenerate emitió `add_column` sin batch, reescribir esa parte así:

```python
    with op.batch_alter_table('notificaciones', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tipo', sa.String(length=60), nullable=False, server_default='legacy'))
        batch_op.add_column(sa.Column('entidad_tipo', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('entidad_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_notificaciones_tipo'), ['tipo'], unique=False)
        batch_op.create_index(
            'ix_notificaciones_pendiente',
            ['consorcio_id', 'entidad_tipo', 'entidad_id', 'leida'],
            unique=False,
        )
```

- [ ] **Step 7: Verificar que la migración corre**

Run: `./.venv/Scripts/python.exe -m alembic upgrade head`
Expected: sin errores.

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: todo el suite verde.

- [ ] **Step 8: Commit**

```bash
git add backend/models.py backend/migrations/versions tests/test_notificaciones.py
git commit -m "feat: tipo y entidad en notificaciones, y tabla de preferencias"
```

---

### Task 2: El catálogo de eventos

**Files:**
- Delete: `backend/notificaciones.py`
- Create: `backend/notificaciones/__init__.py`
- Create: `backend/notificaciones/catalogo.py`
- Create: `tests/test_notificaciones_catalogo.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `Audiencia` (enum: `DEPARTAMENTO`, `ADMINISTRACION`)
  - `EventoNotificacion` (dataclass frozen)
  - `CATALOGO: dict[str, EventoNotificacion]`
  - `evento(clave: str) -> EventoNotificacion`
  - `eventos_para_rol(rol: Rol) -> list[EventoNotificacion]`
  - Las doce constantes de clave (`PETICION_ESTADO_CAMBIADO`, etc.).

**Nota de orden:** este task convierte el módulo en paquete. Para que el suite no quede roto en el medio, `__init__.py` reexporta temporalmente los cuatro helpers viejos moviéndolos tal cual a `backend/notificaciones/legacy.py`. El Task 6 los borra.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_notificaciones_catalogo.py`:

```python
"""El catálogo es declarativo: estos tests lo tratan como datos, no como código."""
import pytest

from backend.models import Rol
from backend.notificaciones.catalogo import (
    CATALOGO,
    Audiencia,
    evento,
    eventos_para_rol,
)


def test_catalogo_tiene_los_doce_eventos():
    assert len(CATALOGO) == 12


def test_evento_desconocido_explota():
    with pytest.raises(KeyError):
        evento("no_existe")


def test_la_clave_del_dict_coincide_con_la_del_evento():
    for clave, ev in CATALOGO.items():
        assert ev.clave == clave


def test_un_evento_que_no_manda_mail_no_declara_asunto():
    for ev in CATALOGO.values():
        if not ev.email_por_defecto and ev.asunto is None:
            assert ev.cuerpo is None, f"{ev.clave} declara cuerpo sin asunto"
        if ev.asunto is not None:
            assert ev.cuerpo is not None, f"{ev.clave} declara asunto sin cuerpo"


def test_un_evento_que_manda_mail_por_defecto_declara_asunto():
    for ev in CATALOGO.values():
        if ev.email_por_defecto:
            assert ev.asunto is not None, f"{ev.clave} manda mail sin asunto"


def test_solo_reserva_confirmada_es_solo_mail():
    solo_mail = [ev.clave for ev in CATALOGO.values() if not ev.crea_campanita]
    assert solo_mail == ["reserva_confirmada"]


def test_los_pendientes_son_exactamente_dos():
    pendientes = sorted(ev.clave for ev in CATALOGO.values() if ev.entidad_tipo)
    assert pendientes == ["comprobante_presentado", "peticion_nueva"]


def test_eventos_para_rol_departamento():
    claves = {ev.clave for ev in eventos_para_rol(Rol.departamento)}
    assert claves == {
        "peticion_estado_cambiado",
        "trabajo_completado",
        "reserva_confirmada",
        "reserva_cancelada_por_admin",
        "comunicado_publicado",
        "expensa_emitida",
        "comprobante_aprobado",
        "comprobante_rechazado",
    }


def test_eventos_para_rol_administracion():
    claves = {ev.clave for ev in eventos_para_rol(Rol.administracion)}
    assert claves == {
        "peticion_nueva",
        "comprobante_presentado",
        "peticion_borrada_por_depto",
        "reserva_nueva_de_depto",
    }


def test_eventos_para_representante_es_vacio():
    assert eventos_para_rol(Rol.representante) == []


def test_mensaje_de_peticion_incluye_el_estado_crudo():
    # tests/test_trabajos.py filtra por este texto. No es cosmético.
    ev = evento("peticion_estado_cambiado")
    texto = ev.mensaje({"titulo": "Filtración", "estado": "convertida_en_trabajo"})
    assert "convertida_en_trabajo" in texto


def test_todas_las_audiencias_son_conocidas():
    for ev in CATALOGO.values():
        assert ev.audiencia in (Audiencia.DEPARTAMENTO, Audiencia.ADMINISTRACION)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_catalogo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.notificaciones.catalogo'`.

- [ ] **Step 3: Convertir el módulo en paquete**

```bash
mkdir backend/notificaciones
git mv backend/notificaciones.py backend/notificaciones/legacy.py
```

En `backend/notificaciones/legacy.py`, corregir los imports relativos: `from .mail_service import` pasa a `from ..mail_service import`, y `from .models import` pasa a `from ..models import` (hay tres apariciones de `from .models import`, dos de ellas dentro de funciones).

- [ ] **Step 4: Escribir `backend/notificaciones/catalogo.py`**

```python
"""Catálogo declarativo de eventos de notificación.

Cada evento se define UNA vez acá: quién lo recibe, qué texto muestra, a
dónde lleva, si manda mail por defecto y —si representa trabajo pendiente—
a qué entidad apunta. El emisor no sabe nada de eventos concretos; lee de
este diccionario. Agregar un aviso nuevo es agregar una entrada acá y una
línea en el lugar donde ocurre la acción.
"""
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from ..models import Rol


class Audiencia(str, Enum):
    DEPARTAMENTO = "departamento"
    ADMINISTRACION = "administracion"


_ROL_POR_AUDIENCIA = {
    Audiencia.DEPARTAMENTO: Rol.departamento,
    Audiencia.ADMINISTRACION: Rol.administracion,
}


@dataclass(frozen=True)
class EventoNotificacion:
    clave: str
    audiencia: Audiencia
    etiqueta: str
    mensaje: Callable[[dict], str]
    link: Callable[[dict], str | None]
    crea_campanita: bool = True
    email_por_defecto: bool = False
    asunto: Callable[[dict], str] | None = None
    cuerpo: Callable[[dict], str] | None = None
    # No-None ⇒ el evento es un pendiente y puede apagarse solo.
    entidad_tipo: str | None = None

    @property
    def puede_mandar_mail(self) -> bool:
        return self.asunto is not None

    @property
    def editable(self) -> bool:
        """False ⇒ el interruptor se muestra pero no se puede tocar.

        Dos casos: el evento nunca manda mail (no hay nada que apagar), o el
        evento es sólo-mail (apagarlo dejaría al usuario sin ningún aviso).
        """
        return self.puede_mandar_mail and self.crea_campanita

    @property
    def motivo_no_editable(self) -> str | None:
        if self.editable:
            return None
        if not self.puede_mandar_mail:
            return "Sólo aparece en la campanita."
        return "Sólo se envía por correo."


def _firma(texto: str) -> str:
    return f"Hola,\n\n{texto}\n\nSaludos,\nAdministración."


# --- Claves ---------------------------------------------------------------

PETICION_ESTADO_CAMBIADO = "peticion_estado_cambiado"
TRABAJO_COMPLETADO = "trabajo_completado"
RESERVA_CONFIRMADA = "reserva_confirmada"
RESERVA_CANCELADA_POR_ADMIN = "reserva_cancelada_por_admin"
COMUNICADO_PUBLICADO = "comunicado_publicado"
EXPENSA_EMITIDA = "expensa_emitida"
COMPROBANTE_APROBADO = "comprobante_aprobado"
COMPROBANTE_RECHAZADO = "comprobante_rechazado"
PETICION_NUEVA = "peticion_nueva"
COMPROBANTE_PRESENTADO = "comprobante_presentado"
PETICION_BORRADA_POR_DEPTO = "peticion_borrada_por_depto"
RESERVA_NUEVA_DE_DEPTO = "reserva_nueva_de_depto"


def _msg_peticion_estado(c: dict) -> str:
    # El valor CRUDO del estado va en el texto: tests/test_trabajos.py filtra
    # por "convertida_en_trabajo". Cambiar esto rompe ese test, a propósito.
    return f"Tu petición '{c['titulo']}' cambió de estado a: {c['estado']}."


def _msg_reserva_confirmada(c: dict) -> str:
    texto = f"Tu reserva de {c['amenity']} para el {c['fecha']} fue confirmada."
    if c.get("monto") is not None:
        texto += f"\nSe cargó ${c['monto']:.2f} a tu cuenta corriente."
    return texto


def _msg_reserva_cancelada(c: dict) -> str:
    texto = f"La administración canceló tu reserva de {c['amenity']} del {c['fecha']}."
    if c.get("monto_reversado") is not None:
        texto += f" Se reversó el cargo de ${c['monto_reversado']:.2f}."
    return texto


def _msg_comprobante_rechazado(c: dict) -> str:
    texto = f"Tu comprobante de pago por ${c['monto']:.2f} fue rechazado."
    if c.get("motivo"):
        texto += f" Motivo: {c['motivo']}"
    return texto


_EVENTOS = [
    # --- Al departamento --------------------------------------------------
    EventoNotificacion(
        clave=PETICION_ESTADO_CAMBIADO,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Cambia el estado de mi petición",
        mensaje=_msg_peticion_estado,
        link=lambda c: "/peticiones",
        email_por_defecto=True,
        asunto=lambda c: f"Tu petición #{c['peticion_id']} fue actualizada",
        cuerpo=lambda c: _firma(_msg_peticion_estado(c)),
    ),
    EventoNotificacion(
        clave=TRABAJO_COMPLETADO,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Se completa el trabajo de mi petición",
        mensaje=lambda c: f"El trabajo de tu petición '{c['titulo']}' fue completado.",
        link=lambda c: "/peticiones",
        asunto=lambda c: "El trabajo de tu petición fue completado",
        cuerpo=lambda c: _firma(
            f"El trabajo de tu petición '{c['titulo']}' fue completado."
        ),
    ),
    EventoNotificacion(
        clave=RESERVA_CONFIRMADA,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Confirmación de mi reserva",
        mensaje=_msg_reserva_confirmada,
        link=lambda c: "/reservas",
        # Sin campanita: el usuario acaba de ver la confirmación en pantalla.
        crea_campanita=False,
        email_por_defecto=True,
        asunto=lambda c: f"Reserva confirmada: {c['amenity']}",
        cuerpo=lambda c: f"{_msg_reserva_confirmada(c)}\n\nSaludos,\nAdministración.",
    ),
    EventoNotificacion(
        clave=RESERVA_CANCELADA_POR_ADMIN,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="La administración cancela mi reserva",
        mensaje=_msg_reserva_cancelada,
        link=lambda c: "/reservas",
        email_por_defecto=True,
        asunto=lambda c: f"Tu reserva de {c['amenity']} fue cancelada",
        cuerpo=lambda c: _firma(_msg_reserva_cancelada(c)),
    ),
    EventoNotificacion(
        clave=COMUNICADO_PUBLICADO,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Se publica un comunicado",
        mensaje=lambda c: f"Nuevo comunicado: {c['titulo']}",
        link=lambda c: "/comunicados",
        email_por_defecto=True,
        asunto=lambda c: f"Nuevo comunicado: {c['titulo']}",
        cuerpo=lambda c: _firma(
            f"Se publicó un comunicado nuevo: {c['titulo']}\n\n{c['cuerpo']}"
        ),
    ),
    EventoNotificacion(
        clave=EXPENSA_EMITIDA,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Se emite mi expensa del período",
        mensaje=lambda c: (
            f"Ya está disponible tu expensa del período {c['periodo']}: "
            f"${c['monto']:.2f}, vence el {c['vencimiento']}."
        ),
        link=lambda c: "/expensas",
        email_por_defecto=True,
        asunto=lambda c: f"Expensa {c['periodo']} disponible",
        cuerpo=lambda c: _firma(
            f"Ya está disponible tu expensa del período {c['periodo']} por "
            f"${c['monto']:.2f}, con vencimiento el {c['vencimiento']}."
        ),
    ),
    EventoNotificacion(
        clave=COMPROBANTE_APROBADO,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Me aprueban un comprobante de pago",
        mensaje=lambda c: f"Tu comprobante de pago por ${c['monto']:.2f} fue aprobado.",
        link=lambda c: "/comprobantes",
        asunto=lambda c: "Tu comprobante de pago fue aprobado",
        cuerpo=lambda c: _firma(
            f"Tu comprobante de pago por ${c['monto']:.2f} fue aprobado."
        ),
    ),
    EventoNotificacion(
        clave=COMPROBANTE_RECHAZADO,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Me rechazan un comprobante de pago",
        mensaje=_msg_comprobante_rechazado,
        link=lambda c: "/comprobantes",
        email_por_defecto=True,
        asunto=lambda c: "Tu comprobante de pago fue rechazado",
        cuerpo=lambda c: _firma(_msg_comprobante_rechazado(c)),
    ),
    # --- A la administración ----------------------------------------------
    EventoNotificacion(
        clave=PETICION_NUEVA,
        audiencia=Audiencia.ADMINISTRACION,
        etiqueta="Un departamento crea una petición",
        mensaje=lambda c: f"{c['codigo_depto']} creó la petición '{c['titulo']}'.",
        link=lambda c: "/peticiones",
        entidad_tipo="peticion",
        asunto=lambda c: f"Nueva petición de {c['codigo_depto']}",
        cuerpo=lambda c: _firma(
            f"{c['codigo_depto']} creó la petición '{c['titulo']}'."
        ),
    ),
    EventoNotificacion(
        clave=COMPROBANTE_PRESENTADO,
        audiencia=Audiencia.ADMINISTRACION,
        etiqueta="Un departamento presenta un comprobante",
        mensaje=lambda c: (
            f"{c['codigo_depto']} presentó un comprobante por ${c['monto']:.2f}."
        ),
        link=lambda c: "/comprobantes",
        entidad_tipo="comprobante",
        asunto=lambda c: f"Comprobante presentado por {c['codigo_depto']}",
        cuerpo=lambda c: _firma(
            f"{c['codigo_depto']} presentó un comprobante de pago por "
            f"${c['monto']:.2f} y está esperando verificación."
        ),
    ),
    EventoNotificacion(
        clave=PETICION_BORRADA_POR_DEPTO,
        audiencia=Audiencia.ADMINISTRACION,
        etiqueta="Un departamento borra su petición",
        mensaje=lambda c: f"{c['codigo_depto']} borró su petición '{c['titulo']}'.",
        link=lambda c: "/peticiones",
        asunto=lambda c: f"{c['codigo_depto']} borró una petición",
        cuerpo=lambda c: _firma(
            f"{c['codigo_depto']} borró su petición '{c['titulo']}'."
        ),
    ),
    EventoNotificacion(
        clave=RESERVA_NUEVA_DE_DEPTO,
        audiencia=Audiencia.ADMINISTRACION,
        etiqueta="Un departamento reserva un amenity",
        mensaje=lambda c: (
            f"{c['codigo_depto']} reservó {c['amenity']} para el {c['fecha']}."
        ),
        link=lambda c: "/reservas",
        asunto=lambda c: f"Nueva reserva de {c['codigo_depto']}",
        cuerpo=lambda c: _firma(
            f"{c['codigo_depto']} reservó {c['amenity']} para el {c['fecha']}."
        ),
    ),
]

CATALOGO: dict[str, EventoNotificacion] = {ev.clave: ev for ev in _EVENTOS}


def evento(clave: str) -> EventoNotificacion:
    """Devuelve el evento. `KeyError` si la clave no existe.

    Explota a propósito: las claves son constantes de este módulo, así que
    una clave desconocida es un bug de programación, no un dato del usuario.
    """
    return CATALOGO[clave]


def eventos_para_rol(rol: Rol) -> list[EventoNotificacion]:
    """Eventos que un usuario de ese rol puede llegar a recibir."""
    return [
        ev for ev in _EVENTOS
        if _ROL_POR_AUDIENCIA.get(ev.audiencia) == rol
    ]
```

- [ ] **Step 5: Escribir `backend/notificaciones/__init__.py`**

```python
"""Sistema de notificaciones.

`emitir` y `resolver_pendiente` son la única API pública. Los helpers de
`legacy` son transitorios y los borra la tarea que migra los cuatro eventos
originales al catálogo.
"""
from .legacy import (  # noqa: F401  — transitorio, se borra en el Task 6
    crear_notificacion,
    notificar_cambio_estado_peticion,
    notificar_reserva_cancelada_por_admin,
    notificar_reserva_creada,
)

__all__ = [
    "crear_notificacion",
    "notificar_cambio_estado_peticion",
    "notificar_reserva_cancelada_por_admin",
    "notificar_reserva_creada",
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_catalogo.py -v`
Expected: PASS, los doce.

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: todo el suite verde — el paquete reexporta lo mismo que exportaba el módulo.

- [ ] **Step 7: Commit**

```bash
git add backend/notificaciones tests/test_notificaciones_catalogo.py
git commit -m "feat: catalogo declarativo de los doce eventos de notificacion"
```

---

### Task 3: Destinatarios

**Files:**
- Create: `backend/notificaciones/destinatarios.py`
- Test: `tests/test_notificaciones_destinatarios.py`

**Interfaces:**
- Consumes: `Audiencia` de `catalogo.py`.
- Produces: `resolver_destinatarios(db, audiencia, *, consorcio_id, departamento_id, excluir_usuario_id) -> list[Usuario]`.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_notificaciones_destinatarios.py`:

```python
"""Resolución de audiencias a listas de usuarios concretos."""
import pytest

from backend.models import Rol, Usuario
from backend.notificaciones.catalogo import Audiencia
from backend.notificaciones.destinatarios import resolver_destinatarios


def test_departamento_devuelve_los_usuarios_de_ese_depto(db):
    us = resolver_destinatarios(
        db, Audiencia.DEPARTAMENTO,
        consorcio_id=1, departamento_id=1, excluir_usuario_id=None,
    )
    assert [u.id for u in us] == [2]


def test_departamento_sin_departamento_id_explota(db):
    with pytest.raises(ValueError):
        resolver_destinatarios(
            db, Audiencia.DEPARTAMENTO,
            consorcio_id=1, departamento_id=None, excluir_usuario_id=None,
        )


def test_administracion_devuelve_los_admin_de_esa_administracion(db):
    us = resolver_destinatarios(
        db, Audiencia.ADMINISTRACION,
        consorcio_id=1, departamento_id=None, excluir_usuario_id=None,
    )
    assert [u.id for u in us] == [1]


def test_administracion_ignora_admins_de_otra_administracion(db, dos_consorcios):
    us = resolver_destinatarios(
        db, Audiencia.ADMINISTRACION,
        consorcio_id=1, departamento_id=None, excluir_usuario_id=None,
    )
    ids = [u.id for u in us]
    assert 1 in ids
    assert 6 not in ids  # admin del consorcio 2


def test_excluye_al_actor(db):
    us = resolver_destinatarios(
        db, Audiencia.ADMINISTRACION,
        consorcio_id=1, departamento_id=None, excluir_usuario_id=1,
    )
    assert us == []


def test_ignora_usuarios_dados_de_baja(db):
    u = db.get(Usuario, 2)
    u.activa = False
    db.flush()
    us = resolver_destinatarios(
        db, Audiencia.DEPARTAMENTO,
        consorcio_id=1, departamento_id=1, excluir_usuario_id=None,
    )
    assert us == []


def test_consorcio_inexistente_no_devuelve_nada(db):
    us = resolver_destinatarios(
        db, Audiencia.ADMINISTRACION,
        consorcio_id=999, departamento_id=None, excluir_usuario_id=None,
    )
    assert us == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_destinatarios.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.notificaciones.destinatarios'`.

- [ ] **Step 3: Escribir `backend/notificaciones/destinatarios.py`**

```python
"""Traduce una audiencia del catálogo a la lista concreta de usuarios."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Consorcio, Rol, Usuario
from .catalogo import Audiencia


def resolver_destinatarios(
    db: Session,
    audiencia: Audiencia,
    *,
    consorcio_id: int,
    departamento_id: int | None,
    excluir_usuario_id: int | None,
) -> list[Usuario]:
    """Usuarios activos que deben recibir un evento de esta audiencia.

    `excluir_usuario_id` es el actor: nadie recibe el evento que causó.
    """
    if audiencia == Audiencia.DEPARTAMENTO:
        if departamento_id is None:
            raise ValueError(
                "Un evento con audiencia DEPARTAMENTO necesita departamento_id."
            )
        stmt = select(Usuario).where(
            Usuario.departamento_id == departamento_id,
            Usuario.rol == Rol.departamento,
        )
    elif audiencia == Audiencia.ADMINISTRACION:
        consorcio = db.get(Consorcio, consorcio_id)
        if consorcio is None:
            return []
        stmt = select(Usuario).where(
            Usuario.administracion_id == consorcio.administracion_id,
            Usuario.rol == Rol.administracion,
        )
    else:  # pragma: no cover — el enum no tiene más miembros
        raise ValueError(f"Audiencia desconocida: {audiencia}")

    stmt = stmt.where(Usuario.activa == True)  # noqa: E712
    if excluir_usuario_id is not None:
        stmt = stmt.where(Usuario.id != excluir_usuario_id)

    return list(db.scalars(stmt.order_by(Usuario.id)).all())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_destinatarios.py -v`
Expected: PASS, los siete.

- [ ] **Step 5: Commit**

```bash
git add backend/notificaciones/destinatarios.py tests/test_notificaciones_destinatarios.py
git commit -m "feat: resolucion de audiencias a destinatarios"
```

---

### Task 4: Preferencias efectivas

**Files:**
- Create: `backend/notificaciones/preferencias.py`
- Test: `tests/test_notificaciones_preferencias.py`

**Interfaces:**
- Consumes: `EventoNotificacion` de `catalogo.py`, `PreferenciaNotificacion` de `models.py`.
- Produces:
  - `email_activo_para(db, usuario_id: int, ev: EventoNotificacion) -> bool`
  - `preferencias_de(db, usuario_id: int) -> dict[str, bool]` (sólo las filas guardadas)
  - `guardar_preferencia(db, usuario_id: int, ev: EventoNotificacion, email_activo: bool) -> None`

- [ ] **Step 1: Write the failing test**

Crear `tests/test_notificaciones_preferencias.py`:

```python
"""Sólo se persisten las diferencias contra el default del catálogo."""
from backend.models import PreferenciaNotificacion
from backend.notificaciones.catalogo import evento
from backend.notificaciones.preferencias import (
    email_activo_para,
    guardar_preferencia,
    preferencias_de,
)

# comunicado_publicado tiene email_por_defecto=True.
# comprobante_aprobado tiene email_por_defecto=False.


def test_sin_fila_vale_el_default_del_catalogo(db):
    assert email_activo_para(db, 2, evento("comunicado_publicado")) is True
    assert email_activo_para(db, 2, evento("comprobante_aprobado")) is False


def test_guardar_distinto_del_default_crea_fila(db):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    filas = db.query(PreferenciaNotificacion).filter_by(usuario_id=2).all()
    assert len(filas) == 1
    assert filas[0].email_activo is False
    assert email_activo_para(db, 2, evento("comunicado_publicado")) is False


def test_volver_al_default_borra_la_fila(db):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    guardar_preferencia(db, 2, evento("comunicado_publicado"), True)
    db.flush()
    assert db.query(PreferenciaNotificacion).filter_by(usuario_id=2).count() == 0
    assert email_activo_para(db, 2, evento("comunicado_publicado")) is True


def test_guardar_igual_al_default_no_crea_fila(db):
    guardar_preferencia(db, 2, evento("comprobante_aprobado"), False)
    db.flush()
    assert db.query(PreferenciaNotificacion).filter_by(usuario_id=2).count() == 0


def test_reguardar_el_mismo_valor_no_duplica(db):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    assert db.query(PreferenciaNotificacion).filter_by(usuario_id=2).count() == 1


def test_preferencias_de_devuelve_solo_lo_guardado(db):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    assert preferencias_de(db, 2) == {"comunicado_publicado": False}


def test_las_preferencias_no_se_cruzan_entre_usuarios(db):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    assert email_activo_para(db, 3, evento("comunicado_publicado")) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_preferencias.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.notificaciones.preferencias'`.

- [ ] **Step 3: Escribir `backend/notificaciones/preferencias.py`**

```python
"""Preferencias de mail por usuario y por evento.

Se persiste sólo la diferencia contra el default del catálogo. Un usuario
que nunca opinó no tiene fila, así que cambiar un default más adelante lo
alcanza a él y respeta al que sí opinó.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PreferenciaNotificacion
from .catalogo import EventoNotificacion


def preferencias_de(db: Session, usuario_id: int) -> dict[str, bool]:
    """Sólo las filas guardadas — los defaults no aparecen acá."""
    filas = db.scalars(
        select(PreferenciaNotificacion).where(
            PreferenciaNotificacion.usuario_id == usuario_id
        )
    ).all()
    return {f.tipo: f.email_activo for f in filas}


def email_activo_para(db: Session, usuario_id: int, ev: EventoNotificacion) -> bool:
    """Valor efectivo: la fila del usuario si existe, el default si no."""
    if not ev.puede_mandar_mail:
        return False
    fila = db.scalar(
        select(PreferenciaNotificacion).where(
            PreferenciaNotificacion.usuario_id == usuario_id,
            PreferenciaNotificacion.tipo == ev.clave,
        )
    )
    if fila is None:
        return ev.email_por_defecto
    return fila.email_activo


def guardar_preferencia(
    db: Session, usuario_id: int, ev: EventoNotificacion, email_activo: bool
) -> None:
    """Crea, actualiza o borra la fila según se aparte o no del default.

    No commitea — el caller lo hace.
    """
    fila = db.scalar(
        select(PreferenciaNotificacion).where(
            PreferenciaNotificacion.usuario_id == usuario_id,
            PreferenciaNotificacion.tipo == ev.clave,
        )
    )

    if email_activo == ev.email_por_defecto:
        # Volver al default es dejar de tener opinión, no guardar el default.
        if fila is not None:
            db.delete(fila)
        return

    if fila is None:
        db.add(PreferenciaNotificacion(
            usuario_id=usuario_id, tipo=ev.clave, email_activo=email_activo,
        ))
    else:
        fila.email_activo = email_activo
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_preferencias.py -v`
Expected: PASS, los siete.

- [ ] **Step 5: Commit**

```bash
git add backend/notificaciones/preferencias.py tests/test_notificaciones_preferencias.py
git commit -m "feat: preferencias de mail como diferencia contra el default"
```

---

### Task 5: Correo diferido

**Files:**
- Create: `backend/notificaciones/correo.py`
- Test: `tests/test_notificaciones_correo.py`

**Interfaces:**
- Consumes: `enviar_email` de `backend/mail_service.py`, `errores.registrar`, `SessionLocal` de `backend/database.py`.
- Produces:
  - `MailPendiente` (dataclass frozen: `to: str`, `subject: str`, `body: str`, `clave_evento: str`)
  - `encolar(tareas: BackgroundTasks | None, mails: list[MailPendiente]) -> None`
  - `enviar_uno(mail: MailPendiente) -> None` (la función que corre en background; nunca levanta)

- [ ] **Step 1: Write the failing test**

Crear `tests/test_notificaciones_correo.py`:

```python
"""El correo sale después de la respuesta y nunca puede romper la operación."""
from backend.notificaciones.correo import MailPendiente, encolar, enviar_uno


def test_enviar_uno_manda_por_mail_service(capsys):
    enviar_uno(MailPendiente(
        to="a@test.local", subject="Asunto", body="Cuerpo",
        clave_evento="comunicado_publicado",
    ))
    salida = capsys.readouterr().out
    assert "a@test.local" in salida
    assert "Asunto" in salida


def test_enviar_uno_no_levanta_si_el_envio_explota(monkeypatch, db, caplog):
    from backend import database as db_module
    from backend.notificaciones import correo

    def _explota(**kwargs):
        raise RuntimeError("SMTP caído")

    monkeypatch.setattr(correo, "enviar_email", _explota)
    monkeypatch.setattr(db_module, "SessionLocal", lambda: db)

    # No debe levantar: el contrato es que un mail caído nunca propaga.
    enviar_uno(MailPendiente(
        to="a@test.local", subject="X", body="Y",
        clave_evento="comunicado_publicado",
    ))


def test_enviar_uno_registra_el_error_con_codigo(monkeypatch, db):
    from backend import database as db_module
    from backend.models import ErrorRegistrado
    from backend.notificaciones import correo

    def _explota(**kwargs):
        raise RuntimeError("SMTP caído")

    monkeypatch.setattr(correo, "enviar_email", _explota)
    monkeypatch.setattr(db_module, "SessionLocal", lambda: db)

    antes = db.query(ErrorRegistrado).count()
    enviar_uno(MailPendiente(
        to="a@test.local", subject="X", body="Y",
        clave_evento="comunicado_publicado",
    ))
    registrados = db.query(ErrorRegistrado).all()
    assert len(registrados) == antes + 1
    assert registrados[-1].ruta == "notificaciones/comunicado_publicado"


def test_encolar_sin_background_tasks_envia_en_linea(capsys):
    encolar(None, [MailPendiente(
        to="b@test.local", subject="Inline", body="Z",
        clave_evento="comunicado_publicado",
    )])
    assert "b@test.local" in capsys.readouterr().out


def test_encolar_con_background_tasks_agrega_una_tarea_por_mail():
    from fastapi import BackgroundTasks

    tareas = BackgroundTasks()
    encolar(tareas, [
        MailPendiente(to="a@x", subject="1", body="c", clave_evento="comunicado_publicado"),
        MailPendiente(to="b@x", subject="2", body="c", clave_evento="comunicado_publicado"),
    ])
    assert len(tareas.tasks) == 2


def test_encolar_lista_vacia_no_agrega_tareas():
    from fastapi import BackgroundTasks

    tareas = BackgroundTasks()
    encolar(tareas, [])
    assert len(tareas.tasks) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_correo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.notificaciones.correo'`.

- [ ] **Step 3: Escribir `backend/notificaciones/correo.py`**

```python
"""Envío de correo diferido: sale después de que la respuesta ya se fue.

Antes el mail se mandaba dentro de la operación. Un comunicado a cuarenta
departamentos eran cuarenta handshakes SMTP con el request abierto y el
usuario mirando una pantalla trabada.

El payload viaja completo (to/subject/body ya armados) porque la tarea de
fondo corre con la sesión de request ya cerrada: no puede tocar la DB para
resolver nada. La única DB que abre es una propia, y sólo para registrar un
error si el envío falla.
"""
import logging
from dataclasses import dataclass

from fastapi import BackgroundTasks

from .. import errores
from ..mail_service import enviar_email

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MailPendiente:
    to: str
    subject: str
    body: str
    clave_evento: str


def enviar_uno(mail: MailPendiente) -> None:
    """Manda un mail. Nunca levanta: es el contrato con BackgroundTasks.

    Una excepción acá no tendría a quién propagar —la respuesta ya salió— y
    en algunos servidores tumba el worker. Se registra y se sigue.
    """
    try:
        enviar_email(
            to=mail.to, subject=mail.subject, body=mail.body, attachments=[],
        )
    except Exception as exc:  # noqa: BLE001 — ver docstring
        _registrar(exc, mail)


def _registrar(exc: Exception, mail: MailPendiente) -> None:
    # Import local: `database` importa modelos, y a nivel de módulo esto
    # cierra un ciclo con `backend.notificaciones`.
    from ..database import SessionLocal

    db = None
    try:
        db = SessionLocal()
        errores.registrar(
            exc,
            ruta=f"notificaciones/{mail.clave_evento}",
            metodo="EMAIL",
            usuario_id=None,
            rol=None,
            consorcio_id=None,
            db=db,
        )
    except Exception as propio:  # noqa: BLE001 — nunca tapar el original
        logger.error(
            "No se pudo registrar el fallo de envío a %s: %s", mail.to, propio,
        )
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:  # noqa: BLE001 — la sesión ya puede estar rota
                pass


def encolar(tareas: BackgroundTasks | None, mails: list[MailPendiente]) -> None:
    """Encola los mails. Sin `tareas` (tests, scripts) envía en línea."""
    for mail in mails:
        if tareas is None:
            enviar_uno(mail)
        else:
            tareas.add_task(enviar_uno, mail)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_correo.py -v`
Expected: PASS, los seis.

- [ ] **Step 5: Commit**

```bash
git add backend/notificaciones/correo.py tests/test_notificaciones_correo.py
git commit -m "feat: envio de correo diferido a BackgroundTasks"
```

---

### Task 6: El emisor, y mudanza de los cuatro eventos existentes

**Files:**
- Create: `backend/notificaciones/emisor.py`
- Modify: `backend/notificaciones/__init__.py`
- Delete: `backend/notificaciones/legacy.py`
- Modify: `backend/routers/peticiones.py:9,142`
- Modify: `backend/routers/trabajos.py:19,79,201`
- Modify: `backend/routers/gastos.py:320-344`
- Modify: `backend/routers/amenities.py:300-305`
- Modify: `backend/routers/reservas.py:137-141`
- Modify: `tests/test_notificaciones.py` (los tres tests que llaman helpers viejos)

**Interfaces:**
- Consumes: `evento` de `catalogo.py`, `resolver_destinatarios` de `destinatarios.py`, `email_activo_para` de `preferencias.py`, `MailPendiente`/`encolar` de `correo.py`.
- Produces:
  - `emitir(db, clave, *, consorcio_id, contexto, actor_usuario_id, departamento_id=None, entidad_id=None, tareas=None) -> None`
  - `resolver_pendiente(db, *, consorcio_id, entidad_tipo, entidad_id) -> int` (devuelve cuántas apagó)

- [ ] **Step 1: Write the failing test**

Crear `tests/test_notificaciones_emisor.py`:

```python
"""El emisor: destinatarios, filtro de actor, pendientes y canal."""
from backend.models import Notificacion, Usuario
from backend.notificaciones import emitir, resolver_pendiente
from backend.notificaciones.preferencias import guardar_preferencia
from backend.notificaciones.catalogo import evento


def _ctx_comunicado():
    return {"titulo": "Corte de agua", "cuerpo": "Mañana de 9 a 13."}


def test_emitir_crea_una_notificacion_por_destinatario(db):
    emitir(
        db, "comunicado_publicado",
        consorcio_id=1, contexto=_ctx_comunicado(),
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()
    ns = db.query(Notificacion).filter_by(tipo="comunicado_publicado").all()
    assert [n.usuario_id for n in ns] == [2]
    assert ns[0].mensaje == "Nuevo comunicado: Corte de agua"
    assert ns[0].link == "/comunicados"


def test_emitir_excluye_al_actor(db):
    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-1A", "titulo": "Filtración"},
        actor_usuario_id=1, entidad_id=10,
    )
    db.commit()
    ns = db.query(Notificacion).filter_by(tipo="peticion_nueva").all()
    assert ns == []  # el único admin del consorcio es el actor


def test_emitir_guarda_la_entidad_si_el_evento_es_pendiente(db):
    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-1A", "titulo": "Filtración"},
        actor_usuario_id=2, entidad_id=10,
    )
    db.commit()
    n = db.query(Notificacion).filter_by(tipo="peticion_nueva").one()
    assert n.entidad_tipo == "peticion"
    assert n.entidad_id == 10


def test_emitir_evento_informativo_no_guarda_entidad(db):
    emitir(
        db, "comunicado_publicado",
        consorcio_id=1, contexto=_ctx_comunicado(),
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()
    n = db.query(Notificacion).filter_by(tipo="comunicado_publicado").one()
    assert n.entidad_tipo is None
    assert n.entidad_id is None


def test_evento_solo_mail_no_crea_campanita(db, capsys):
    emitir(
        db, "reserva_confirmada",
        consorcio_id=1,
        contexto={"amenity": "SUM", "fecha": "2026-09-01 14:00", "monto": None},
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()
    assert db.query(Notificacion).filter_by(tipo="reserva_confirmada").count() == 0
    assert "a@test.local" in capsys.readouterr().out


def test_preferencia_apagada_no_manda_mail_pero_si_campanita(db, capsys):
    guardar_preferencia(db, 2, evento("comunicado_publicado"), False)
    db.flush()
    capsys.readouterr()  # descartar salida previa

    emitir(
        db, "comunicado_publicado",
        consorcio_id=1, contexto=_ctx_comunicado(),
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()

    assert db.query(Notificacion).filter_by(tipo="comunicado_publicado").count() == 1
    assert "Nuevo comunicado" not in capsys.readouterr().out


def test_emitir_no_commitea(db):
    emitir(
        db, "comunicado_publicado",
        consorcio_id=1, contexto=_ctx_comunicado(),
        actor_usuario_id=1, departamento_id=1,
    )
    db.rollback()
    assert db.query(Notificacion).filter_by(tipo="comunicado_publicado").count() == 0


def test_resolver_pendiente_apaga_todas_las_copias(db):
    otro_admin = Usuario(
        id=50, email="admin2@test.local", password_hash="x",
        rol=db.get(Usuario, 1).rol, administracion_id=1,
    )
    db.add(otro_admin)
    db.flush()

    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-1A", "titulo": "Filtración"},
        actor_usuario_id=2, entidad_id=10,
    )
    db.commit()
    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 2

    apagadas = resolver_pendiente(
        db, consorcio_id=1, entidad_tipo="peticion", entidad_id=10,
    )
    db.commit()
    assert apagadas == 2
    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 0


def test_resolver_pendiente_no_toca_otras_entidades(db):
    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-1A", "titulo": "A"},
        actor_usuario_id=2, entidad_id=10,
    )
    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-2B", "titulo": "B"},
        actor_usuario_id=3, entidad_id=11,
    )
    db.commit()

    resolver_pendiente(db, consorcio_id=1, entidad_tipo="peticion", entidad_id=10)
    db.commit()
    restantes = db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).all()
    assert [n.entidad_id for n in restantes] == [11]


def test_resolver_pendiente_no_cruza_consorcios(db, dos_consorcios):
    emitir(
        db, "peticion_nueva",
        consorcio_id=1, contexto={"codigo_depto": "UF-1A", "titulo": "A"},
        actor_usuario_id=2, entidad_id=10,
    )
    db.commit()
    apagadas = resolver_pendiente(
        db, consorcio_id=2, entidad_tipo="peticion", entidad_id=10,
    )
    assert apagadas == 0


def test_clave_desconocida_explota(db):
    import pytest

    with pytest.raises(KeyError):
        emitir(
            db, "no_existe",
            consorcio_id=1, contexto={}, actor_usuario_id=1,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_emisor.py -v`
Expected: FAIL — `ImportError: cannot import name 'emitir' from 'backend.notificaciones'`.

- [ ] **Step 3: Escribir `backend/notificaciones/emisor.py`**

```python
"""El emisor: única puerta de entrada para generar notificaciones.

No sabe nada de eventos concretos. Lee el catálogo, resuelve destinatarios,
descarta al actor, persiste la campanita y encola el mail. Agregar un evento
no toca este archivo.
"""
from fastapi import BackgroundTasks
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Notificacion
from .catalogo import evento as _evento
from .correo import MailPendiente, encolar
from .destinatarios import resolver_destinatarios
from .preferencias import email_activo_para


def emitir(
    db: Session,
    clave: str,
    *,
    consorcio_id: int,
    contexto: dict,
    actor_usuario_id: int | None,
    departamento_id: int | None = None,
    entidad_id: int | None = None,
    tareas: BackgroundTasks | None = None,
) -> None:
    """Emite un evento del catálogo. NO commitea — el caller lo hace.

    Va dentro de la transacción de la operación que lo causó: si esa
    operación falla, no queda un aviso fantasma.
    """
    ev = _evento(clave)

    destinatarios = resolver_destinatarios(
        db, ev.audiencia,
        consorcio_id=consorcio_id,
        departamento_id=departamento_id,
        excluir_usuario_id=actor_usuario_id,
    )
    if not destinatarios:
        return

    mails: list[MailPendiente] = []

    for u in destinatarios:
        if ev.crea_campanita:
            db.add(Notificacion(
                consorcio_id=consorcio_id,
                usuario_id=u.id,
                tipo=ev.clave,
                mensaje=ev.mensaje(contexto),
                link=ev.link(contexto),
                entidad_tipo=ev.entidad_tipo,
                entidad_id=entidad_id if ev.entidad_tipo else None,
            ))

        if u.email and email_activo_para(db, u.id, ev):
            # Payload completo ACÁ: la tarea de fondo corre con la sesión
            # cerrada y no puede resolver nada contra la DB.
            mails.append(MailPendiente(
                to=u.email,
                subject=ev.asunto(contexto),
                body=ev.cuerpo(contexto),
                clave_evento=ev.clave,
            ))

    encolar(tareas, mails)


def resolver_pendiente(
    db: Session,
    *,
    consorcio_id: int,
    entidad_tipo: str,
    entidad_id: int,
) -> int:
    """Apaga el pendiente para TODOS sus destinatarios. Devuelve cuántos apagó.

    Que Ana apruebe el comprobante le apaga el puntito a Juan también: el
    puntito significa "te queda algo por hacer", no "hay novedades". Juan
    puede no llegar a verlo nunca; el hecho igual queda en su historial, ya
    marcado como leído.

    NO commitea — el caller lo hace.
    """
    ids = list(db.scalars(
        select(Notificacion.id).where(
            Notificacion.consorcio_id == consorcio_id,
            Notificacion.entidad_tipo == entidad_tipo,
            Notificacion.entidad_id == entidad_id,
            Notificacion.leida == False,  # noqa: E712
        )
    ).all())
    if not ids:
        return 0

    db.execute(
        update(Notificacion)
        .where(Notificacion.id.in_(ids))
        .values(leida=True)
    )
    return len(ids)
```

- [ ] **Step 4: Reemplazar `backend/notificaciones/__init__.py`**

```python
"""Sistema de notificaciones.

`emitir` y `resolver_pendiente` son la única API pública. Todo lo demás
—catálogo, destinatarios, preferencias, correo— es interno del paquete.
"""
from .emisor import emitir, resolver_pendiente

__all__ = ["emitir", "resolver_pendiente"]
```

Y borrar el módulo viejo:

```bash
git rm backend/notificaciones/legacy.py
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_emisor.py -v`
Expected: PASS, los once.

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: FAIL en los routers y en `tests/test_notificaciones.py` — los helpers ya no existen. Es lo esperado; los pasos siguientes los migran.

- [ ] **Step 6: Migrar `peticiones.py`**

En `backend/routers/peticiones.py`, reemplazar el import de la línea 9:

```python
from ..notificaciones import emitir
```

Agregar `BackgroundTasks` al import de fastapi de la línea 1:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
```

En `actualizar_peticion`, agregar el parámetro `tareas: BackgroundTasks` después de `payload`, y reemplazar la llamada de la línea 142 (`notificar_cambio_estado_peticion(...)`) por:

```python
    # El rechazo saca la petición de "abierta": el pendiente del admin ya no
    # es trabajo por hacer.
    resolver_pendiente(
        db, consorcio_id=cid, entidad_tipo="peticion", entidad_id=peticion.id,
    )
    emitir(
        db, PETICION_ESTADO_CAMBIADO,
        consorcio_id=cid,
        contexto={
            "titulo": peticion.titulo,
            "estado": peticion.estado.value,
            "peticion_id": peticion.id,
        },
        actor_usuario_id=_user.id,
        departamento_id=peticion.departamento_id,
        tareas=tareas,
    )
```

Cambiar `_user` a un nombre usable: la firma pasa a `user: CurrentUser = Depends(require_roles(*_ADMIN_O_REPRESENTANTE))` y la llamada usa `user.id`. Actualizar el import:

```python
from ..notificaciones import emitir, resolver_pendiente
from ..notificaciones.catalogo import PETICION_ESTADO_CAMBIADO
```

- [ ] **Step 7: Migrar `trabajos.py`**

Reemplazar el import de la línea 19 por:

```python
from ..notificaciones import emitir, resolver_pendiente
from ..notificaciones.catalogo import PETICION_ESTADO_CAMBIADO
```

Agregar `BackgroundTasks` al import de fastapi.

En `crear_trabajo`, agregar `tareas: BackgroundTasks` a la firma y reemplazar el bloque de la línea 79:

```python
    if peticion_a_notificar is not None:
        resolver_pendiente(
            db, consorcio_id=cid, entidad_tipo="peticion",
            entidad_id=peticion_a_notificar.id,
        )
        emitir(
            db, PETICION_ESTADO_CAMBIADO,
            consorcio_id=cid,
            contexto={
                "titulo": peticion_a_notificar.titulo,
                "estado": peticion_a_notificar.estado.value,
                "peticion_id": peticion_a_notificar.id,
            },
            actor_usuario_id=user.id,
            departamento_id=peticion_a_notificar.departamento_id,
            tareas=tareas,
        )
```

Renombrar `_user` a `user` en la firma de `crear_trabajo`.

En `cancelar_trabajo`, agregar `tareas: BackgroundTasks`, renombrar `_user` a `user`, y reemplazar la llamada de la línea 201:

```python
            emitir(
                db, PETICION_ESTADO_CAMBIADO,
                consorcio_id=cid,
                contexto={
                    "titulo": peticion.titulo,
                    "estado": peticion.estado.value,
                    "peticion_id": peticion.id,
                },
                actor_usuario_id=user.id,
                departamento_id=peticion.departamento_id,
                tareas=tareas,
            )
```

(No hace falta `resolver_pendiente` acá: la petición ya había salido de `abierta` al convertirse en trabajo.)

- [ ] **Step 8: Migrar `gastos.py`**

En `backend/routers/gastos.py`, reemplazar el bloque de las líneas 320-344 (desde `from ..notificaciones import crear_notificacion` hasta el cierre del `for u in usuarios`) por:

```python
        from ..notificaciones import emitir
        from ..notificaciones.catalogo import TRABAJO_COMPLETADO

        t = db.get(Trabajo, payload.trabajo_id)
        if t is None or t.consorcio_id != cid:
            raise HTTPException(404, f"Trabajo {payload.trabajo_id} no encontrado.")
        t.gasto_id = gasto.id
        t.estado = EstadoTrabajo.finalizado

        if t.peticion_id:
            pet = db.get(Peticion, t.peticion_id)
            if pet:
                emitir(
                    db, TRABAJO_COMPLETADO,
                    consorcio_id=cid,
                    contexto={"titulo": pet.titulo},
                    actor_usuario_id=user.id,
                    departamento_id=pet.departamento_id,
                    tareas=tareas,
                )
```

Agregar `tareas: BackgroundTasks` a la firma del endpoint que contiene ese bloque, `BackgroundTasks` al import de fastapi, y verificar que el endpoint tenga el usuario disponible como `user` (si está como `_user`, renombrarlo).

- [ ] **Step 9: Migrar `amenities.py`**

En `backend/routers/amenities.py`, reemplazar el bloque de las líneas 300-305 (que hoy corre **después** del `db.commit()`) moviéndolo **antes** del commit, justo después de asignar `reserva.movimiento_cuenta_id`:

```python
    from ..notificaciones import emitir
    from ..notificaciones.catalogo import RESERVA_CONFIRMADA

    monto = (
        amenity.precio_reserva
        if (user.rol == Rol.departamento and amenity.precio_reserva is not None)
        else None
    )
    ctx_reserva = {
        "amenity": amenity.nombre,
        "fecha": inicio_naive.strftime("%Y-%m-%d %H:%M"),
        "monto": monto,
    }
    if user.rol == Rol.departamento:
        emitir(
            db, RESERVA_CONFIRMADA,
            consorcio_id=cid, contexto=ctx_reserva,
            actor_usuario_id=None,
            departamento_id=user.departamento_id,
            tareas=tareas,
        )

    db.commit()
    db.refresh(reserva)
    return reserva
```

Nota sobre `actor_usuario_id=None`: este evento es la confirmación al propio reservante. Es el único caso donde el actor **sí** debe recibirlo, porque el mail es el comprobante de su propia acción.

Agregar `tareas: BackgroundTasks` a la firma del endpoint y `BackgroundTasks` al import de fastapi. Borrar el bloque viejo que quedó después del commit.

- [ ] **Step 10: Migrar `reservas.py`**

En `backend/routers/reservas.py`, reemplazar el bloque de las líneas 137-141 por:

```python
    if es_admin and not es_dueno:
        from ..notificaciones import emitir
        from ..notificaciones.catalogo import RESERVA_CANCELADA_POR_ADMIN

        amenity_n = db.get(Amenity, reserva.amenity_id)
        dueno = db.get(Usuario, reserva.usuario_id)
        emitir(
            db, RESERVA_CANCELADA_POR_ADMIN,
            consorcio_id=cid,
            contexto={
                "amenity": amenity_n.nombre,
                "fecha": reserva.inicio.strftime("%Y-%m-%d %H:%M"),
                "monto_reversado": monto_reversado,
            },
            actor_usuario_id=user.id,
            departamento_id=dueno.departamento_id if dueno else None,
            tareas=tareas,
        )
```

Agregar `tareas: BackgroundTasks` a la firma, `BackgroundTasks` al import de fastapi, y `Usuario` al import de `..models` si falta.

- [ ] **Step 11: Reescribir los tres tests que usaban helpers viejos**

En `tests/test_notificaciones.py`, reemplazar `test_crear_notificacion_persiste`, `test_notificar_abierta_a_convertida_crea_notif` y `test_notificar_sin_cambio_estado_no_hace_nada` por:

```python
def test_emitir_persiste_la_campanita(db):
    from backend.notificaciones import emitir

    emitir(
        db, "peticion_estado_cambiado",
        consorcio_id=1,
        contexto={"titulo": "Test", "estado": "rechazada", "peticion_id": 10},
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()
    n = db.query(Notificacion).filter_by(tipo="peticion_estado_cambiado").one()
    assert n.usuario_id == 2
    assert n.leida is False
    assert n.link == "/peticiones"


def test_emitir_conversion_menciona_el_estado_crudo(db):
    from backend.notificaciones import emitir

    emitir(
        db, "peticion_estado_cambiado",
        consorcio_id=1,
        contexto={
            "titulo": "Test peti",
            "estado": "convertida_en_trabajo",
            "peticion_id": 10,
        },
        actor_usuario_id=1, departamento_id=1,
    )
    db.commit()
    n = db.query(Notificacion).filter_by(tipo="peticion_estado_cambiado").one()
    assert "convertida_en_trabajo" in n.mensaje
```

Ajustar el import del tope del archivo: `from backend.models import Notificacion, Rol, Usuario` (sacar `EstadoPeticion` y `Peticion` si quedan sin uso, y sacar la línea `from backend.notificaciones import crear_notificacion, notificar_cambio_estado_peticion`).

- [ ] **Step 12: Verificar que no queda ninguna referencia a los helpers viejos**

Run: `grep -rn "crear_notificacion\|notificar_cambio_estado_peticion\|notificar_reserva_creada\|notificar_reserva_cancelada_por_admin" backend tests`
Expected: sin resultados.

- [ ] **Step 13: Run the full suite**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: todo verde. En particular, **sin tocar una línea**:
- `tests/test_peticiones.py::test_patch_cambio_estado_dispara_notificacion`
- `tests/test_trabajos.py` (el que filtra por `convertida_en_trabajo`)
- `tests/test_reservas.py::test_depto_cancela_su_reserva_no_genera_notificacion`

Si alguno falla, el catálogo o la migración cambiaron comportamiento: arreglar el catálogo, no el test.

- [ ] **Step 14: Commit**

```bash
git add backend/notificaciones backend/routers tests/test_notificaciones.py tests/test_notificaciones_emisor.py
git commit -m "refactor: los cuatro eventos existentes pasan por el emisor unico"
```

---

### Task 7: Los cuatro eventos nuevos al departamento

**Files:**
- Modify: `backend/routers/comunicados.py:40-62`
- Modify: `backend/routers/periodos.py:124-200`
- Modify: `backend/routers/comprobantes.py:164-250`
- Test: `tests/test_comunicados.py`, `tests/test_cierre.py`, `tests/test_comprobantes.py`

**Interfaces:**
- Consumes: `emitir` del Task 6; las claves `COMUNICADO_PUBLICADO`, `EXPENSA_EMITIDA`, `COMPROBANTE_APROBADO`, `COMPROBANTE_RECHAZADO`.
- Produces: nada nuevo.

- [ ] **Step 1: Write the failing tests**

Agregar a `tests/test_comunicados.py`:

```python
def test_publicar_comunicado_notifica_a_los_deptos(client, headers_admin, db):
    from backend.models import Notificacion

    r = client.post(
        "/comunicados",
        json={"titulo": "Corte de agua", "cuerpo": "Mañana de 9 a 13."},
        headers=headers_admin,
    )
    assert r.status_code == 201

    ns = db.query(Notificacion).filter_by(tipo="comunicado_publicado").all()
    assert sorted(n.usuario_id for n in ns) == [2, 3]
    assert all("Corte de agua" in n.mensaje for n in ns)


def test_publicar_comunicado_no_notifica_al_admin(client, headers_admin, db):
    from backend.models import Notificacion

    client.post(
        "/comunicados",
        json={"titulo": "X", "cuerpo": "Y"},
        headers=headers_admin,
    )
    ns = db.query(Notificacion).filter_by(tipo="comunicado_publicado").all()
    assert 1 not in [n.usuario_id for n in ns]
```

Agregar a `tests/test_comprobantes.py`:

```python
def test_aprobar_comprobante_notifica_al_depto(client, headers_admin, headers_depto_a, db):
    from backend.models import Notificacion

    with open(__file__, "rb") as f:
        r = client.post(
            "/comprobantes",
            data={"fecha_pago": "2026-08-01", "monto": "1000"},
            files={"archivo": ("c.pdf", f.read(), "application/pdf")},
            headers=headers_depto_a,
        )
    assert r.status_code == 201
    cid_comp = r.json()["id"]

    r2 = client.patch(
        f"/comprobantes/{cid_comp}",
        json={"estado": "aprobado"},
        headers=headers_admin,
    )
    assert r2.status_code == 200

    ns = db.query(Notificacion).filter_by(tipo="comprobante_aprobado").all()
    assert [n.usuario_id for n in ns] == [2]


def test_rechazar_comprobante_incluye_el_motivo(client, headers_admin, headers_depto_a, db):
    from backend.models import Notificacion

    with open(__file__, "rb") as f:
        r = client.post(
            "/comprobantes",
            data={"fecha_pago": "2026-08-01", "monto": "1000"},
            files={"archivo": ("c.pdf", f.read(), "application/pdf")},
            headers=headers_depto_a,
        )
    cid_comp = r.json()["id"]

    client.patch(
        f"/comprobantes/{cid_comp}",
        json={"estado": "rechazado", "motivo_rechazo": "El monto no coincide"},
        headers=headers_admin,
    )

    n = db.query(Notificacion).filter_by(tipo="comprobante_rechazado").one()
    assert "El monto no coincide" in n.mensaje
```

Agregar a `tests/test_periodos.py` (el armado es el mismo que usa
`tests/test_envio_pdfs.py::test_admin_envia_pdfs_periodo_cerrado`; `test_cierre.py`
no sirve porque prueba el cálculo contra `db_empty`, sin pasar por la API):

```python
def test_cerrar_periodo_notifica_la_expensa_a_cada_depto(client, headers_admin, db_session):
    from datetime import date

    from backend.models import (
        CoeficienteDepartamento, FormaPago, Gasto, Notificacion, Rubro,
    )

    db_session.add(CoeficienteDepartamento(
        consorcio_id=1, departamento_id=1, clase_prorrateo_id=500, porcentaje=50,
    ))
    db_session.add(CoeficienteDepartamento(
        consorcio_id=1, departamento_id=2, clase_prorrateo_id=500, porcentaje=50,
    ))
    db_session.add(Gasto(
        consorcio_id=1, periodo="2026-06", monto=1000, rubro=Rubro.servicios_publicos,
        clase_prorrateo_id=500, departamento_id=None, proveedor_id=600,
        concepto="Luz", forma_pago=FormaPago.efectivo, caja_id=900,
        fecha_pago=date(2026, 6, 10),
    ))
    db_session.commit()

    r = client.post("/periodos/2026-06/cerrar", json={}, headers=headers_admin)
    assert r.status_code == 201

    ns = db_session.query(Notificacion).filter_by(tipo="expensa_emitida").all()
    assert sorted(n.usuario_id for n in ns) == [2, 3]
    assert all("2026-06" in n.mensaje for n in ns)
```

Y un test de extremo a extremo del fallo de correo, en `tests/test_comunicados.py`
— el unitario del Task 5 prueba `enviar_uno`; este prueba la promesa completa:

```python
def test_un_smtp_caido_no_rompe_la_publicacion(client, headers_admin, db, monkeypatch):
    """La operación devuelve 2xx, la campanita queda, y el error se registra."""
    from backend.models import ErrorRegistrado, Notificacion
    from backend.notificaciones import correo

    def _explota(**kwargs):
        raise RuntimeError("SMTP caído")

    monkeypatch.setattr(correo, "enviar_email", _explota)

    r = client.post(
        "/comunicados",
        json={"titulo": "Corte", "cuerpo": "X"},
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert db.query(Notificacion).filter_by(tipo="comunicado_publicado").count() == 2
    assert db.query(ErrorRegistrado).count() >= 1
```

(`TestClient` corre las `BackgroundTasks` antes de devolver la respuesta al test,
así que el registro del error ya está hecho cuando se hacen las aserciones.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comunicados.py tests/test_comprobantes.py tests/test_cierre.py -v -k "notifica or motivo"`
Expected: FAIL — las queries devuelven listas vacías.

- [ ] **Step 3: Implementar en `comunicados.py`**

Agregar `BackgroundTasks` al import de fastapi. En `crear_comunicado`, agregar `tareas: BackgroundTasks` a la firma y, entre `db.add(comunicado)` y `db.commit()`:

```python
    db.flush()

    # Un comunicado le habla a todos los departamentos del consorcio, así que
    # hay que emitir uno por departamento: la audiencia del catálogo apunta a
    # un departamento concreto, no a "todos".
    from ..notificaciones import emitir
    from ..notificaciones.catalogo import COMUNICADO_PUBLICADO

    deptos = db.scalars(
        select(Departamento.id).where(Departamento.consorcio_id == cid)
    ).all()
    for depto_id in deptos:
        emitir(
            db, COMUNICADO_PUBLICADO,
            consorcio_id=cid,
            contexto={"titulo": comunicado.titulo, "cuerpo": comunicado.cuerpo},
            actor_usuario_id=user.id,
            departamento_id=depto_id,
            tareas=tareas,
        )
```

Agregar `Departamento` al import de `..models`.

- [ ] **Step 4: Implementar en `comprobantes.py`**

Agregar `BackgroundTasks` al import de fastapi. En `actualizar_comprobante`, renombrar `_user` a `user`, agregar `tareas: BackgroundTasks` a la firma, y antes del `db.commit()` final:

```python
    from ..notificaciones import emitir, resolver_pendiente
    from ..notificaciones.catalogo import COMPROBANTE_APROBADO, COMPROBANTE_RECHAZADO

    # El comprobante deja de estar esperando verificación: el pendiente del
    # admin se apaga para todos, lo haya resuelto quien lo haya resuelto.
    resolver_pendiente(
        db, consorcio_id=cid, entidad_tipo="comprobante", entidad_id=comprobante.id,
    )

    aprobado = comprobante.estado == EstadoComprobante.aprobado
    emitir(
        db,
        COMPROBANTE_APROBADO if aprobado else COMPROBANTE_RECHAZADO,
        consorcio_id=cid,
        contexto={
            "monto": comprobante.monto,
            "motivo": comprobante.motivo_rechazo,
        },
        actor_usuario_id=user.id,
        departamento_id=comprobante.departamento_id,
        tareas=tareas,
    )
```

- [ ] **Step 5: Implementar en `periodos.py`**

Agregar `BackgroundTasks` al import de fastapi. En `cerrar_periodo`, agregar `tareas: BackgroundTasks` a la firma y, después del bucle que crea las `Expensa` y antes del `db.commit()` final:

```python
    from ..notificaciones import emitir
    from ..notificaciones.catalogo import EXPENSA_EMITIDA

    for exp in preview.expensas:
        emitir(
            db, EXPENSA_EMITIDA,
            consorcio_id=cid,
            contexto={
                "periodo": periodo,
                "monto": exp.monto_primer_vencimiento,
                "vencimiento": preview.fecha_primer_vencimiento.isoformat(),
            },
            actor_usuario_id=user.id,
            departamento_id=exp.departamento_id,
            tareas=tareas,
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comunicados.py tests/test_comprobantes.py tests/test_cierre.py -v`
Expected: PASS.

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: todo verde.

- [ ] **Step 7: Commit**

```bash
git add backend/routers tests
git commit -m "feat: avisar al depto comunicado, expensa emitida y comprobante verificado"
```

---

### Task 8: Los cuatro eventos nuevos a la administración

**Files:**
- Modify: `backend/routers/peticiones.py` (`crear_peticion`, `eliminar_peticion`)
- Modify: `backend/routers/comprobantes.py` (`presentar_comprobante`)
- Modify: `backend/routers/amenities.py` (creación de reserva)
- Test: `tests/test_peticiones.py`, `tests/test_comprobantes.py`, `tests/test_reservas.py`

**Interfaces:**
- Consumes: `emitir`, `resolver_pendiente`; claves `PETICION_NUEVA`, `COMPROBANTE_PRESENTADO`, `PETICION_BORRADA_POR_DEPTO`, `RESERVA_NUEVA_DE_DEPTO`.
- Produces: nada nuevo.

- [ ] **Step 1: Write the failing tests**

Agregar a `tests/test_peticiones.py`:

```python
def test_crear_peticion_avisa_al_admin_como_pendiente(client, headers_depto_a, db):
    from backend.models import Notificacion

    r = client.post(
        "/peticiones",
        json={"titulo": "Filtración", "descripcion": "Cocina"},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    n = db.query(Notificacion).filter_by(tipo="peticion_nueva").one()
    assert n.usuario_id == 1
    assert n.entidad_tipo == "peticion"
    assert n.entidad_id == pid
    assert "UF-1A" in n.mensaje


def test_rechazar_peticion_apaga_el_pendiente_del_admin(client, headers_depto_a, headers_admin, db):
    from backend.models import Notificacion

    r = client.post(
        "/peticiones",
        json={"titulo": "Filtración", "descripcion": "Cocina"},
        headers=headers_depto_a,
    )
    pid = r.json()["id"]
    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 1

    client.patch(
        f"/peticiones/{pid}",
        json={"estado": "rechazada", "motivo_rechazo": "No corresponde"},
        headers=headers_admin,
    )
    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 0


def test_convertir_en_trabajo_apaga_el_pendiente(client, headers_depto_a, headers_admin, db):
    from backend.models import Notificacion

    r = client.post(
        "/peticiones",
        json={"titulo": "Filtración", "descripcion": "Cocina"},
        headers=headers_depto_a,
    )
    pid = r.json()["id"]

    r2 = client.post(
        "/trabajos",
        json={"peticion_id": pid, "descripcion": "Arreglar caño"},
        headers=headers_admin,
    )
    assert r2.status_code == 201
    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 0


def test_depto_borra_su_peticion_avisa_y_apaga_el_pendiente(client, headers_depto_a, db):
    from backend.models import Notificacion

    r = client.post(
        "/peticiones",
        json={"titulo": "Filtración", "descripcion": "Cocina"},
        headers=headers_depto_a,
    )
    pid = r.json()["id"]

    r2 = client.delete(f"/peticiones/{pid}", headers=headers_depto_a)
    assert r2.status_code == 204

    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 0
    n = db.query(Notificacion).filter_by(tipo="peticion_borrada_por_depto").one()
    assert n.usuario_id == 1
    assert "Filtración" in n.mensaje


def test_admin_borra_una_peticion_apaga_el_pendiente_sin_avisar(client, headers_depto_a, headers_admin, db):
    from backend.models import Notificacion

    r = client.post(
        "/peticiones",
        json={"titulo": "Filtración", "descripcion": "Cocina"},
        headers=headers_depto_a,
    )
    pid = r.json()["id"]

    client.delete(f"/peticiones/{pid}", headers=headers_admin)

    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 0
    assert db.query(Notificacion).filter_by(tipo="peticion_borrada_por_depto").count() == 0
```

Agregar a `tests/test_comprobantes.py`:

```python
def test_presentar_comprobante_avisa_al_admin_como_pendiente(client, headers_depto_a, db):
    from backend.models import Notificacion

    with open(__file__, "rb") as f:
        r = client.post(
            "/comprobantes",
            data={"fecha_pago": "2026-08-01", "monto": "1000"},
            files={"archivo": ("c.pdf", f.read(), "application/pdf")},
            headers=headers_depto_a,
        )
    assert r.status_code == 201

    n = db.query(Notificacion).filter_by(tipo="comprobante_presentado").one()
    assert n.usuario_id == 1
    assert n.entidad_tipo == "comprobante"
    assert n.entidad_id == r.json()["id"]
    assert "UF-1A" in n.mensaje
```

Agregar a `tests/test_reservas.py`:

```python
def test_reserva_de_depto_avisa_al_admin(client, headers_depto_a, db_session):
    from backend.models import Notificacion
    from tests.conftest import RESERVA_INICIO

    inicio = (RESERVA_INICIO.replace(hour=9)).isoformat()
    fin = (RESERVA_INICIO.replace(hour=11)).isoformat()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 201

    n = db_session.query(Notificacion).filter_by(tipo="reserva_nueva_de_depto").one()
    assert n.usuario_id == 1
    assert "Laundry" in n.mensaje


def test_reserva_del_admin_no_se_autoavisa(client, headers_admin, db_session):
    from backend.models import Notificacion
    from tests.conftest import RESERVA_INICIO

    inicio = (RESERVA_INICIO.replace(hour=19)).isoformat()
    fin = (RESERVA_INICIO.replace(hour=21)).isoformat()
    client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_admin,
    )
    assert db_session.query(Notificacion).filter_by(tipo="reserva_nueva_de_depto").count() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_peticiones.py tests/test_comprobantes.py tests/test_reservas.py -v -k "pendiente or avisa or borra or autoavisa"`
Expected: FAIL — `NoResultFound` / conteos en 1 donde se espera 0.

- [ ] **Step 3: Implementar `peticion_nueva` en `crear_peticion`**

En `backend/routers/peticiones.py`, en `crear_peticion`, agregar `tareas: BackgroundTasks` a la firma y reemplazar el bloque de commit por:

```python
    db.add(peticion)
    db.flush()

    depto = db.get(Departamento, user.departamento_id)
    emitir(
        db, PETICION_NUEVA,
        consorcio_id=cid,
        contexto={
            "codigo_depto": depto.codigo if depto else "Un departamento",
            "titulo": peticion.titulo,
        },
        actor_usuario_id=user.id,
        entidad_id=peticion.id,
        tareas=tareas,
    )

    db.commit()
    db.refresh(peticion)
    return peticion
```

Agregar `Departamento` al import de `..models` y `PETICION_NUEVA` al import del catálogo.

- [ ] **Step 4: Implementar en `eliminar_peticion`**

En `backend/routers/peticiones.py`, en `eliminar_peticion`, agregar `tareas: BackgroundTasks` a la firma y reemplazar las dos ramas de borrado por:

```python
    if user.rol in (Rol.administracion, Rol.representante):
        # El pendiente apunta a esta petición y no puede quedar vivo señalando
        # algo que ya no existe. Va después de los chequeos de permiso, no
        # antes: así ninguna rama que termina en 403/409 lo toca.
        resolver_pendiente(
            db, consorcio_id=cid, entidad_tipo="peticion", entidad_id=peticion.id,
        )
        db.delete(peticion)
        db.commit()
        return

    if user.rol == Rol.departamento:
        if peticion.departamento_id != user.departamento_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No autorizado para eliminar esta petición.",
            )
        if peticion.estado != EstadoPeticion.abierta:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo podés eliminar peticiones en estado abierta.",
            )

        resolver_pendiente(
            db, consorcio_id=cid, entidad_tipo="peticion", entidad_id=peticion.id,
        )
        depto = db.get(Departamento, user.departamento_id)
        emitir(
            db, PETICION_BORRADA_POR_DEPTO,
            consorcio_id=cid,
            contexto={
                "codigo_depto": depto.codigo if depto else "Un departamento",
                "titulo": peticion.titulo,
            },
            actor_usuario_id=user.id,
            tareas=tareas,
        )
        db.delete(peticion)
        db.commit()
        return
```

El `resolver_pendiente` queda duplicado en las dos ramas a propósito: sacarlo
arriba lo pondría antes de los chequeos de permiso, y aunque el `raise` termina
descartando la transacción, depender de eso es frágil. Dos líneas iguales valen
menos que una sutileza.

Agregar `PETICION_BORRADA_POR_DEPTO` al import del catálogo.

- [ ] **Step 5: Implementar `comprobante_presentado`**

En `backend/routers/comprobantes.py`, en `presentar_comprobante`, agregar `tareas: BackgroundTasks` a la firma y reemplazar el commit por:

```python
    db.add(comprobante)
    db.flush()

    from ..notificaciones import emitir
    from ..notificaciones.catalogo import COMPROBANTE_PRESENTADO
    from ..models import Departamento

    depto = db.get(Departamento, user.departamento_id)
    emitir(
        db, COMPROBANTE_PRESENTADO,
        consorcio_id=cid,
        contexto={
            "codigo_depto": depto.codigo if depto else "Un departamento",
            "monto": comprobante.monto,
        },
        actor_usuario_id=user.id,
        entidad_id=comprobante.id,
        tareas=tareas,
    )

    db.commit()
    db.refresh(comprobante)
    return comprobante
```

- [ ] **Step 6: Implementar `reserva_nueva_de_depto`**

En `backend/routers/amenities.py`, en el bloque que el Task 6 dejó antes del `db.commit()`, agregar dentro del mismo `if user.rol == Rol.departamento:`:

```python
        depto = db.get(Departamento, user.departamento_id)
        emitir(
            db, RESERVA_NUEVA_DE_DEPTO,
            consorcio_id=cid,
            contexto={
                "codigo_depto": depto.codigo if depto else "Un departamento",
                "amenity": amenity.nombre,
                "fecha": inicio_naive.strftime("%Y-%m-%d %H:%M"),
            },
            actor_usuario_id=user.id,
            tareas=tareas,
        )
```

Agregar `Departamento` al import de `..models` y `RESERVA_NUEVA_DE_DEPTO` al import del catálogo.

- [ ] **Step 7: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_peticiones.py tests/test_comprobantes.py tests/test_reservas.py -v`
Expected: PASS, incluido `test_depto_cancela_su_reserva_no_genera_notificacion` sin modificar.

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: todo verde.

- [ ] **Step 8: Commit**

```bash
git add backend/routers tests
git commit -m "feat: bandeja de pendientes de la administracion"
```

---

### Task 9: Endpoints de listado, contador y marcado

**Files:**
- Modify: `openapi.yaml` (bloque `/notificaciones`)
- Modify: `backend/schemas.py:1191-1202`
- Modify: `backend/routers/notificaciones.py`
- Test: `tests/test_notificaciones.py`

**Interfaces:**
- Consumes: `get_consorcio_activo`.
- Produces: `NotificacionOut` con `tipo`; `NotificacionesCountOut` con `otros_consorcios`.

- [ ] **Step 1: Documentar en `openapi.yaml`**

En el bloque `/notificaciones`, agregar los parámetros `solo_no_leidas`, `q`, `offset` al `get` existente (junto a `limit`), y sumar `tipo` al schema `NotificacionOut` y `otros_consorcios` a `NotificacionesCountOut`.

- [ ] **Step 2: Write the failing test**

Agregar a `tests/test_notificaciones.py`:

```python
def test_listado_filtra_por_consorcio_activo(client, headers_admin, db, dos_consorcios):
    from backend.models import Notificacion

    db.add(Notificacion(consorcio_id=1, usuario_id=1, tipo="peticion_nueva", mensaje="del 1"))
    db.add(Notificacion(consorcio_id=2, usuario_id=1, tipo="peticion_nueva", mensaje="del 2"))
    db.commit()

    r = client.get("/notificaciones", headers=headers_admin)
    assert r.status_code == 200
    mensajes = [n["mensaje"] for n in r.json()]
    assert "del 1" in mensajes
    assert "del 2" not in mensajes


def test_listado_expone_el_tipo(client, headers_depto_a, db):
    from backend.models import Notificacion

    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="comunicado_publicado", mensaje="X"))
    db.commit()
    r = client.get("/notificaciones", headers=headers_depto_a)
    assert r.json()[0]["tipo"] == "comunicado_publicado"


def test_listado_solo_no_leidas(client, headers_depto_a, db):
    from backend.models import Notificacion

    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje="pendiente", leida=False))
    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje="vista", leida=True))
    db.commit()

    r = client.get("/notificaciones?solo_no_leidas=true", headers=headers_depto_a)
    assert [n["mensaje"] for n in r.json()] == ["pendiente"]


def test_listado_busca_por_texto_sin_distinguir_mayusculas(client, headers_depto_a, db):
    from backend.models import Notificacion

    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje="Corte de AGUA"))
    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje="Reunión"))
    db.commit()

    r = client.get("/notificaciones?q=agua", headers=headers_depto_a)
    assert [n["mensaje"] for n in r.json()] == ["Corte de AGUA"]


def test_listado_pagina_con_offset(client, headers_depto_a, db):
    from backend.models import Notificacion

    for i in range(5):
        db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje=f"n{i}"))
    db.commit()

    primera = client.get("/notificaciones?limit=2", headers=headers_depto_a).json()
    segunda = client.get("/notificaciones?limit=2&offset=2", headers=headers_depto_a).json()
    assert len(primera) == 2
    assert len(segunda) == 2
    assert {n["id"] for n in primera}.isdisjoint({n["id"] for n in segunda})


def test_contador_reporta_otros_consorcios(client, db, dos_consorcios):
    """Un admin de una administración con dos consorcios ve el contador del otro."""
    from backend.auth import create_access_token
    from backend.models import Consorcio, Notificacion, Rol

    # Mover el consorcio 2 bajo la administración 1: mismo admin, dos edificios.
    db.get(Consorcio, 2).administracion_id = 1
    db.add(Notificacion(consorcio_id=1, usuario_id=1, tipo="x", mensaje="acá", leida=False))
    db.add(Notificacion(consorcio_id=2, usuario_id=1, tipo="x", mensaje="allá", leida=False))
    db.add(Notificacion(consorcio_id=2, usuario_id=1, tipo="x", mensaje="allá2", leida=False))
    db.commit()

    token = create_access_token(user_id=1, rol=Rol.administracion, departamento_id=None)
    headers = {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}

    r = client.get("/notificaciones/no-leidas-count", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"count": 1, "otros_consorcios": 2}


def test_contador_de_depto_no_tiene_otros_consorcios(client, headers_depto_a, db):
    from backend.models import Notificacion

    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje="X", leida=False))
    db.commit()
    r = client.get("/notificaciones/no-leidas-count", headers=headers_depto_a)
    assert r.json()["otros_consorcios"] == 0


def test_marcar_todas_alcanza_solo_al_consorcio_activo(client, db, dos_consorcios):
    from backend.auth import create_access_token
    from backend.models import Consorcio, Notificacion, Rol

    db.get(Consorcio, 2).administracion_id = 1
    db.add(Notificacion(consorcio_id=1, usuario_id=1, tipo="x", mensaje="acá", leida=False))
    n2 = Notificacion(consorcio_id=2, usuario_id=1, tipo="x", mensaje="allá", leida=False)
    db.add(n2)
    db.commit()

    token = create_access_token(user_id=1, rol=Rol.administracion, departamento_id=None)
    headers = {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}

    r = client.post("/notificaciones/marcar-todas-leidas", headers=headers)
    assert r.status_code == 204
    db.refresh(n2)
    assert n2.leida is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones.py -v`
Expected: FAIL en los nuevos (`KeyError: 'tipo'`, `otros_consorcios` ausente, filtros ignorados).

- [ ] **Step 4: Actualizar los schemas**

En `backend/schemas.py`, en `NotificacionOut` agregar `tipo: str` después de `usuario_id`. En `NotificacionesCountOut` agregar:

```python
class NotificacionesCountOut(BaseModel):
    count: int
    # No leídas del usuario en los OTROS consorcios de su administración.
    # Siempre 0 para departamento y representante: tienen uno solo.
    otros_consorcios: int = 0
```

- [ ] **Step 5: Reescribir el router**

Reemplazar `listar_notificaciones` y `contar_no_leidas` en `backend/routers/notificaciones.py`:

```python
@router.get(
    "",
    response_model=list[NotificacionOut],
    summary="Listar notificaciones del usuario",
)
def listar_notificaciones(
    solo_no_leidas: bool = False,
    q: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> list[Notificacion]:
    stmt = select(Notificacion).where(
        Notificacion.usuario_id == user.id,
        Notificacion.consorcio_id == cid,
    )
    if solo_no_leidas:
        stmt = stmt.where(Notificacion.leida == False)  # noqa: E712
    if q:
        stmt = stmt.where(Notificacion.mensaje.ilike(f"%{q}%"))

    stmt = stmt.order_by(Notificacion.created_at.desc(), Notificacion.id.desc())
    return list(db.scalars(stmt.offset(offset).limit(limit)).all())


@router.get(
    "/no-leidas-count",
    response_model=NotificacionesCountOut,
    summary="Contar notificaciones no leídas",
)
def contar_no_leidas(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> NotificacionesCountOut:
    base = select(func.count(Notificacion.id)).where(
        Notificacion.usuario_id == user.id,
        Notificacion.leida == False,  # noqa: E712
    )
    count = db.scalar(base.where(Notificacion.consorcio_id == cid)) or 0

    # Para que el admin con varios edificios no pierda trabajo de vista sin
    # tener que entrar a cada uno. Un depto tiene un solo consorcio: siempre 0.
    otros = db.scalar(base.where(Notificacion.consorcio_id != cid)) or 0

    return NotificacionesCountOut(count=count, otros_consorcios=otros)
```

En `marcar_todas_leidas`, agregar la dependencia `cid: int = Depends(get_consorcio_activo)` y el filtro `Notificacion.consorcio_id == cid` a la query. En `marcar_leida`, agregar `cid` y sumar `notif.consorcio_id != cid` a la condición del 404.

Agregar `Query` al import de fastapi.

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones.py -v`
Expected: PASS.

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: todo verde.

- [ ] **Step 7: Commit**

```bash
git add openapi.yaml backend/schemas.py backend/routers/notificaciones.py tests/test_notificaciones.py
git commit -m "feat: listado con filtros, busqueda y contador de otros consorcios"
```

---

### Task 10: Endpoints de preferencias

**Files:**
- Modify: `openapi.yaml`
- Modify: `backend/schemas.py`
- Modify: `backend/routers/notificaciones.py`
- Test: `tests/test_notificaciones.py`

**Interfaces:**
- Consumes: `eventos_para_rol`, `evento`, `email_activo_para`, `guardar_preferencia`.
- Produces: `GET /notificaciones/preferencias`, `PUT /notificaciones/preferencias`.

- [ ] **Step 1: Documentar en `openapi.yaml`**

Agregar bajo una sola entrada `/notificaciones/preferencias` los verbos `get` (200, `array` de `PreferenciaNotificacionOut`) y `put` (204). Definir `PreferenciaNotificacionOut` con `tipo`, `etiqueta`, `email_activo`, `editable`, `motivo_no_editable`, y `PreferenciaNotificacionIn` con `tipo` y `email_activo`.

- [ ] **Step 2: Write the failing test**

Agregar a `tests/test_notificaciones.py`:

```python
def test_preferencias_depto_lista_sus_ocho_eventos(client, headers_depto_a):
    r = client.get("/notificaciones/preferencias", headers=headers_depto_a)
    assert r.status_code == 200
    assert len(r.json()) == 8


def test_preferencias_admin_lista_sus_cuatro_eventos(client, headers_admin):
    r = client.get("/notificaciones/preferencias", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 4


def test_preferencias_representante_lista_vacia(client, headers_representante):
    r = client.get("/notificaciones/preferencias", headers=headers_representante)
    assert r.status_code == 200
    assert r.json() == []


def test_preferencias_devuelve_los_defaults_del_catalogo(client, headers_depto_a):
    r = client.get("/notificaciones/preferencias", headers=headers_depto_a)
    por_tipo = {p["tipo"]: p for p in r.json()}
    assert por_tipo["comunicado_publicado"]["email_activo"] is True
    assert por_tipo["comprobante_aprobado"]["email_activo"] is False


def test_reserva_confirmada_no_es_editable(client, headers_depto_a):
    r = client.get("/notificaciones/preferencias", headers=headers_depto_a)
    por_tipo = {p["tipo"]: p for p in r.json()}
    assert por_tipo["reserva_confirmada"]["editable"] is False
    assert por_tipo["reserva_confirmada"]["motivo_no_editable"] == "Sólo se envía por correo."


def test_put_preferencias_apaga_el_mail(client, headers_depto_a):
    r = client.put(
        "/notificaciones/preferencias",
        json=[{"tipo": "comunicado_publicado", "email_activo": False}],
        headers=headers_depto_a,
    )
    assert r.status_code == 204

    r2 = client.get("/notificaciones/preferencias", headers=headers_depto_a)
    por_tipo = {p["tipo"]: p for p in r2.json()}
    assert por_tipo["comunicado_publicado"]["email_activo"] is False


def test_put_preferencias_tipo_desconocido_es_400(client, headers_depto_a):
    r = client.put(
        "/notificaciones/preferencias",
        json=[{"tipo": "no_existe", "email_activo": False}],
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_put_preferencias_tipo_de_otro_rol_es_400(client, headers_depto_a):
    r = client.put(
        "/notificaciones/preferencias",
        json=[{"tipo": "peticion_nueva", "email_activo": True}],
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_put_preferencias_no_editable_es_400(client, headers_depto_a):
    r = client.put(
        "/notificaciones/preferencias",
        json=[{"tipo": "reserva_confirmada", "email_activo": False}],
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_las_preferencias_afectan_el_envio_real(client, headers_admin, headers_depto_a, db, capsys):
    client.put(
        "/notificaciones/preferencias",
        json=[{"tipo": "comunicado_publicado", "email_activo": False}],
        headers=headers_depto_a,
    )
    capsys.readouterr()

    client.post(
        "/comunicados",
        json={"titulo": "Corte", "cuerpo": "X"},
        headers=headers_admin,
    )
    salida = capsys.readouterr().out
    # Al depto A (usuario 2) no le llega mail; al B (usuario 3) sí.
    assert "a@test.local" not in salida
    assert "b@test.local" in salida
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones.py -v -k preferencia`
Expected: FAIL — 404, el endpoint no existe.

- [ ] **Step 4: Agregar los schemas**

En `backend/schemas.py`, después de `NotificacionesCountOut`:

```python
class PreferenciaNotificacionOut(BaseModel):
    tipo: str
    etiqueta: str
    email_activo: bool
    # False ⇒ el interruptor se muestra pero no se puede tocar.
    editable: bool
    motivo_no_editable: str | None


class PreferenciaNotificacionIn(BaseModel):
    tipo: str
    email_activo: bool
```

- [ ] **Step 5: Agregar los endpoints**

En `backend/routers/notificaciones.py`, **antes** de la ruta `/{notificacion_id}/marcar-leida` (si no, `preferencias` se come como `notificacion_id`):

```python
@router.get(
    "/preferencias",
    response_model=list[PreferenciaNotificacionOut],
    summary="Listar preferencias de aviso del usuario",
)
def listar_preferencias(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> list[PreferenciaNotificacionOut]:
    return [
        PreferenciaNotificacionOut(
            tipo=ev.clave,
            etiqueta=ev.etiqueta,
            email_activo=email_activo_para(db, user.id, ev),
            editable=ev.editable,
            motivo_no_editable=ev.motivo_no_editable,
        )
        for ev in eventos_para_rol(user.rol)
    ]


@router.put(
    "/preferencias",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Guardar preferencias de aviso del usuario",
)
def guardar_preferencias(
    payload: list[PreferenciaNotificacionIn],
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> None:
    permitidos = {ev.clave: ev for ev in eventos_para_rol(user.rol)}

    for item in payload:
        ev = permitidos.get(item.tipo)
        if ev is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Aviso desconocido para tu rol: {item.tipo}.",
            )
        if not ev.editable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El aviso '{ev.etiqueta}' no se puede configurar.",
            )
        guardar_preferencia(db, user.id, ev, item.email_activo)

    db.commit()
```

Agregar los imports:

```python
from ..notificaciones.catalogo import eventos_para_rol
from ..notificaciones.preferencias import email_activo_para, guardar_preferencia
from ..schemas import (
    NotificacionOut,
    NotificacionesCountOut,
    PreferenciaNotificacionIn,
    PreferenciaNotificacionOut,
)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones.py -v`
Expected: PASS.

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: todo verde.

- [ ] **Step 7: Commit**

```bash
git add openapi.yaml backend/schemas.py backend/routers/notificaciones.py tests/test_notificaciones.py
git commit -m "feat: endpoints de preferencias de aviso por usuario"
```

---

### Task 11: Campanita — ver todas, engranaje y otros consorcios

**Files:**
- Modify: `frontend/src/api/notificaciones.js`
- Modify: `frontend/src/components/Campanita.jsx`
- Modify: `frontend/src/index.css` (bloque `.campanita-*`)

**Interfaces:**
- Consumes: `GET /notificaciones/no-leidas-count` con `otros_consorcios`.
- Produces: nada que consuman otras tareas.

- [ ] **Step 1: Extender el cliente de API**

En `frontend/src/api/notificaciones.js`, reemplazar `listarNotificaciones` y agregar las dos funciones de preferencias:

```javascript
export function listarNotificaciones({ limit = 50, offset = 0, soloNoLeidas = false, q = "" } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (soloNoLeidas) params.set("solo_no_leidas", "true");
  if (q) params.set("q", q);
  return apiFetch(`/notificaciones?${params.toString()}`);
}

export function listarPreferencias() {
  return apiFetch("/notificaciones/preferencias");
}

export function guardarPreferencias(items) {
  return apiFetch("/notificaciones/preferencias", { method: "PUT", body: items });
}
```

- [ ] **Step 2: Actualizar `Campanita.jsx`**

Cambiar la llamada de `refrescarLista` a la nueva firma:

```javascript
  async function refrescarLista() {
    const r = await listarNotificaciones({ limit: 10 });
    if (r.status === 200) setItems(r.data);
  }
```

Agregar el estado del contador de otros consorcios:

```javascript
  const [otrosConsorcios, setOtrosConsorcios] = useState(0);
```

y en `refrescarCount`:

```javascript
  async function refrescarCount() {
    const r = await obtenerNoLeidasCount();
    if (r.status === 200) {
      setCount(r.data.count);
      setOtrosConsorcios(r.data.otros_consorcios ?? 0);
    }
  }
```

En el encabezado del panel, agregar el engranaje a la izquierda del "Marcar todas":

```jsx
          <button
            type="button"
            onClick={() => { setAbierto(false); navigate("/notificaciones/preferencias"); }}
            className="campanita-engranaje"
            aria-label="Configurar avisos"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
```

Al pie del panel, después del `</ul>` / del bloque de vacío, agregar:

```jsx
          <footer className="campanita-panel-pie">
            <button
              type="button"
              className="campanita-ver-todas"
              onClick={() => { setAbierto(false); navigate("/notificaciones"); }}
            >
              Ver todas
            </button>
            {/* Sólo la administración puede tener más de un consorcio; para
                depto y representante el backend devuelve siempre 0, así que
                esta línea no aparece sin necesidad de chequear el rol acá. */}
            {otrosConsorcios > 0 && (
              <span className="campanita-otros-consorcios">
                {otrosConsorcios} sin leer en otros consorcios
              </span>
            )}
          </footer>
```

- [ ] **Step 3: Estilos**

En `frontend/src/index.css`, después de `.campanita-marcar-todas:hover:not(:disabled)`:

```css
/* El engranaje va a la izquierda del "Marcar todas": es configuración, no
   acción sobre la lista, así que no compite con el botón principal. */
.campanita-engranaje {
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  padding: 0.25rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  min-width: 44px;
  justify-content: center;
}

.campanita-engranaje:hover:not(:disabled) {
  color: var(--color-primary);
}

.campanita-panel-header .campanita-acciones {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.campanita-panel-pie {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.25rem;
  padding: 0.5rem 0.8rem;
  border-top: 1px solid var(--color-border);
}

.campanita-ver-todas {
  background: transparent;
  border: none;
  color: var(--color-primary);
  font-size: 0.75rem;
  padding: 0.25rem 0;
  cursor: pointer;
  /* Ancho al contenido: un botón de texto estirado a todo el panel se lee
     como barra de acción y este no lo es. */
  width: fit-content;
  min-height: 44px;
}

.campanita-ver-todas:hover {
  text-decoration: underline;
}

.campanita-otros-consorcios {
  font-size: 0.6875rem;
  color: var(--color-text-muted);
}
```

Envolver el engranaje y el "Marcar todas" del JSX en `<div className="campanita-acciones">` para que el header siga siendo dos bloques y no tres.

- [ ] **Step 4: Verificar en el navegador**

Run: `cd frontend && npm run dev`

Abrir la app, entrar como administración, verificar: el engranaje navega a preferencias, el "Ver todas" navega a la bandeja, y la línea de otros consorcios aparece sólo cuando corresponde. Revisar a 375px de ancho.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/notificaciones.js frontend/src/components/Campanita.jsx frontend/src/index.css
git commit -m "feat: engranaje, ver todas y otros consorcios en la campanita"
```

---

### Task 12: Pantalla de notificaciones

**Files:**
- Create: `frontend/src/screens/Notificaciones.jsx`
- Modify: `frontend/src/App.jsx` (import + `<Route path="notificaciones" .../>`)

**Interfaces:**
- Consumes: `listarNotificaciones`, `marcarLeida`, `marcarTodasLeidas`.
- Produces: la ruta `/notificaciones`.

- [ ] **Step 1: Crear la pantalla**

`frontend/src/screens/Notificaciones.jsx`:

```jsx
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  listarNotificaciones,
  marcarLeida,
  marcarTodasLeidas,
} from "../api/notificaciones";
import { formatearTiempoRelativo } from "../utils/tiempoRelativo";

const POR_PAGINA = 30;

export default function Notificaciones() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [soloNoLeidas, setSoloNoLeidas] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [offset, setOffset] = useState(0);
  const [hayMas, setHayMas] = useState(false);
  const [cargando, setCargando] = useState(false);

  const cargar = useCallback(
    async (nuevoOffset, reemplazar) => {
      setCargando(true);
      const r = await listarNotificaciones({
        limit: POR_PAGINA,
        offset: nuevoOffset,
        soloNoLeidas,
        q: busqueda,
      });
      setCargando(false);
      if (r.status !== 200) return;
      setItems((prev) => (reemplazar ? r.data : [...prev, ...r.data]));
      setOffset(nuevoOffset + r.data.length);
      // Una página completa significa que puede haber más; una parcial, que
      // llegamos al final. Evita un pedido extra sólo para descubrirlo.
      setHayMas(r.data.length === POR_PAGINA);
    },
    [soloNoLeidas, busqueda],
  );

  useEffect(() => {
    const id = setTimeout(() => cargar(0, true), 250);
    return () => clearTimeout(id);
  }, [cargar]);

  async function handleClick(n) {
    if (!n.leida) await marcarLeida(n.id);
    if (n.link) navigate(n.link);
    else cargar(0, true);
  }

  async function handleMarcarTodas() {
    await marcarTodasLeidas();
    cargar(0, true);
  }

  return (
    <section className="pantalla-notificaciones">
      <header className="pantalla-notificaciones-header">
        <h1>Notificaciones</h1>
        <button type="button" onClick={handleMarcarTodas}>Marcar todas</button>
      </header>

      <div className="pantalla-notificaciones-filtros">
        <input
          type="search"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar en las notificaciones"
          aria-label="Buscar en las notificaciones"
        />
        <label>
          <input
            type="checkbox"
            checked={soloNoLeidas}
            onChange={(e) => setSoloNoLeidas(e.target.checked)}
          />
          Solo no leídas
        </label>
      </div>

      {items.length === 0 && !cargando ? (
        <p className="pantalla-notificaciones-vacio">
          {busqueda || soloNoLeidas
            ? "No hay notificaciones que coincidan."
            : "Todavía no tenés notificaciones."}
        </p>
      ) : (
        <ul className="pantalla-notificaciones-lista">
          {items.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                onClick={() => handleClick(n)}
                className={`campanita-item${n.leida ? "" : " campanita-item-no-leida"}`}
              >
                <span className="campanita-item-punto" aria-hidden="true" />
                <span className="campanita-item-texto">
                  <span className="campanita-item-mensaje">{n.mensaje}</span>
                  <span className="campanita-item-fecha">
                    {formatearTiempoRelativo(n.created_at)}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {hayMas && (
        <button type="button" onClick={() => cargar(offset, false)} disabled={cargando}>
          {cargando ? "Cargando…" : "Cargar más"}
        </button>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Registrar la ruta**

En `frontend/src/App.jsx`, agregar el import junto a los demás screens y la ruta dentro del bloque de rutas autenticadas, cerca de `comunicados`:

```jsx
            <Route path="notificaciones" element={<Notificaciones />} />
```

- [ ] **Step 3: Estilos**

En `frontend/src/index.css`, al final del bloque de campanita:

```css
/* Las filas reusan .campanita-item*: ya resuelven el gutter del punto y el
   estado de no-leída. Acá sólo va el envoltorio de pantalla. */
.pantalla-notificaciones {
  padding: 1rem;
}

.pantalla-notificaciones-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.pantalla-notificaciones-header h1 {
  margin: 0;
}

.pantalla-notificaciones-filtros {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.pantalla-notificaciones-filtros input[type="search"] {
  width: 100%;
  min-height: 44px;
}

.pantalla-notificaciones-filtros label {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8125rem;
  color: var(--color-text-muted);
}

@media (min-width: 600px) {
  .pantalla-notificaciones {
    /* Ancho al contenido, no al viewport: una lista de una línea por fila
       estirada a 1600px es ilegible. */
    max-width: 46rem;
  }

  .pantalla-notificaciones-filtros {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }

  .pantalla-notificaciones-filtros input[type="search"] {
    width: fit-content;
    min-width: 18rem;
  }
}

.pantalla-notificaciones-lista {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
}

.pantalla-notificaciones-vacio {
  color: var(--color-text-muted);
  padding: 1.5rem 0;
}
```

- [ ] **Step 4: Verificar en el navegador**

Run: `cd frontend && npm run dev`

Verificar: el filtro de no leídas, el buscador con su retardo, el "Cargar más", y que hacer clic navegue y marque como leída. Revisar a 375px.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/Notificaciones.jsx frontend/src/App.jsx frontend/src/index.css
git commit -m "feat: pantalla completa de notificaciones con filtro y busqueda"
```

---

### Task 13: Pantalla de preferencias

**Files:**
- Create: `frontend/src/screens/PreferenciasAvisos.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `listarPreferencias`, `guardarPreferencias`.
- Produces: la ruta `/notificaciones/preferencias`.

- [ ] **Step 1: Crear la pantalla**

`frontend/src/screens/PreferenciasAvisos.jsx`:

```jsx
import { useEffect, useState } from "react";
import { guardarPreferencias, listarPreferencias } from "../api/notificaciones";

export default function PreferenciasAvisos() {
  const [items, setItems] = useState([]);
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState("");

  useEffect(() => {
    listarPreferencias().then((r) => {
      if (r.status === 200) setItems(r.data);
    });
  }, []);

  function alternar(tipo) {
    setItems((prev) =>
      prev.map((p) => (p.tipo === tipo ? { ...p, email_activo: !p.email_activo } : p)),
    );
    setMensaje("");
  }

  async function handleGuardar() {
    setGuardando(true);
    // Sólo los editables: el backend rechaza los otros con 400.
    const payload = items
      .filter((p) => p.editable)
      .map((p) => ({ tipo: p.tipo, email_activo: p.email_activo }));
    const r = await guardarPreferencias(payload);
    setGuardando(false);
    setMensaje(r.status === 204 ? "Preferencias guardadas." : "No se pudo guardar.");
  }

  return (
    <section className="pantalla-preferencias-avisos">
      <header>
        <h1>Avisos</h1>
        <p>
          Elegí de qué te avisamos por correo. La campanita dentro de la app
          siempre te avisa de todo.
        </p>
      </header>

      {items.length === 0 ? (
        <p>Tu rol no recibe avisos configurables.</p>
      ) : (
        <ul className="lista-preferencias">
          {items.map((p) => (
            <li key={p.tipo}>
              <label>
                <input
                  type="checkbox"
                  checked={p.email_activo}
                  disabled={!p.editable}
                  onChange={() => alternar(p.tipo)}
                />
                <span className="preferencia-etiqueta">{p.etiqueta}</span>
              </label>
              {!p.editable && (
                <span className="preferencia-nota">{p.motivo_no_editable}</span>
              )}
            </li>
          ))}
        </ul>
      )}

      <footer>
        <button type="button" onClick={handleGuardar} disabled={guardando || items.length === 0}>
          {guardando ? "Guardando…" : "Guardar"}
        </button>
        {mensaje && <span role="status">{mensaje}</span>}
      </footer>
    </section>
  );
}
```

- [ ] **Step 2: Registrar la ruta**

En `frontend/src/App.jsx`, junto a la ruta del Task 12:

```jsx
            <Route path="notificaciones/preferencias" element={<PreferenciasAvisos />} />
```

**Ojo con el orden:** React Router v6 resuelve por especificidad, no por orden, así que `notificaciones/preferencias` no queda tapada por `notificaciones`. Verificarlo navegando a mano.

- [ ] **Step 3: Estilos**

En `frontend/src/index.css`, después del bloque del Task 12:

```css
.pantalla-preferencias-avisos {
  padding: 1rem;
}

.pantalla-preferencias-avisos header p {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  max-width: 34rem;
}

@media (min-width: 600px) {
  .pantalla-preferencias-avisos {
    max-width: 40rem;
  }
}

.lista-preferencias {
  list-style: none;
  margin: 0 0 1rem;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  overflow: hidden;
}

.lista-preferencias li {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid var(--color-border);
}

.lista-preferencias li:last-child {
  border-bottom: none;
}

.lista-preferencias label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 44px;
  cursor: pointer;
}

.lista-preferencias label:has(input:disabled) {
  cursor: default;
}

.preferencia-etiqueta {
  font-size: 0.875rem;
}

/* La leyenda del interruptor bloqueado va debajo y alineada al texto, no
   al checkbox: es una explicación de la fila, no una etiqueta más. */
.preferencia-nota {
  font-size: 0.6875rem;
  color: var(--color-text-muted);
  padding-left: 1.65rem;
}

.pantalla-preferencias-avisos footer {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
```

- [ ] **Step 4: Verificar en el navegador**

Run: `cd frontend && npm run dev`

Verificar como departamento: aparecen ocho avisos, el de reserva confirmada está deshabilitado con su leyenda, guardar responde. Como administración: aparecen cuatro. Revisar a 375px.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/PreferenciasAvisos.jsx frontend/src/App.jsx frontend/src/index.css
git commit -m "feat: pantalla de preferencias de avisos"
```

---

### Task 14: Modo demo

**Files:**
- Modify: `backend/export_demo.py`
- Modify: `frontend/src/demo/escrituras.js`
- Modify: `frontend/src/demo/recorrido.test.js`
- Modify: `frontend/src/demo/dataset.json` (regenerado, no editado a mano)

**Interfaces:**
- Consumes: los endpoints de los Tasks 9 y 10.
- Produces: nada.

- [ ] **Step 1: Agregar las rutas nuevas al recorrido**

En `frontend/src/demo/recorrido.test.js`, junto a las dos entradas de campanita que ya están:

```javascript
  ["/notificaciones/preferencias", "Preferencias de avisos"],
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/recorrido.test.js`
Expected: FAIL — la ruta no está en el dataset exportado.

- [ ] **Step 3: Exportar las preferencias**

En `backend/export_demo.py`, en la lista de tuplas `(perfil, path)`, junto a
`("admin", "/notificaciones")` y `("admin", "/notificaciones/no-leidas-count")`:

```python
    ("admin", "/notificaciones/preferencias"),
    ("depto", "/notificaciones/preferencias"),
```

El contador ya sale del endpoint real, así que `otros_consorcios` viene solo;
verificar en el dataset regenerado que aparezca en `/notificaciones/no-leidas-count`.

- [ ] **Step 4: Manejar el `PUT` de preferencias en la demo**

En `frontend/src/demo/escrituras.js`, dentro de `escribir`, junto a los otros
casos:

```javascript
  if (method === "PUT" && ruta === "/notificaciones/preferencias") {
    // La demo corre entera en el navegador: guardar en el estado en memoria
    // alcanza para que la pantalla responda como la real.
    const actuales = estado.leer("/notificaciones/preferencias") ?? [];
    const porTipo = new Map((body ?? []).map((p) => [p.tipo, p.email_activo]));
    estado.reemplazar(
      "/notificaciones/preferencias",
      actuales.map((p) =>
        porTipo.has(p.tipo) ? { ...p, email_activo: porTipo.get(p.tipo) } : p,
      ),
    );
    return { ok: true, status: 204, data: null };
  }
```

(`reemplazar` es el método del estado en memoria; `agregar` es para listas que
crecen y acá se reescribe la lista entera.)

`servidor.js` deriva cualquier método distinto de `GET` a `escribir`, así que el
`PUT` llega solo — no hay que tocar el enrutador.

- [ ] **Step 5: Regenerar el dataset**

Run: `./.venv/Scripts/python.exe -m backend.export_demo`

(Confirmar el comando exacto leyendo el `if __name__ == "__main__"` de `backend/export_demo.py`.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run`
Expected: todo verde, incluido `recorrido.test.js`.

Run: `./.venv/Scripts/python.exe -m pytest tests/test_export_demo.py tests/test_dataset_demo_curado.py -v`
Expected: PASS.

- [ ] **Step 7: Verificar la demo a mano**

Run: `cd frontend && npm run dev`

Entrar en modo demo, abrir la campanita, ir a preferencias, apagar un interruptor y guardar. Verificar que no aparezca el cartel de "no implementado".

- [ ] **Step 8: Full suite y commit**

Run: `./.venv/Scripts/python.exe -m pytest -v && cd frontend && npx vitest run`
Expected: todo verde.

```bash
git add backend/export_demo.py frontend/src/demo
git commit -m "feat: soporte de preferencias de aviso en el modo demo"
```

---

## Verificación final

- [ ] `./.venv/Scripts/python.exe -m pytest -v` — todo verde.
- [ ] `cd frontend && npx vitest run` — todo verde.
- [ ] `grep -rn "crear_notificacion\|notificar_cambio_estado_peticion\|notificar_reserva" backend tests` — sin resultados.
- [ ] `./.venv/Scripts/python.exe -m alembic upgrade head` sobre una copia de una base con datos previos — sin errores, las notificaciones viejas quedan con `tipo="legacy"`.
- [ ] Los tres tests que el plan promete no tocar siguen intactos en git: `git diff HEAD~N --stat` no debe mostrar cambios en las líneas de `test_trabajos.py` ni en `test_reservas.py::test_depto_cancela_su_reserva_no_genera_notificacion`.

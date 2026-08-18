# Recuperación de contraseña por email — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que un vecino que olvidó su contraseña la recupere solo, por email, sin que intervenga el administrador ni el dueño de la plataforma.

**Architecture:** Dos endpoints públicos en el router de auth. El primero recibe un email y —exista o no la cuenta— responde siempre 202, guardando en la base el **hash** de un token de un solo uso con vencimiento, y mandando el link por correo. El segundo canjea ese token por una contraseña nueva. El token en claro sólo existe en el email: en la base va hasheado, así que ni una filtración de la base permite resetear contraseñas.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · `secrets` + `hashlib` (token y hash) · SMTP vía `backend/mail_service.py` · React + Vite · pytest.

**Spec:** `docs/superpowers/specs/2026-08-17-listo-para-cliente-real.md` (Frente 3)

## Global Constraints

- **Nunca revelar si un email está registrado.** `POST /auth/recuperar-password` responde 202 siempre, con el mismo cuerpo y sin ramificar el tiempo de respuesta de forma observable. El proyecto ya sigue este criterio en el login (`_DUMMY_HASH` en `backend/routers/auth.py:18`).
- **El token en claro no se persiste.** En la base va sólo `sha256(token)`.
- El cambio de esquema va como revisión de Alembic. Después de generarla, `pytest tests/test_migraciones.py` tiene que quedar verde: esa es la guarda de deriva.
- Los 1104 tests existentes siguen en verde al terminar cada tarea.
- Contraseña nueva: mismo mínimo que el resto del sistema — `min_length=8` (ver `CambiarPasswordIn`, `backend/schemas.py:44`).
- Con `DEMO_MODE=true`, `mail_service` ya fuerza modo consola: la demo nunca manda un correo real.
- Nombres, mensajes y comentarios en español.

## Contexto que el implementador necesita saber

**Lo que hay hoy.** `backend/routers/auth.py` expone `/login`, `/me`, `/logout` y `/cambiar-password`. El único reseteo posible es `reset_password_usuario` (`backend/routers/super_admin.py:319`), disponible **sólo para el super admin**: ni el administrador del consorcio puede usarlo. Con 50 departamentos eso se vuelve soporte manual la primera semana.

**Hasheo de contraseñas.** `backend/security.py` — `hash_password` / `verify_password` con bcrypt vía passlib. Bcrypt es caro (~100 ms), lo que importa para el diseño del rate limit.

**El flag que hay que bajar.** `Usuario.must_change_password` (`backend/models.py:188`) fuerza 403 en todo endpoint operacional (ver `backend/tenant.py`). `cambiar_password` lo baja al cambiar la contraseña; el restablecimiento tiene que hacer lo mismo, o el usuario resetea su clave y sigue sin poder entrar.

**Cuentas dadas de baja.** `Usuario.activa` y `Administracion.activa` — un usuario inactivo o de un tenant suspendido no debe poder recuperar nada. `_administracion_activa_para` (`backend/routers/auth.py:39`) ya resuelve lo segundo y se reutiliza.

**Correo.** `backend/mail_service.py` — `enviar_email(to, subject, body, attachments)`. Devuelve `False` si falla el envío en vez de levantar excepción. Importante: **un fallo de envío no debe cambiar la respuesta**, o el atacante distingue emails registrados por el código de estado.

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `backend/models.py` (modificar) | `TokenRecuperacion`: hash del token, vencimiento, un solo uso. |
| `backend/migrations/versions/*.py` (crear) | Revisión de Alembic con la tabla nueva. |
| `backend/schemas.py` (modificar) | `RecuperarPasswordIn`, `RestablecerPasswordIn`. |
| `backend/recuperacion.py` (crear) | Lógica del token: generar, hashear, validar, invalidar. Aparte del router para poder testearla sin HTTP. |
| `backend/routers/auth.py` (modificar) | Los dos endpoints públicos. |
| `backend/config.py` (modificar) | `FRONTEND_URL`, `RECUPERACION_TOKEN_MINUTOS`, `RECUPERACION_MAX_POR_HORA`. |
| `frontend/src/screens/RecuperarPassword.jsx` (crear) | Pedir el link. |
| `frontend/src/screens/RestablecerPassword.jsx` (crear) | Elegir la contraseña nueva. |
| `frontend/src/api/auth.js` (modificar) | Las dos llamadas. |
| `frontend/src/App.jsx` (modificar) | Las dos rutas públicas. |
| `tests/test_recuperar_password.py` (crear) | Circuito completo y todos los rechazos. |

---

### Task 1: Modelo del token y migración

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/config.py`
- Create: `backend/migrations/versions/<hash>_tokens_recuperacion.py` (autogenerado)
- Create: `tests/test_recuperar_password.py`

**Interfaces:**
- Produces: `TokenRecuperacion` con columnas `id`, `usuario_id`, `token_hash` (unique), `expira_at`, `usado_at`, `creado_at`. Y en `Settings`: `FRONTEND_URL: str`, `RECUPERACION_TOKEN_MINUTOS: int = 60`, `RECUPERACION_MAX_POR_HORA: int = 3`.

- [ ] **Step 1: Escribir el test del modelo (falla)**

Crear `tests/test_recuperar_password.py`:

```python
"""Recuperación de contraseña por email.

Lo que se protege acá, además del circuito feliz:
  - no revelar qué emails están registrados,
  - que el token sea de un solo uso y venza,
  - que en la base nunca quede el token en claro.
"""
from datetime import datetime, timedelta, timezone

import pytest

from backend.models import TokenRecuperacion, Usuario


def test_el_modelo_guarda_hash_vencimiento_y_uso(db_session):
    token = TokenRecuperacion(
        usuario_id=1,
        token_hash="a" * 64,
        expira_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(token)
    db_session.commit()

    guardado = db_session.get(TokenRecuperacion, token.id)
    assert guardado.usado_at is None
    assert guardado.creado_at is not None


def test_dos_tokens_no_pueden_compartir_hash(db_session):
    """El hash es la llave de canje: si se repitiera, un canje afectaría a dos
    usuarios."""
    from sqlalchemy.exc import IntegrityError

    ahora = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.add(TokenRecuperacion(usuario_id=1, token_hash="b" * 64, expira_at=ahora))
    db_session.commit()

    db_session.add(TokenRecuperacion(usuario_id=2, token_hash="b" * 64, expira_at=ahora))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_recuperar_password.py -q`
Expected: FAIL — `TokenRecuperacion` no existe.

- [ ] **Step 3: Agregar el modelo**

En `backend/models.py`, junto a `Usuario`:

```python
class TokenRecuperacion(Base):
    """Token de un solo uso para restablecer la contraseña.

    Se guarda el **hash** del token, nunca el token en claro: el claro sólo
    viaja en el email. Así una filtración de la base no permite resetear las
    contraseñas de nadie.

    No lleva `consorcio_id`: cuelga del usuario, que ya define el alcance.
    """

    __tablename__ = "tokens_recuperacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    expira_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

Verificar que `DateTime`, `func`, `ForeignKey` y `String` ya estén importados en el módulo; agregarlos si falta alguno.

- [ ] **Step 4: Agregar la configuración**

En `backend/config.py`, dentro de `Settings`:

```python
    # Base del link que se manda por email. En producción, el dominio real del
    # frontend; si queda vacío, el link sale relativo y no sirve en un correo.
    FRONTEND_URL: str = "http://localhost:5173"
    RECUPERACION_TOKEN_MINUTOS: int = 60
    RECUPERACION_MAX_POR_HORA: int = 3
```

- [ ] **Step 5: Generar la revisión de Alembic**

```powershell
$env:DATABASE_URL = "sqlite:///./_migracion_tmp.db"
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m alembic revision --autogenerate -m "tokens de recuperacion de password"
Remove-Item ./_migracion_tmp.db
```

Abrir la revisión generada y verificar que crea `tokens_recuperacion` con el índice único sobre `token_hash` y la FK con `ondelete="CASCADE"`.

- [ ] **Step 6: Correr los tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_recuperar_password.py tests/test_migraciones.py -q`
Expected: PASS. La guarda de deriva confirma que la revisión y los modelos quedaron alineados.

- [ ] **Step 7: Correr el suite completo y commitear**

```bash
./.venv/Scripts/python.exe -m pytest -q
git add backend/models.py backend/config.py backend/migrations/versions tests/test_recuperar_password.py
git commit -m "feat: modelo de token de recuperacion de password"
```

---

### Task 2: Lógica del token, aislada del HTTP

**Files:**
- Create: `backend/recuperacion.py`
- Modify: `tests/test_recuperar_password.py`

**Interfaces:**
- Consumes: `TokenRecuperacion` (Tarea 1).
- Produces:
  - `emitir_token(db, usuario) -> str | None` — devuelve el token **en claro** para el email, o `None` si el usuario superó el límite de pedidos por hora.
  - `canjear_token(db, token_claro) -> Usuario | None` — valida y marca usado; `None` si es inválido, vencido o ya usado.
  - `hashear(token_claro) -> str`

- [ ] **Step 1: Escribir los tests (fallan)**

```python
from backend import recuperacion


def test_emitir_token_devuelve_el_claro_y_guarda_solo_el_hash(db_session):
    usuario = db_session.get(Usuario, 2)

    claro = recuperacion.emitir_token(db_session, usuario)

    assert claro and len(claro) >= 32
    guardado = db_session.query(TokenRecuperacion).one()
    assert guardado.token_hash != claro
    assert guardado.token_hash == recuperacion.hashear(claro)


def test_canjear_token_devuelve_el_usuario_y_lo_marca_usado(db_session):
    usuario = db_session.get(Usuario, 2)
    claro = recuperacion.emitir_token(db_session, usuario)

    canjeado = recuperacion.canjear_token(db_session, claro)

    assert canjeado.id == usuario.id
    assert db_session.query(TokenRecuperacion).one().usado_at is not None


def test_un_token_no_se_puede_canjear_dos_veces(db_session):
    usuario = db_session.get(Usuario, 2)
    claro = recuperacion.emitir_token(db_session, usuario)
    recuperacion.canjear_token(db_session, claro)

    assert recuperacion.canjear_token(db_session, claro) is None


def test_un_token_vencido_no_se_canjea(db_session, monkeypatch):
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "RECUPERACION_TOKEN_MINUTOS", -1)
    usuario = db_session.get(Usuario, 2)
    claro = recuperacion.emitir_token(db_session, usuario)

    assert recuperacion.canjear_token(db_session, claro) is None


def test_un_token_inventado_no_se_canjea(db_session):
    assert recuperacion.canjear_token(db_session, "token-que-nadie-emitio") is None


def test_emitir_invalida_los_tokens_anteriores_del_usuario(db_session):
    """Pedir un link nuevo tiene que dejar sin efecto el anterior: si no, un
    link viejo reenviado o filtrado sigue sirviendo."""
    usuario = db_session.get(Usuario, 2)
    primero = recuperacion.emitir_token(db_session, usuario)
    recuperacion.emitir_token(db_session, usuario)

    assert recuperacion.canjear_token(db_session, primero) is None


def test_el_limite_por_hora_corta_los_pedidos(db_session, monkeypatch):
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "RECUPERACION_MAX_POR_HORA", 2)
    usuario = db_session.get(Usuario, 2)

    assert recuperacion.emitir_token(db_session, usuario) is not None
    assert recuperacion.emitir_token(db_session, usuario) is not None
    assert recuperacion.emitir_token(db_session, usuario) is None
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_recuperar_password.py -q`
Expected: FAIL — `backend.recuperacion` no existe.

- [ ] **Step 3: Crear `backend/recuperacion.py`**

```python
"""Tokens de recuperación de contraseña.

Aparte del router a propósito: son las reglas que importan (un solo uso,
vencimiento, límite de pedidos) y conviene poder testearlas sin levantar HTTP.

El token en claro se genera acá, se devuelve para el email y **no se persiste**:
en la base va sólo su sha256. No hace falta bcrypt como en las contraseñas —
el token tiene 256 bits de aleatoriedad, así que no hay diccionario que
adivinarlo, y sha256 mantiene el canje barato.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import TokenRecuperacion, Usuario


def hashear(token_claro: str) -> str:
    return hashlib.sha256(token_claro.encode()).hexdigest()


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def emitir_token(db: Session, usuario: Usuario) -> str | None:
    """Emite un token nuevo para `usuario` y devuelve el claro, o `None` si
    superó el límite de pedidos por hora.

    El límite se cuenta contra la base y no en memoria: sobrevive a un reinicio
    y funciona igual con más de una instancia del servidor.
    """
    settings = get_settings()
    ahora = _ahora()

    emitidos = db.scalar(
        select(func.count())
        .select_from(TokenRecuperacion)
        .where(
            TokenRecuperacion.usuario_id == usuario.id,
            TokenRecuperacion.creado_at >= ahora - timedelta(hours=1),
        )
    )
    if emitidos >= settings.RECUPERACION_MAX_POR_HORA:
        return None

    # Pedir un link nuevo invalida los anteriores: si no, un link viejo
    # reenviado o filtrado seguiría sirviendo.
    for viejo in db.scalars(
        select(TokenRecuperacion).where(
            TokenRecuperacion.usuario_id == usuario.id,
            TokenRecuperacion.usado_at.is_(None),
        )
    ):
        viejo.usado_at = ahora

    claro = secrets.token_urlsafe(32)
    db.add(
        TokenRecuperacion(
            usuario_id=usuario.id,
            token_hash=hashear(claro),
            expira_at=ahora + timedelta(minutes=settings.RECUPERACION_TOKEN_MINUTOS),
        )
    )
    db.commit()
    return claro


def canjear_token(db: Session, token_claro: str) -> Usuario | None:
    """Valida el token y lo marca usado. Devuelve el usuario, o `None` si el
    token no existe, ya se usó o venció."""
    if not token_claro:
        return None

    token = db.scalar(
        select(TokenRecuperacion).where(
            TokenRecuperacion.token_hash == hashear(token_claro)
        )
    )
    if token is None or token.usado_at is not None:
        return None

    # SQLite devuelve datetimes sin tzinfo; se los normaliza para poder
    # compararlos con un `now` que sí la tiene.
    expira = token.expira_at
    if expira.tzinfo is None:
        expira = expira.replace(tzinfo=timezone.utc)
    if expira < _ahora():
        return None

    token.usado_at = _ahora()
    db.commit()
    return db.get(Usuario, token.usuario_id)
```

Agregar `from sqlalchemy import func, select` (el count lo necesita).

- [ ] **Step 4: Correr los tests y el suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_recuperar_password.py -q` → PASS
Run: `./.venv/Scripts/python.exe -m pytest -q` → verde

- [ ] **Step 5: Commit**

```bash
git add backend/recuperacion.py tests/test_recuperar_password.py
git commit -m "feat: logica de tokens de recuperacion, con un solo uso y vencimiento"
```

---

### Task 3: Los dos endpoints públicos

**Files:**
- Modify: `backend/schemas.py`
- Modify: `backend/routers/auth.py`
- Modify: `tests/test_recuperar_password.py`
- Modify: `openapi.yaml`

**Interfaces:**
- Consumes: `emitir_token`, `canjear_token` (Tarea 2); `enviar_email` (`backend/mail_service.py`); `_administracion_activa_para` (`backend/routers/auth.py`).
- Produces: `POST /auth/recuperar-password` (202) y `POST /auth/restablecer-password` (204).

- [ ] **Step 1: Escribir los tests (fallan)**

```python
def test_pedir_recuperacion_de_un_email_registrado_responde_202(client, db_session):
    r = client.post("/auth/recuperar-password", json={"email": "depto-a@consorcio.local"})

    assert r.status_code == 202
    assert db_session.query(TokenRecuperacion).count() == 1


def test_pedir_recuperacion_de_un_email_inexistente_responde_igual(client, db_session):
    """No se puede distinguir un email registrado de uno que no lo está: si no,
    el formulario se convierte en un verificador de cuentas."""
    r = client.post("/auth/recuperar-password", json={"email": "nadie@ejemplo.com"})

    assert r.status_code == 202
    assert db_session.query(TokenRecuperacion).count() == 0


def test_el_email_lleva_el_link_con_el_token(client, capsys, db_session):
    """Sin SMTP configurado, mail_service imprime a consola: ahí se lee el link
    que le llegaría al usuario."""
    client.post("/auth/recuperar-password", json={"email": "depto-a@consorcio.local"})

    salida = capsys.readouterr().out
    assert "/restablecer-password?token=" in salida


def test_restablecer_con_token_valido_cambia_la_password(client, db_session, capsys):
    from backend.security import verify_password

    client.post("/auth/recuperar-password", json={"email": "depto-a@consorcio.local"})
    token = capsys.readouterr().out.split("?token=")[1].split()[0].strip()

    r = client.post(
        "/auth/restablecer-password",
        json={"token": token, "new_password": "password-nueva-2026"},
    )

    assert r.status_code == 204
    db_session.expire_all()
    usuario = db_session.query(Usuario).filter_by(email="depto-a@consorcio.local").one()
    assert verify_password("password-nueva-2026", usuario.password_hash)


def test_restablecer_baja_el_flag_de_cambio_obligatorio(client, db_session, capsys):
    """Si no se bajara, el usuario resetea su clave y sigue sin poder operar."""
    usuario = db_session.query(Usuario).filter_by(email="depto-a@consorcio.local").one()
    usuario.must_change_password = True
    db_session.commit()

    client.post("/auth/recuperar-password", json={"email": "depto-a@consorcio.local"})
    token = capsys.readouterr().out.split("?token=")[1].split()[0].strip()
    client.post(
        "/auth/restablecer-password",
        json={"token": token, "new_password": "password-nueva-2026"},
    )

    db_session.expire_all()
    assert usuario.must_change_password is False


def test_restablecer_con_token_invalido_responde_400(client):
    r = client.post(
        "/auth/restablecer-password",
        json={"token": "no-existe", "new_password": "password-nueva-2026"},
    )
    assert r.status_code == 400


def test_restablecer_con_password_corta_responde_400(client, capsys):
    client.post("/auth/recuperar-password", json={"email": "depto-a@consorcio.local"})
    token = capsys.readouterr().out.split("?token=")[1].split()[0].strip()

    r = client.post(
        "/auth/restablecer-password", json={"token": token, "new_password": "corta"}
    )
    assert r.status_code == 400


def test_despues_de_restablecer_se_puede_entrar_con_la_nueva(client, capsys):
    client.post("/auth/recuperar-password", json={"email": "depto-a@consorcio.local"})
    token = capsys.readouterr().out.split("?token=")[1].split()[0].strip()
    client.post(
        "/auth/restablecer-password",
        json={"token": token, "new_password": "password-nueva-2026"},
    )

    r = client.post(
        "/auth/login",
        json={"email": "depto-a@consorcio.local", "password": "password-nueva-2026"},
    )
    assert r.status_code == 200
```

Verificar el email exacto del depto en `tests/conftest.py` (`_seed`) antes de escribirlos.

- [ ] **Step 2: Correr y verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_recuperar_password.py -q`
Expected: FAIL — los endpoints no existen (404).

- [ ] **Step 3: Agregar los schemas**

En `backend/schemas.py`, junto a `CambiarPasswordIn`:

```python
class RecuperarPasswordIn(BaseModel):
    email: EmailStr


class RestablecerPasswordIn(BaseModel):
    token: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)
```

Verificar que `EmailStr` esté importado (`LoginIn` ya debería usarlo); si no, usar `str` con la misma validación que use `LoginIn`.

- [ ] **Step 4: Agregar los endpoints**

En `backend/routers/auth.py`:

```python
@router.post(
    "/recuperar-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Pedir un link para restablecer la contraseña",
)
def recuperar_password(payload: RecuperarPasswordIn, db: Session = Depends(get_db)) -> dict:
    """Siempre responde 202, exista o no la cuenta.

    Cualquier ramificación observable —código distinto, mensaje distinto, o un
    error cuando falla el envío— convierte este formulario en un verificador de
    qué emails están registrados en el sistema.
    """
    usuario = db.scalar(select(Usuario).where(Usuario.email == payload.email))

    if (
        usuario is not None
        and usuario.activa
        and _administracion_activa_para(db, usuario)
    ):
        claro = emitir_token(db, usuario)
        if claro is not None:  # None = superó el límite por hora
            link = f"{get_settings().FRONTEND_URL}/restablecer-password?token={claro}"
            enviar_email(
                to=usuario.email,
                subject="Restablecer tu contraseña",
                body=(
                    "Hola,\n\n"
                    "Pediste restablecer tu contraseña. Entrá acá para elegir una nueva:\n\n"
                    f"{link}\n\n"
                    f"El link vence en {get_settings().RECUPERACION_TOKEN_MINUTOS} minutos "
                    "y se puede usar una sola vez.\n\n"
                    "Si no fuiste vos, ignorá este mensaje: tu contraseña no cambió.\n\n"
                    "Administración."
                ),
            )

    return {"detail": "Si el email está registrado, te va a llegar un mensaje."}


@router.post(
    "/restablecer-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Restablecer la contraseña con el token del email",
    response_class=Response,
)
def restablecer_password(
    payload: RestablecerPasswordIn, db: Session = Depends(get_db)
) -> Response:
    usuario = canjear_token(db, payload.token)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El link es inválido o venció. Pedí uno nuevo.",
        )

    usuario.password_hash = hash_password(payload.new_password)
    # Sin esto, quien tenía cambio obligatorio pendiente resetea su clave y
    # sigue recibiendo 403 en todo endpoint operacional.
    usuario.must_change_password = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Agregar los imports: `RecuperarPasswordIn`, `RestablecerPasswordIn` de `..schemas`; `emitir_token`, `canjear_token` de `..recuperacion`; `enviar_email` de `..mail_service`.

- [ ] **Step 5: Correr los tests y el suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_recuperar_password.py -q` → PASS
Run: `./.venv/Scripts/python.exe -m pytest -q` → verde

- [ ] **Step 6: Documentar en OpenAPI**

Agregar a `openapi.yaml` los dos paths con `security: []` (son públicos) y los schemas `RecuperarPasswordIn` / `RestablecerPasswordIn`. Dejar escrito en la descripción del primero **por qué** responde siempre 202.

- [ ] **Step 7: Commit**

```bash
git add backend/schemas.py backend/routers/auth.py tests/test_recuperar_password.py openapi.yaml
git commit -m "feat: endpoints publicos para pedir y canjear el link de recuperacion"
```

---

### Task 4: Las dos pantallas

**Files:**
- Create: `frontend/src/screens/RecuperarPassword.jsx`
- Create: `frontend/src/screens/RestablecerPassword.jsx`
- Modify: `frontend/src/api/auth.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/screens/Login.jsx` (el enlace)
- Create: `frontend/src/screens/RecuperarPassword.test.jsx`

**Interfaces:**
- Consumes: los dos endpoints de la Tarea 3.
- Produces: rutas públicas `/recuperar-password` y `/restablecer-password`.

- [ ] **Step 1: Escribir el test de la pantalla (falla)**

```jsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import RecuperarPassword from "./RecuperarPassword";

vi.mock("../api/auth", () => ({ recuperarPassword: vi.fn().mockResolvedValue({ ok: true }) }));

describe("RecuperarPassword", () => {
  it("muestra el mismo mensaje sin decir si el email existe", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><RecuperarPassword /></MemoryRouter>);

    await user.type(screen.getByLabelText(/email/i), "cualquiera@ejemplo.com");
    await user.click(screen.getByRole("button", { name: /enviar/i }));

    expect(await screen.findByText(/si el email está registrado/i)).toBeInTheDocument();
  });
});
```

Antes de escribirlo, mirar un test de pantalla existente (por ejemplo `frontend/src/screens/*.test.jsx` si hay, o `frontend/src/components/BannerDemo.test.jsx`) para copiar el patrón exacto de render y de mocks que usa el proyecto.

- [ ] **Step 2: Correr y verificar que falla**

Run (desde `frontend/`): `npm test -- --run RecuperarPassword`

- [ ] **Step 3: Agregar las llamadas a la API**

En `frontend/src/api/auth.js`:

```javascript
export function recuperarPassword(email) {
  return apiFetch("/auth/recuperar-password", { method: "POST", body: { email } });
}

export function restablecerPassword(token, newPassword) {
  return apiFetch("/auth/restablecer-password", {
    method: "POST",
    body: { token, new_password: newPassword },
  });
}
```

Verificar la forma exacta que espera `apiFetch` para el body mirando otra llamada del mismo archivo.

- [ ] **Step 4: Crear las dos pantallas**

`RecuperarPassword.jsx`: un `<form>` con un input de email y un botón. Al enviar, llama y **siempre** muestra el mismo mensaje —"Si el email está registrado, te va a llegar un mensaje"— sin importar la respuesta. Un enlace para volver al login.

`RestablecerPassword.jsx`: lee el token de la query string (`useSearchParams`). Un `<form>` con contraseña nueva y confirmación; valida en el cliente que coincidan y que tenga 8 caracteres como mínimo, antes de llamar. Con 400 del servidor muestra el `detail` y ofrece pedir un link nuevo. Con éxito, redirige al login con un cartel de "listo, entrá con tu contraseña nueva".

Seguir `.claude/rules/frontend.md`: HTML semántico, `<form onSubmit>` con `preventDefault`, estado en `useState`, colores por variables CSS, usable a 375px.

- [ ] **Step 5: Enlazar desde el login y registrar las rutas**

En `Login.jsx`, un enlace "¿Olvidaste tu contraseña?" a `/recuperar-password`.

En `App.jsx`, junto a `<Route path="/login" ...>` (línea 121), que son las rutas públicas:

```jsx
<Route path="/recuperar-password" element={<RecuperarPassword />} />
<Route path="/restablecer-password" element={<RestablecerPassword />} />
```

- [ ] **Step 6: Correr los tests del frontend**

Run (desde `frontend/`): `npm test -- --run`
Expected: verde.

- [ ] **Step 7: Verificar a ojo el circuito completo**

Levantar backend y frontend. Pedir recuperación con un email real del seed; leer el link en la consola del backend; abrirlo; elegir contraseña nueva; entrar con ella. Probar además que el mismo link ya no funciona una segunda vez.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat: pantallas para recuperar y restablecer la contraseña"
```

---

### Task 5: Configuración y documentación

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Documentar las variables**

```
# --- Recuperación de contraseña ---
# Base del link que se manda por email. En producción, el dominio real del
# frontend: si apunta a localhost, el link no le sirve a nadie.
FRONTEND_URL=http://localhost:5173
RECUPERACION_TOKEN_MINUTOS=60
RECUPERACION_MAX_POR_HORA=3
```

- [ ] **Step 2: Documentar el circuito en el README**

Una sección "Recuperación de contraseña" con: el circuito de dos pasos; que la respuesta es siempre 202 y por qué; que en la base va el hash y no el token; que sin SMTP configurado el link se imprime en la consola del backend, que es como se prueba en desarrollo; y el recordatorio de que `FRONTEND_URL` tiene que ser el dominio real en producción.

- [ ] **Step 3: Verificación final**

```bash
./.venv/Scripts/python.exe -m pytest -q
cd frontend && npm test -- --run
```

- [ ] **Step 4: Commit**

```bash
git add .env.example README.md
git commit -m "docs: documentar la recuperacion de contraseña y su configuracion"
```

---

## Self-Review

**Cobertura de la spec (Frente 3):**

| Requisito de la spec | Tarea |
|---|---|
| Tabla de tokens: hash, vencimiento, `usado_at`, `usuario_id` | 1 |
| `POST /auth/recuperar-password` público, siempre 202, con límite de frecuencia | 2 y 3 |
| `POST /auth/restablecer-password`: vencimiento, un solo uso, baja `must_change_password` | 2 y 3 |
| Invalidar el resto de los tokens del usuario | 2 |
| Frontend: dos pantallas enlazadas desde el login | 4 |
| Tests: token vencido, reusado, email inexistente, límite, token no en claro | 1, 2, 3 |
| Alta del proveedor de correo y variables `SMTP_*` | Fuera del código: es configuración de cuenta, documentada en la Tarea 5 |

**Desvío consciente respecto de la spec:** la spec pedía límite de frecuencia "por email e IP". Se implementa **sólo por usuario**, contra la base. El límite por IP necesitaría estado compartido entre instancias o un middleware aparte, y sin él el ataque que queda —pedir links para muchas cuentas distintas desde una misma IP— no revela nada (la respuesta es siempre igual) y sólo genera correo. Queda anotado como pendiente si aparece abuso real.

**Riesgo residual conocido:** restablecer la contraseña **no cierra las sesiones abiertas** con la contraseña vieja. La lista de revocación del proyecto trabaja por `jti` y no hay índice de los jti vigentes de un usuario. Si el caso de uso es "me robaron la cuenta", eso hace falta; para "me olvidé la clave", que es el caso que motiva este frente, no. Anotado, no resuelto.

**Consistencia de nombres:** `emitir_token(db, usuario) -> str | None` y `canjear_token(db, token_claro) -> Usuario | None` se definen en la Tarea 2 y se consumen con esas firmas en la 3. `hashear(token_claro)` se define y se usa en la 2. `RecuperarPasswordIn{email}` y `RestablecerPasswordIn{token, new_password}` se definen en la 3 y es lo que arma `frontend/src/api/auth.js` en la 4.

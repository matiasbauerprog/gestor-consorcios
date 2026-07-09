"""POST /padron/importar: alta masiva unificada de deptos + usuarios en 1 CSV.

Cada fila representa una combinación (depto, usuario). Si el código de depto se
repite en varias filas, el depto se crea una sola vez (reutilizado en filas
subsecuentes). Si el email queda vacío se crea solo el depto — útil para deptos
sin habitantes o cuando se quiere solo poblar el listado antes de asignar
credenciales.
"""
import csv
import io
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Departamento, Rol, Usuario
from ..schemas import PadronImportarResultado, PadronImportItemOut
from ..security import hash_password
from ..tenant import get_consorcio_activo

router = APIRouter(prefix="/padron", tags=["Administracion"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COLUMNAS_REQUERIDAS = {"codigo", "ubicacion", "email"}


def _generar_password() -> str:
    return secrets.token_urlsafe(12)


@router.post(
    "/importar",
    response_model=PadronImportarResultado,
    status_code=status.HTTP_200_OK,
    summary="Alta masiva unificada de departamentos y usuarios desde CSV",
)
def importar_padron(
    file: UploadFile,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> PadronImportarResultado:
    contenido = file.file.read()
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "csv_encoding_invalido")

    reader = csv.DictReader(io.StringIO(texto))
    if reader.fieldnames is None or not _COLUMNAS_REQUERIDAS.issubset(reader.fieldnames):
        raise HTTPException(400, "csv_columnas_faltantes")

    filas = list(reader)
    if not filas:
        raise HTTPException(400, "csv_sin_filas")

    # Deptos existentes en el consorcio, por código.
    deptos_por_codigo: dict[str, Departamento] = {
        d.codigo: d for d in db.query(Departamento).filter(Departamento.consorcio_id == cid).all()
    }
    codigos_creados_en_este_batch: set[str] = set()
    emails_creados_en_este_batch: set[str] = set()

    resultados: list[PadronImportItemOut] = []

    for fila in filas:
        codigo = (fila.get("codigo") or "").strip()
        ubicacion_raw = (fila.get("ubicacion") or "").strip()
        ubicacion = ubicacion_raw or None
        email = (fila.get("email") or "").strip().lower()

        item = PadronImportItemOut(
            codigo=codigo,
            ubicacion=ubicacion,
            email=email or None,
            depto_status="error",
            usuario_status="error",
        )

        # 1. Validar y resolver depto.
        if not codigo or len(codigo) > 32:
            item.error = "codigo_invalido"
            resultados.append(item)
            continue

        depto = deptos_por_codigo.get(codigo)
        if depto is None:
            depto = Departamento(consorcio_id=cid, codigo=codigo, descripcion=ubicacion)
            db.add(depto)
            db.flush()
            deptos_por_codigo[codigo] = depto
            codigos_creados_en_este_batch.add(codigo)
            item.depto_status = "creado"
        else:
            item.depto_status = "reutilizado"

        # 2. Resolver usuario (opcional).
        if not email:
            item.usuario_status = "sin_usuario"
            resultados.append(item)
            continue

        if not _EMAIL_RE.match(email):
            item.usuario_status = "error"
            item.error = "email_invalido"
            resultados.append(item)
            continue

        if email in emails_creados_en_este_batch:
            item.usuario_status = "error"
            item.error = "email_duplicado"
            resultados.append(item)
            continue

        existe = db.scalar(select(Usuario.id).where(Usuario.email == email))
        if existe is not None:
            item.usuario_status = "error"
            item.error = "email_duplicado"
            resultados.append(item)
            continue

        password = _generar_password()
        u = Usuario(
            email=email,
            password_hash=hash_password(password),
            rol=Rol.departamento,
            departamento_id=depto.id,
            must_change_password=True,
        )
        db.add(u)
        db.flush()
        emails_creados_en_este_batch.add(email)

        item.usuario_status = "creado"
        item.password_generada = password
        resultados.append(item)

    db.commit()
    return PadronImportarResultado(resultados=resultados)

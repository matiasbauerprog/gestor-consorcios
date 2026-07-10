from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import (
    ClaseProrrateo,
    CoeficienteDepartamento,
    Comprobante,
    Departamento,
    Expensa,
    Gasto,
    MovimientoCuenta,
    Peticion,
    Rol,
    Usuario,
)
from ..tenant import get_consorcio_activo
from ..schemas import (
    CoeficienteOut,
    CoeficientesReemplazar,
    DepartamentoActualizar,
    DepartamentoCrear,
    DepartamentoOut,
)

router = APIRouter(prefix="/departamentos", tags=["Administracion"])


@router.get(
    "",
    response_model=list[DepartamentoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar departamentos",
)
def listar_departamentos(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> list[Departamento]:
    stmt = select(Departamento).where(Departamento.consorcio_id == cid).order_by(Departamento.codigo.asc())
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=DepartamentoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un departamento (unidad funcional)",
)
def crear_departamento(
    payload: DepartamentoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Departamento:
    duplicado = db.scalar(
        select(Departamento.id).where(
            Departamento.consorcio_id == cid,
            Departamento.codigo == payload.codigo,
        )
    )
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un departamento con ese código.",
        )

    departamento = Departamento(
        consorcio_id=cid,
        codigo=payload.codigo,
        descripcion=payload.descripcion,
    )
    db.add(departamento)
    db.commit()
    db.refresh(departamento)
    return departamento


@router.patch(
    "/{departamento_id}",
    response_model=DepartamentoOut,
    status_code=status.HTTP_200_OK,
    summary="Editar un departamento",
)
def actualizar_departamento(
    departamento_id: int,
    payload: DepartamentoActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Departamento:
    departamento = db.get(Departamento, departamento_id)
    if departamento is None or departamento.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(departamento, campo, valor)

    db.commit()
    db.refresh(departamento)
    return departamento


@router.get(
    "/{departamento_id}/coeficientes",
    response_model=list[CoeficienteOut],
    status_code=status.HTTP_200_OK,
    summary="Listar coeficientes de prorrateo del departamento",
)
def listar_coeficientes(
    departamento_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> list[CoeficienteOut]:
    depto = db.get(Departamento, departamento_id)
    if depto is None or depto.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento solicitado no existe.",
        )

    stmt = (
        select(CoeficienteDepartamento, ClaseProrrateo)
        .join(ClaseProrrateo, CoeficienteDepartamento.clase_prorrateo_id == ClaseProrrateo.id)
        .where(CoeficienteDepartamento.departamento_id == departamento_id)
        .order_by(ClaseProrrateo.codigo.asc())
    )
    return [
        CoeficienteOut(
            clase_prorrateo_id=clase.id,
            codigo=clase.codigo,
            nombre=clase.nombre,
            porcentaje=coef.porcentaje,
        )
        for coef, clase in db.execute(stmt).all()
    ]


@router.put(
    "/{departamento_id}/coeficientes",
    response_model=list[CoeficienteOut],
    status_code=status.HTTP_200_OK,
    summary="Reemplazar todos los coeficientes del departamento",
)
def reemplazar_coeficientes(
    departamento_id: int,
    payload: CoeficientesReemplazar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> list[CoeficienteOut]:
    depto = db.get(Departamento, departamento_id)
    if depto is None or depto.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento solicitado no existe.",
        )

    ids_pedidos = {item.clase_prorrateo_id for item in payload.coeficientes}
    if ids_pedidos:
        existentes = db.scalars(
            select(ClaseProrrateo.id).where(
                ClaseProrrateo.consorcio_id == cid,
                ClaseProrrateo.id.in_(ids_pedidos),
            )
        ).all()
        faltantes = ids_pedidos - set(existentes)
        if faltantes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clases inexistentes: {sorted(faltantes)}",
            )

    db.query(CoeficienteDepartamento).filter(
        CoeficienteDepartamento.departamento_id == departamento_id
    ).delete(synchronize_session=False)

    for item in payload.coeficientes:
        db.add(
            CoeficienteDepartamento(
                consorcio_id=cid,
                departamento_id=departamento_id,
                clase_prorrateo_id=item.clase_prorrateo_id,
                porcentaje=item.porcentaje,
            )
        )
    db.commit()

    return listar_coeficientes(departamento_id, db, _user, cid)


def _depto_tiene_actividad(db: Session, departamento_id: int) -> bool:
    """True si el depto tiene datos que forzarían un FK RESTRICT al borrar."""
    checks = [
        db.query(Usuario.id).filter(Usuario.departamento_id == departamento_id),
        db.query(Peticion.id).filter(Peticion.departamento_id == departamento_id),
        db.query(Expensa.id).filter(Expensa.departamento_id == departamento_id),
        db.query(Comprobante.id).filter(Comprobante.departamento_id == departamento_id),
        db.query(MovimientoCuenta.id).filter(MovimientoCuenta.departamento_id == departamento_id),
        db.query(Gasto.id).filter(Gasto.departamento_id == departamento_id),
    ]
    return any(q.first() is not None for q in checks)


@router.delete(
    "/{departamento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un departamento",
    response_class=Response,
)
def eliminar_departamento(
    departamento_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Response:
    depto = db.get(Departamento, departamento_id)
    if depto is None or depto.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento solicitado no existe.",
        )
    if _depto_tiene_actividad(db, departamento_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="departamento_con_actividad",
        )
    # Coeficientes son configuración: cascade manual antes del delete.
    db.query(CoeficienteDepartamento).filter(
        CoeficienteDepartamento.departamento_id == departamento_id
    ).delete(synchronize_session=False)
    db.delete(depto)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)



"""PUT /coeficientes: reemplaza atómicamente toda la matriz de coeficientes
del consorcio activo. Diseñado para el flujo de setup del padrón (matriz
deptos × clases editada en una sola pantalla)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import ClaseProrrateo, CoeficienteDepartamento, Departamento, Rol
from ..schemas import CoeficientesBulkIn
from ..tenant import get_consorcio_activo

router = APIRouter(prefix="/coeficientes", tags=["Administracion"])


@router.put(
    "",
    status_code=status.HTTP_200_OK,
    summary="Reemplazar toda la matriz de coeficientes del consorcio",
)
def reemplazar_matriz(
    payload: CoeficientesBulkIn,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> dict:
    depto_ids = {c.departamento_id for c in payload.coeficientes}
    clase_ids = {c.clase_prorrateo_id for c in payload.coeficientes}

    if depto_ids:
        deptos_ok = {
            d for (d,) in db.query(Departamento.id).filter(
                Departamento.consorcio_id == cid,
                Departamento.id.in_(depto_ids),
            ).all()
        }
        faltantes = depto_ids - deptos_ok
        if faltantes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Departamentos inexistentes en el consorcio: {sorted(faltantes)}",
            )

    if clase_ids:
        clases_ok = {
            c for (c,) in db.query(ClaseProrrateo.id).filter(
                ClaseProrrateo.consorcio_id == cid,
                ClaseProrrateo.id.in_(clase_ids),
            ).all()
        }
        faltantes = clase_ids - clases_ok
        if faltantes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clases inexistentes en el consorcio: {sorted(faltantes)}",
            )

    # Reemplazo atómico: borrar los del consorcio activo y volver a insertar.
    db.query(CoeficienteDepartamento).filter(
        CoeficienteDepartamento.consorcio_id == cid
    ).delete(synchronize_session=False)

    for item in payload.coeficientes:
        db.add(CoeficienteDepartamento(
            consorcio_id=cid,
            departamento_id=item.departamento_id,
            clase_prorrateo_id=item.clase_prorrateo_id,
            porcentaje=item.porcentaje,
        ))

    db.commit()
    return {"cantidad": len(payload.coeficientes)}

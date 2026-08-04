"""Devengamiento del recargo por mora — el salto del primer al segundo vencimiento.

El movimiento `expensa_emitida` se emite siempre por `monto_primer_vencimiento`,
así que sin este módulo el recargo no existiría en la cuenta corriente: el saldo
quedaría por debajo del pendiente real y un pago con recargo dejaría un crédito
a favor fantasma.

El recargo se gana el día del primer vencimiento. Si a esa fecha la expensa tenía
saldo, corresponde, y no se revierte aunque el departamento pague después — por
eso la evaluación mira la foto de esa fecha y no la de hoy: el resultado es
estable y no cambia retroactivamente.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .cuenta_corriente import calcular_estado_cuenta
from .models import Expensa, MovimientoCuenta, TipoMovimiento


def devengar_recargos(
    db: Session, departamento_id: int, hoy: date | None = None
) -> list[MovimientoCuenta]:
    """Emite el recargo de las expensas del depto que vencieron impagas.

    Idempotente: una expensa que ya tiene su movimiento de recargo se saltea.
    No hace commit — el llamador decide la transacción.
    """
    hoy = hoy or date.today()

    expensas = list(
        db.scalars(
            select(Expensa)
            .where(
                Expensa.departamento_id == departamento_id,
                Expensa.fecha_primer_vencimiento < hoy,
            )
            .order_by(Expensa.fecha_primer_vencimiento.asc(), Expensa.id.asc())
        ).all()
    )
    if not expensas:
        return []

    ya_recargadas = set(
        db.scalars(
            select(MovimientoCuenta.expensa_id).where(
                MovimientoCuenta.departamento_id == departamento_id,
                MovimientoCuenta.tipo == TipoMovimiento.recargo,
            )
        ).all()
    )

    nuevos: list[MovimientoCuenta] = []
    for e in expensas:
        if e.id in ya_recargadas:
            continue
        recargo = round(e.monto_segundo_vencimiento - e.monto_primer_vencimiento, 2)
        if recargo <= 0.005:
            continue
        # La foto al día del vencimiento: calcular_estado_cuenta ignora los
        # movimientos posteriores, así que un pago tardío no borra el recargo.
        foto = calcular_estado_cuenta(
            db, departamento_id, hoy=e.fecha_primer_vencimiento
        )
        calc = foto.por_expensa.get(e.id)
        if calc is None or calc.monto_pendiente <= 0.005:
            continue
        mov = MovimientoCuenta(
            consorcio_id=e.consorcio_id,
            departamento_id=departamento_id,
            fecha=e.fecha_primer_vencimiento,
            tipo=TipoMovimiento.recargo,
            descripcion=f"Recargo por mora — expensa {e.periodo}",
            monto=recargo,
            expensa_id=e.id,
        )
        db.add(mov)
        nuevos.append(mov)

    if nuevos:
        db.flush()
    return nuevos

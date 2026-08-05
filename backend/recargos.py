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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .cuenta_corriente import calcular_estado_cuenta
from .models import Expensa, MovimientoCuenta, TipoMovimiento


def _devengar(
    db: Session, departamento_id: int, hoy: date | None
) -> tuple[list[MovimientoCuenta], list[Expensa]]:
    """Núcleo del devengamiento. Devuelve (movimientos nuevos, expensas evaluadas).

    Cada expensa se evalúa UNA SOLA VEZ: se la marca con `recargo_evaluado`
    haya emitido recargo o no. Sin esa marca, las expensas que no devengan
    (pagadas antes del vencimiento, o consorcios sin recargo configurado)
    volverían a costar un `calcular_estado_cuenta` completo en cada lectura,
    para siempre y acumulando un mes por período.

    No hace commit — el llamador decide la transacción.
    """
    hoy = hoy or date.today()

    expensas = list(
        db.scalars(
            select(Expensa)
            .where(
                Expensa.departamento_id == departamento_id,
                Expensa.fecha_primer_vencimiento < hoy,
                Expensa.recargo_evaluado == False,  # noqa: E712
            )
            .order_by(Expensa.fecha_primer_vencimiento.asc(), Expensa.id.asc())
        ).all()
    )
    if not expensas:
        return [], []

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
        # La decisión se toma acá y no se vuelve a tomar, salga como salga.
        e.recargo_evaluado = True
        # `ya_recargadas` sigue haciendo falta: las expensas que ya tenían su
        # recargo antes de que existiera la columna migran con la marca en 0,
        # y sin esta guarda emitirían un segundo movimiento.
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
        # Savepoint alrededor del INSERT: las guardas de arriba son un
        # chequeo-y-después-inserto, y dos lecturas concurrentes (FastAPI
        # atiende los endpoints sync en un threadpool) lo pasan las dos. La
        # restricción única decide, y el que pierde descarta su propio
        # movimiento sin voltear la transacción entera.
        savepoint = db.begin_nested()
        db.add(mov)
        try:
            db.flush()
        except IntegrityError:
            savepoint.rollback()
            # El recargo ya existe: lo emitió el otro request. La marca se
            # reafirma por si el savepoint la revirtió.
            e.recargo_evaluado = True
            continue
        savepoint.commit()
        nuevos.append(mov)

    db.flush()
    return nuevos, expensas


def devengar_recargos_y_marcar(
    db: Session, departamento_id: int, hoy: date | None = None
) -> bool:
    """Emite el recargo de las expensas del depto que vencieron impagas y
    devuelve si quedó algo por commitear.

    Es el punto de entrada de las lecturas. La marca `recargo_evaluado` se
    escribe también cuando NO se emite recargo, y esa escritura hay que
    persistirla: `get_db` cierra la sesión sin commitear, así que un llamador
    que sólo mire los movimientos creados perdería la marca y volvería a
    evaluar la misma expensa en cada request — justo lo que la marca evita.
    """
    nuevos, evaluadas = _devengar(db, departamento_id, hoy)
    return bool(nuevos or evaluadas)

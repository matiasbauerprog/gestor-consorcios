"""
Migración idempotente a multitenant.

- Crea administracion "Demo" + consorcio "Demo" si no existen.
- Adopta datos existentes bajo esos IDs (tasks futuras).
- Idempotente: correr N veces es equivalente a correr 1 vez.

Uso: python -m backend.migrate_multitenant
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import SessionLocal
from .models import Administracion, Consorcio

logger = logging.getLogger(__name__)


def ya_migrado(db: Session) -> bool:
    """Devuelve True si ya existe al menos una administración."""
    return db.query(Administracion).first() is not None


def _tabla_existe(db: Session, nombre: str) -> bool:
    r = db.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": nombre},
    ).first()
    return r is not None


def _crear_demo(db: Session) -> tuple[Administracion, Consorcio]:
    admin = Administracion(
        razon_social="Administración Demo",
        cuit="30-00000000-0",
        email_contacto="demo@example.com",
    )
    db.add(admin)
    db.flush()

    cfg = None
    if _tabla_existe(db, "configuracion_consorcio"):
        # Leemos con raw SQL — el modelo Python ya fue eliminado
        row = db.execute(text(
            "SELECT consorcio_nombre, consorcio_domicilio, consorcio_cuit, "
            "  consorcio_convenio_suterh, admin_nombre, admin_domicilio, admin_email, "
            "  admin_telefono, admin_cuit, admin_rpa, admin_situacion_fiscal, "
            "  banco_titular, banco_nombre, banco_sucursal, banco_numero_cuenta, "
            "  banco_cbu, banco_alias, dia_primer_vencimiento, dias_entre_vencimientos, "
            "  recargo_segundo_vencimiento_pct, tasa_interes_mensual_pct, "
            "  caja_default_pagos_id, reportes_visibles_a_depto "
            "FROM configuracion_consorcio LIMIT 1"
        )).first()
        if row is not None:
            cfg = row._mapping

    if cfg is not None:
        c = Consorcio(
            administracion_id=admin.id,
            nombre=cfg["consorcio_nombre"],
            consorcio_domicilio=cfg["consorcio_domicilio"],
            consorcio_cuit=cfg["consorcio_cuit"],
            consorcio_convenio_suterh=cfg["consorcio_convenio_suterh"],
            admin_nombre=cfg["admin_nombre"],
            admin_domicilio=cfg["admin_domicilio"],
            admin_email=cfg["admin_email"],
            admin_telefono=cfg["admin_telefono"],
            admin_cuit=cfg["admin_cuit"],
            admin_rpa=cfg["admin_rpa"],
            admin_situacion_fiscal=cfg["admin_situacion_fiscal"],
            banco_titular=cfg["banco_titular"],
            banco_nombre=cfg["banco_nombre"],
            banco_sucursal=cfg["banco_sucursal"],
            banco_numero_cuenta=cfg["banco_numero_cuenta"],
            banco_cbu=cfg["banco_cbu"],
            banco_alias=cfg["banco_alias"],
            dia_primer_vencimiento=cfg["dia_primer_vencimiento"],
            dias_entre_vencimientos=cfg["dias_entre_vencimientos"],
            recargo_segundo_vencimiento_pct=cfg["recargo_segundo_vencimiento_pct"],
            tasa_interes_mensual_pct=cfg["tasa_interes_mensual_pct"],
            caja_default_pagos_id=cfg["caja_default_pagos_id"],
            reportes_visibles_a_depto=cfg["reportes_visibles_a_depto"],
        )
    else:
        c = Consorcio(
            administracion_id=admin.id,
            nombre="Consorcio Demo",
            consorcio_domicilio="Sin domicilio",
            consorcio_cuit="30-00000000-0",
            admin_nombre="Demo",
            admin_domicilio="Sin domicilio",
            admin_email="demo@example.com",
            admin_telefono="0",
            admin_cuit="30-00000000-0",
            admin_rpa="0000",
            admin_situacion_fiscal="Monotributo",
            banco_titular="Demo",
            banco_nombre="Banco Demo",
            banco_numero_cuenta="0-0",
            banco_cbu="0" * 22,
        )
    db.add(c)
    db.flush()
    return admin, c


def _adoptar_tabla(db: Session, tabla: str, cid: int) -> None:
    """Agrega columna consorcio_id (si falta) y setea todas las filas al cid."""
    cols = db.execute(text(f"PRAGMA table_info({tabla})")).all()
    tiene_col = any(c[1] == "consorcio_id" for c in cols)
    if not tiene_col:
        db.execute(text(f"ALTER TABLE {tabla} ADD COLUMN consorcio_id INTEGER"))
    db.execute(
        text(f"UPDATE {tabla} SET consorcio_id = :cid WHERE consorcio_id IS NULL"),
        {"cid": cid},
    )
    db.execute(text(
        f"CREATE INDEX IF NOT EXISTS ix_{tabla}_consorcio_id ON {tabla}(consorcio_id)"
    ))


def migrar(db: Session) -> None:
    if ya_migrado(db):
        logger.info("Ya migrado a multitenant, nada que hacer.")
        return

    admin, consorcio = _crear_demo(db)
    logger.info(f"Creados admin #{admin.id} y consorcio #{consorcio.id}")

    _adoptar_tabla(db, "departamentos", consorcio.id)
    logger.info(f"Tabla departamentos adoptada bajo consorcio #{consorcio.id}")

    GRUPO_EXPENSAS = ("expensas", "expensa_detalle", "movimientos_cuenta",
                      "comprobantes", "periodos_cerrados")
    for tabla in GRUPO_EXPENSAS:
        _adoptar_tabla(db, tabla, consorcio.id)
        logger.info(f"Adoptada tabla {tabla} bajo consorcio #{consorcio.id}")

    GRUPO_GASTOS = ("gastos", "gastos_habituales")
    for tabla in GRUPO_GASTOS:
        _adoptar_tabla(db, tabla, consorcio.id)
        logger.info(f"Adoptada tabla {tabla} bajo consorcio #{consorcio.id}")

    GRUPO_TAREAS = ("peticiones", "trabajos", "trabajos_recurrentes", "presupuestos")
    for tabla in GRUPO_TAREAS:
        _adoptar_tabla(db, tabla, consorcio.id)
        logger.info(f"Adoptada tabla {tabla} bajo consorcio #{consorcio.id}")

    GRUPO_COMUNIDAD = ("comunicados", "amenities", "reservas")
    for tabla in GRUPO_COMUNIDAD:
        _adoptar_tabla(db, tabla, consorcio.id)
        logger.info(f"Adoptada tabla {tabla} bajo consorcio #{consorcio.id}")

    GRUPO_TESORERIA = ("cajas", "movimientos_caja", "transferencias_caja")
    for tabla in GRUPO_TESORERIA:
        _adoptar_tabla(db, tabla, consorcio.id)
        logger.info(f"Adoptada tabla {tabla} bajo consorcio #{consorcio.id}")

    GRUPO_CATALOGOS = ("clases_prorrateo", "coeficientes_departamento", "proveedores")
    for tabla in GRUPO_CATALOGOS:
        _adoptar_tabla(db, tabla, consorcio.id)
        logger.info(f"Adoptada tabla {tabla} bajo consorcio #{consorcio.id}")

    GRUPO_PERSONAL = ("empleados", "haberes", "conceptos_liquidacion",
                      "liquidaciones_empleado", "liquidaciones_haber", "liquidaciones_detalle")
    for tabla in GRUPO_PERSONAL:
        _adoptar_tabla(db, tabla, consorcio.id)
        logger.info(f"Adoptada tabla {tabla} bajo consorcio #{consorcio.id}")

    _adoptar_tabla(db, "notificaciones", consorcio.id)
    logger.info(f"Adoptada tabla notificaciones bajo consorcio #{consorcio.id}")

    # Asignar administracion_id a todos los usuarios con rol administracion
    db.execute(
        text("UPDATE usuarios SET administracion_id = :aid WHERE rol = 'administracion'"),
        {"aid": admin.id},
    )
    logger.info(f"Usuarios administracion asignados al tenant #{admin.id}")

    # Drop configuracion_consorcio (ya migrada a Consorcio) si existe
    if _tabla_existe(db, "configuracion_consorcio"):
        db.execute(text("DROP TABLE configuracion_consorcio"))
        logger.info("Tabla configuracion_consorcio eliminada")

    db.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        migrar(db)


if __name__ == "__main__":
    main()

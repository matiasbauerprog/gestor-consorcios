import logging
import secrets
from datetime import date, timedelta

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    Administracion,
    Amenity,
    Caja,
    CategoriaEmpleado,
    ClaseProrrateo,
    CoeficienteDepartamento,
    ConceptoLiquidacion,
    Consorcio,
    Departamento,
    Empleado,
    EstadoPeticion,
    Expensa,
    ExpensaDetalle,
    FormaPago,
    Gasto,
    GastoHabitual,
    Haber,
    MovimientoCaja,
    MovimientoCuenta,
    PeriodicidadRecurrente,
    Peticion,
    Proveedor,
    Rol,
    Rubro,
    TipoCaja,
    TipoConcepto,
    TipoHaber,
    TipoMovimiento,
    TipoMovimientoCaja,
    TrabajoRecurrente,
    Usuario,
)
from .security import hash_password

logger = logging.getLogger(__name__)


def _resolve_default_password() -> tuple[str, bool]:
    cfg = get_settings().SEED_DEFAULT_PASSWORD
    if cfg:
        return cfg, False
    return secrets.token_urlsafe(12), True


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(Usuario).limit(1)) is not None:
        return

    password, generated = _resolve_default_password()

    # Multitenant: crear administracion + consorcio Demo primero.
    admin_tenant = Administracion(
        id=1,
        razon_social="Administración Demo",
        cuit="30-00000000-0",
        email_contacto="demo@consorcio.local",
    )
    db.add(admin_tenant)
    db.flush()
    consorcio = Consorcio(
        id=1,
        administracion_id=1,
        nombre="Consorcio Demo",
        consorcio_domicilio="PENDIENTE",
        consorcio_cuit="00-00000000-0",
        admin_nombre="PENDIENTE",
        admin_domicilio="PENDIENTE",
        admin_email="pendiente@local",
        admin_telefono="PENDIENTE",
        admin_cuit="00-00000000-0",
        admin_rpa="PENDIENTE",
        admin_situacion_fiscal="PENDIENTE",
        banco_titular="PENDIENTE",
        banco_nombre="PENDIENTE",
        banco_numero_cuenta="PENDIENTE",
        banco_cbu="0000000000000000000000",
    )
    db.add(consorcio)
    db.flush()

    depto_a = Departamento(consorcio_id=1, codigo="UF-1A", descripcion="Piso 1, Unidad A")
    depto_b = Departamento(consorcio_id=1, codigo="UF-2B", descripcion="Piso 2, Unidad B")
    db.add_all([depto_a, depto_b])
    db.flush()

    admin = Usuario(
        email="admin@consorcio.local",
        password_hash=hash_password(password),
        rol=Rol.administracion,
        administracion_id=1,
        departamento_id=None,
    )
    user_a = Usuario(
        email="depto-a@consorcio.local",
        password_hash=hash_password(password),
        rol=Rol.departamento,
        departamento_id=depto_a.id,
    )
    user_b = Usuario(
        email="depto-b@consorcio.local",
        password_hash=hash_password(password),
        rol=Rol.departamento,
        departamento_id=depto_b.id,
    )
    db.add_all([admin, user_a, user_b])
    db.flush()

    # ----- Fase 1: clases de prorrateo -----
    clase_a = ClaseProrrateo(consorcio_id=1, codigo="A", nombre="Expensas ordinarias", activa=True)
    clase_b = ClaseProrrateo(consorcio_id=1, codigo="B", nombre="Expensas extraordinarias", activa=True)
    clase_c = ClaseProrrateo(consorcio_id=1, codigo="C", nombre="Servicios diferenciados", activa=True)
    clase_d = ClaseProrrateo(consorcio_id=1, codigo="D", nombre="Obras de frente", activa=True)
    db.add_all([clase_a, clase_b, clase_c, clase_d])
    db.flush()

    # ----- Fase 1: coeficientes para cada depto (clase A, 50% c/u) -----
    db.add_all([
        CoeficienteDepartamento(
            consorcio_id=1, departamento_id=depto_a.id, clase_prorrateo_id=clase_a.id, porcentaje=50.0
        ),
        CoeficienteDepartamento(
            consorcio_id=1, departamento_id=depto_b.id, clase_prorrateo_id=clase_a.id, porcentaje=50.0
        ),
    ])

    # ----- Fase 1: proveedores de ejemplo -----
    db.add_all([
        Proveedor(consorcio_id=1, razon_social="Limpieza S.A.", nombre_fantasia="Limpieza", cuit="30-11111111-1"),
        Proveedor(consorcio_id=1, razon_social="Ascensores SRL", nombre_fantasia="Ascensores", cuit="30-22222222-2"),
        Proveedor(consorcio_id=1, razon_social="Seguros del Hogar", nombre_fantasia="SeguHogar", cuit="30-33333333-3"),
        Proveedor(consorcio_id=1, razon_social="Banco Río", nombre_fantasia="Banco", cuit="30-44444444-4"),
        Proveedor(consorcio_id=1, razon_social="Admin Consorcios", nombre_fantasia="Admin", cuit="30-55555555-5"),
    ])
    db.flush()

    # ----- Fase 5: cajas default -----
    caja_banco = Caja(
        id=1, consorcio_id=1, nombre="Banco Provincia", tipo=TipoCaja.banco,
        saldo_inicial=0.0, activa=True,
    )
    caja_chica = Caja(
        id=2, consorcio_id=1, nombre="Caja chica", tipo=TipoCaja.efectivo,
        saldo_inicial=0.0, activa=True,
    )
    caja_fondo = Caja(
        id=3, consorcio_id=1, nombre="Fondo de reparación", tipo=TipoCaja.fondo_reparacion,
        saldo_inicial=0.0, activa=True,
    )
    db.add_all([caja_banco, caja_chica, caja_fondo])
    db.flush()

    # Multitenant: apuntar caja default del consorcio
    consorcio.caja_default_pagos_id = caja_banco.id
    db.flush()

    # ----- Fase 2: plantillas de gastos habituales -----
    # Tomamos proveedores sembrados por id (orden de creación = orden alfabético del seed).
    proveedores_seed = db.scalars(
        select(Proveedor).order_by(Proveedor.id)
    ).all()
    prov_limpieza = proveedores_seed[0]
    prov_ascensor = proveedores_seed[1]
    prov_admin = proveedores_seed[4]

    plantilla_sueldo = GastoHabitual(
        consorcio_id=1,
        nombre="Sueldo encargado",
        rubro=Rubro.sueldos_y_cargas_sociales,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_admin.id,
        concepto="Sueldo mensual del encargado",
        monto=800000.0,
        forma_pago=FormaPago.transferencia,
        caja_id=caja_banco.id,
        activa=True,
    )
    plantilla_limpieza = GastoHabitual(
        consorcio_id=1,
        nombre="Servicio de limpieza",
        rubro=Rubro.abonos_y_servicios,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_limpieza.id,
        concepto="Limpieza mensual de áreas comunes",
        monto=200000.0,
        forma_pago=FormaPago.transferencia,
        caja_id=caja_banco.id,
        activa=True,
    )
    plantilla_ascensor = GastoHabitual(
        consorcio_id=1,
        nombre="Mantenimiento ascensores",
        rubro=Rubro.abonos_y_servicios,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_ascensor.id,
        concepto="Mantenimiento mensual de ascensores",
        monto=50000.0,
        forma_pago=FormaPago.transferencia,
        caja_id=caja_banco.id,
        activa=True,
    )
    db.add_all([plantilla_sueldo, plantilla_limpieza, plantilla_ascensor])
    db.flush()

    # ----- Fase 2: gastos puntuales de ejemplo (período 2026-06) -----
    # Generado a partir de plantilla.
    gasto_1 = Gasto(
        consorcio_id=1,
        periodo="2026-06",
        rubro=Rubro.sueldos_y_cargas_sociales,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_admin.id,
        concepto="Sueldo mensual del encargado",
        monto=800000.0,
        forma_pago=FormaPago.transferencia,
        fecha_pago=date(2026, 6, 1),
        gasto_habitual_id=plantilla_sueldo.id,
        caja_id=caja_banco.id,
    )
    db.add(gasto_1)
    db.flush()
    db.add(MovimientoCaja(
        consorcio_id=1,
        caja_id=caja_banco.id, fecha=gasto_1.fecha_pago,
        tipo=TipoMovimientoCaja.egreso, monto=gasto_1.monto,
        descripcion=gasto_1.concepto or f"Gasto {gasto_1.id}",
        gasto_id=gasto_1.id,
    ))

    # Prorrateable puntual.
    gasto_2 = Gasto(
        consorcio_id=1,
        periodo="2026-06",
        rubro=Rubro.mantenimiento_partes_comunes,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_limpieza.id,
        concepto="Reparación cañería común",
        monto=120000.0,
        forma_pago=FormaPago.transferencia,
        fecha_pago=date(2026, 6, 8),
        caja_id=caja_banco.id,
    )
    db.add(gasto_2)
    db.flush()
    db.add(MovimientoCaja(
        consorcio_id=1,
        caja_id=caja_banco.id, fecha=gasto_2.fecha_pago,
        tipo=TipoMovimientoCaja.egreso, monto=gasto_2.monto,
        descripcion=gasto_2.concepto or f"Gasto {gasto_2.id}",
        gasto_id=gasto_2.id,
    ))

    # Particular a un depto.
    gasto_3 = Gasto(
        consorcio_id=1,
        periodo="2026-06",
        rubro=Rubro.trabajos_reparaciones_unidades,
        departamento_id=depto_a.id,
        proveedor_id=prov_limpieza.id,
        concepto="Arreglo plomería - UF 1A",
        monto=80000.0,
        forma_pago=FormaPago.transferencia,
        fecha_pago=date(2026, 6, 12),
        caja_id=caja_banco.id,
    )
    db.add(gasto_3)
    db.flush()
    db.add(MovimientoCaja(
        consorcio_id=1,
        caja_id=caja_banco.id, fecha=gasto_3.fecha_pago,
        tipo=TipoMovimientoCaja.egreso, monto=gasto_3.monto,
        descripcion=gasto_3.concepto or f"Gasto {gasto_3.id}",
        gasto_id=gasto_3.id,
    ))

    # En cuotas (cuota 1/3 cargada manualmente).
    gasto_4 = Gasto(
        consorcio_id=1,
        periodo="2026-06",
        rubro=Rubro.seguros,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_admin.id,
        concepto="Seguro anual - Cuota 1/3",
        monto=70000.0,
        forma_pago=FormaPago.transferencia,
        fecha_pago=date(2026, 6, 5),
        cuota_actual=1,
        cuota_total=3,
        caja_id=caja_banco.id,
    )
    db.add(gasto_4)
    db.flush()
    db.add(MovimientoCaja(
        consorcio_id=1,
        caja_id=caja_banco.id, fecha=gasto_4.fecha_pago,
        tipo=TipoMovimientoCaja.egreso, monto=gasto_4.monto,
        descripcion=gasto_4.concepto or f"Gasto {gasto_4.id}",
        gasto_id=gasto_4.id,
    ))

    # ----- Fase 3: 4 proveedores institucionales -----
    afip = Proveedor(consorcio_id=1, razon_social="AFIP", nombre_fantasia="AFIP", cuit="30-00000001-7")
    arca = Proveedor(consorcio_id=1, razon_social="ARCA", nombre_fantasia="ARCA", cuit="30-00000002-5")
    fateryh = Proveedor(consorcio_id=1, razon_social="FATERYH", nombre_fantasia="FATERYH", cuit="30-00000003-3")
    suterh_prov = Proveedor(consorcio_id=1, razon_social="SUTERH", nombre_fantasia="SUTERH", cuit="30-00000004-1")
    db.add_all([afip, arca, fateryh, suterh_prov])
    db.flush()

    # ----- Fase 3: proveedor + empleado de ejemplo -----
    prov_empleado = Proveedor(consorcio_id=1, razon_social="Pérez, Juan", nombre_fantasia="Pérez Juan", cuit="20-12345678-9")
    db.add(prov_empleado)
    db.flush()

    empleado_ej = Empleado(
        consorcio_id=1,
        nombre_completo="Juan Pérez",
        cuil="20-12345678-9",
        categoria=CategoriaEmpleado.encargado_permanente_sin_vivienda,
        fecha_ingreso=date(2020, 1, 1),
        fecha_egreso=None,
        sueldo_basico=1000000.0,
        proveedor_id=prov_empleado.id,
        activo=True,
    )
    db.add(empleado_ej)
    db.flush()

    # ----- Fase 3: 6 haberes SUTERH -----
    db.add_all([
        Haber(consorcio_id=1, nombre="Básico", tipo=TipoHaber.porcentaje_sobre_basico, valor_default=100.0, orden=1, activo=True),
        Haber(consorcio_id=1, nombre="Antigüedad", tipo=TipoHaber.porcentaje_sobre_basico, valor_default=1.0, orden=2, activo=True),
        Haber(consorcio_id=1, nombre="Presentismo", tipo=TipoHaber.porcentaje_sobre_basico, valor_default=8.33, orden=3, activo=True),
        Haber(consorcio_id=1, nombre="Adicional vivienda", tipo=TipoHaber.monto_fijo, valor_default=0.0, orden=4, activo=True),
        Haber(consorcio_id=1, nombre="Horas extra 50%", tipo=TipoHaber.cantidad_x_valor, valor_default=0.0, orden=5, activo=True),
        Haber(consorcio_id=1, nombre="Horas extra 100%", tipo=TipoHaber.cantidad_x_valor, valor_default=0.0, orden=6, activo=True),
    ])

    # ----- Fase 3: 12 conceptos SUTERH (paritarias 2026 referencia) -----
    db.add_all([
        # Descuentos (salen del bruto)
        ConceptoLiquidacion(consorcio_id=1, nombre="Jubilación", tipo=TipoConcepto.descuento, porcentaje=11.0, proveedor_id=afip.id, orden=1, activo=True),
        ConceptoLiquidacion(consorcio_id=1, nombre="ISSPJ Ley 19032", tipo=TipoConcepto.descuento, porcentaje=3.0, proveedor_id=afip.id, orden=2, activo=True),
        ConceptoLiquidacion(consorcio_id=1, nombre="OSPERyHA", tipo=TipoConcepto.descuento, porcentaje=2.55, proveedor_id=afip.id, orden=3, activo=True),
        ConceptoLiquidacion(consorcio_id=1, nombre="ANSSAL", tipo=TipoConcepto.descuento, porcentaje=0.45, proveedor_id=afip.id, orden=4, activo=True),
        ConceptoLiquidacion(consorcio_id=1, nombre="Caja Protección Familia", tipo=TipoConcepto.descuento, porcentaje=1.0, proveedor_id=fateryh.id, orden=5, activo=True),
        ConceptoLiquidacion(consorcio_id=1, nombre="Cuota Sindical SUTERH", tipo=TipoConcepto.descuento, porcentaje=2.0, proveedor_id=suterh_prov.id, orden=6, activo=True),
        ConceptoLiquidacion(consorcio_id=1, nombre="FMVDD art. 27 CCT", tipo=TipoConcepto.descuento, porcentaje=1.75, proveedor_id=fateryh.id, orden=7, activo=True),
        # Contribuciones (paga el consorcio aparte)
        ConceptoLiquidacion(consorcio_id=1, nombre="AFIP F931", tipo=TipoConcepto.contribucion, porcentaje=16.0, proveedor_id=afip.id, orden=10, activo=True),
        ConceptoLiquidacion(consorcio_id=1, nombre="ARCA VEP", tipo=TipoConcepto.contribucion, porcentaje=10.78, proveedor_id=arca.id, orden=11, activo=True),
        ConceptoLiquidacion(consorcio_id=1, nombre="FATERYH", tipo=TipoConcepto.contribucion, porcentaje=8.535, proveedor_id=fateryh.id, orden=12, activo=True),
        ConceptoLiquidacion(consorcio_id=1, nombre="FATERYH-SERACARH", tipo=TipoConcepto.contribucion, porcentaje=0.5, proveedor_id=fateryh.id, orden=13, activo=True),
        ConceptoLiquidacion(consorcio_id=1, nombre="SUTERH patronal", tipo=TipoConcepto.contribucion, porcentaje=4.51, proveedor_id=suterh_prov.id, orden=14, activo=True),
    ])

    # ----- Fase 11: plantillas de trabajos recurrentes -----
    db.add_all([
        TrabajoRecurrente(
            consorcio_id=1,
            nombre="Limpieza tanque",
            descripcion="Limpieza trimestral del tanque de agua",
            periodicidad=PeriodicidadRecurrente.trimestral,
            proveedor_sugerido_id=prov_limpieza.id,
            monto_estimado=80000,
            activa=True,
        ),
        TrabajoRecurrente(
            consorcio_id=1,
            nombre="Mantenimiento ascensores",
            descripcion="Service mensual de ascensores",
            periodicidad=PeriodicidadRecurrente.mensual,
            proveedor_sugerido_id=prov_ascensor.id,
            monto_estimado=120000,
            activa=True,
        ),
    ])
    db.flush()

    db.add_all(
        [
            Peticion(
                consorcio_id=1,
                departamento_id=depto_a.id,
                titulo="Filtración en cocina",
                descripcion="Hay una filtración del piso de arriba en la cocina.",
                estado=EstadoPeticion.abierta,
            ),
            Peticion(
                consorcio_id=1,
                departamento_id=depto_b.id,
                titulo="Luz quemada en pasillo",
                descripcion="La lámpara del pasillo del 2do piso está quemada.",
                estado=EstadoPeticion.abierta,
            ),
        ]
    )
    db.flush()

    # ----- Fase 3.5: expensas de muestra + cuenta corriente -----
    fecha_1_demo = date(2026, 7, 10)
    fecha_2_demo = fecha_1_demo + timedelta(days=10)
    expensa_a = Expensa(
        consorcio_id=1,
        departamento_id=depto_a.id,
        periodo="2026-05",
        monto_primer_vencimiento=85000.00,
        fecha_primer_vencimiento=fecha_1_demo,
        monto_segundo_vencimiento=round(85000.00 * 1.07, 2),
        fecha_segundo_vencimiento=fecha_2_demo,
        saldo_anterior=0.0,
    )
    expensa_b = Expensa(
        consorcio_id=1,
        departamento_id=depto_b.id,
        periodo="2026-05",
        monto_primer_vencimiento=92000.00,
        fecha_primer_vencimiento=fecha_1_demo,
        monto_segundo_vencimiento=round(92000.00 * 1.07, 2),
        fecha_segundo_vencimiento=fecha_2_demo,
        saldo_anterior=0.0,
    )
    db.add_all([expensa_a, expensa_b])
    db.flush()

    db.add_all([
        ExpensaDetalle(
            consorcio_id=1,
            expensa_id=expensa_a.id,
            rubro=Rubro.abonos_y_servicios,
            clase_prorrateo_id=clase_a.id,
            departamento_origen_id=None,
            concepto="Demo Fase 3.5: prorrateo clase A",
            monto=85000.00,
        ),
        ExpensaDetalle(
            consorcio_id=1,
            expensa_id=expensa_b.id,
            rubro=Rubro.abonos_y_servicios,
            clase_prorrateo_id=clase_a.id,
            departamento_origen_id=None,
            concepto="Demo Fase 3.5: prorrateo clase A",
            monto=92000.00,
        ),
    ])
    db.flush()

    db.add_all([
        MovimientoCuenta(
            consorcio_id=1,
            departamento_id=depto_a.id,
            fecha=date(2026, 6, 10),
            tipo=TipoMovimiento.expensa_emitida,
            descripcion="Expensa 2026-05",
            monto=85000.00,
            expensa_id=expensa_a.id,
        ),
        MovimientoCuenta(
            consorcio_id=1,
            departamento_id=depto_b.id,
            fecha=date(2026, 6, 10),
            tipo=TipoMovimiento.expensa_emitida,
            descripcion="Expensa 2026-05",
            monto=92000.00,
            expensa_id=expensa_b.id,
        ),
        # Variedad de ejemplo: una nota crédito para depto_a y una nota débito para depto_b.
        MovimientoCuenta(
            consorcio_id=1,
            departamento_id=depto_a.id,
            fecha=date(2026, 6, 15),
            tipo=TipoMovimiento.nota_credito,
            descripcion="Bonificación pago anticipado",
            monto=2000.00,
        ),
        MovimientoCuenta(
            consorcio_id=1,
            departamento_id=depto_b.id,
            fecha=date(2026, 6, 15),
            tipo=TipoMovimiento.nota_debito,
            descripcion="Ajuste por mantenimiento extraordinario",
            monto=1500.00,
        ),
    ])

    # ----- Fase 12: amenities demo -----
    db.add_all([
        Amenity(
            consorcio_id=1,
            nombre="SUM",
            descripcion="Salón de usos múltiples (eventos privados)",
            activo=True,
            precio_reserva=20000.0,
            duracion_maxima_horas=12,
            anticipacion_maxima_dias=60,
            max_reservas_activas_por_depto=2,
            horas_minimas_cancelacion=48,
        ),
        Amenity(
            consorcio_id=1,
            nombre="Laundry",
            descripcion="Lavandería compartida",
            activo=True,
            precio_reserva=None,
            duracion_maxima_horas=3,
            anticipacion_maxima_dias=14,
            max_reservas_activas_por_depto=3,
            horas_minimas_cancelacion=None,
        ),
    ])
    db.flush()

    db.commit()

    # Postgres: resetear las sequences de tablas donde insertamos IDs explícitos.
    # Sin esto, el próximo INSERT sin ID sale con id=1 y colisiona con el PK
    # existente (SQLite no tiene sequences separadas, no aplica ahí).
    if get_settings().DATABASE_URL.startswith("postgresql"):
        for tabla in inspect(db.bind).get_table_names():
            db.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {tabla}), 1), "
                f"(SELECT MAX(id) FROM {tabla}) IS NOT NULL)"
            ))
        db.commit()

    logger.warning(
        "Seed completado. Usuarios: admin id=%s, depto-a id=%s, depto-b id=%s",
        admin.id,
        user_a.id,
        user_b.id,
    )
    if generated:
        logger.warning(
            "SEED_DEFAULT_PASSWORD no definida — generada al vuelo: %s "
            "(guardala ahora; no se persiste).",
            password,
        )

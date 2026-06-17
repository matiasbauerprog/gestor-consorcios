import logging
import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    CategoriaEmpleado,
    ClaseProrrateo,
    CoeficienteDepartamento,
    ConceptoLiquidacion,
    ConfiguracionConsorcio,
    Departamento,
    Empleado,
    EstadoPeticion,
    FormaPago,
    Gasto,
    GastoHabitual,
    Haber,
    Peticion,
    Proveedor,
    Rol,
    Rubro,
    TipoConcepto,
    TipoHaber,
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

    depto_a = Departamento(codigo="UF-1A", descripcion="Piso 1, Unidad A")
    depto_b = Departamento(codigo="UF-2B", descripcion="Piso 2, Unidad B")
    db.add_all([depto_a, depto_b])
    db.flush()

    admin = Usuario(
        email="admin@consorcio.local",
        password_hash=hash_password(password),
        rol=Rol.administracion,
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
    clase_a = ClaseProrrateo(codigo="A", nombre="Expensas ordinarias", activa=True)
    clase_b = ClaseProrrateo(codigo="B", nombre="Expensas extraordinarias", activa=True)
    clase_c = ClaseProrrateo(codigo="C", nombre="Servicios diferenciados", activa=True)
    clase_d = ClaseProrrateo(codigo="D", nombre="Obras de frente", activa=True)
    db.add_all([clase_a, clase_b, clase_c, clase_d])
    db.flush()

    # ----- Fase 1: coeficientes para cada depto (clase A, 50% c/u) -----
    db.add_all([
        CoeficienteDepartamento(
            departamento_id=depto_a.id, clase_prorrateo_id=clase_a.id, porcentaje=50.0
        ),
        CoeficienteDepartamento(
            departamento_id=depto_b.id, clase_prorrateo_id=clase_a.id, porcentaje=50.0
        ),
    ])

    # ----- Fase 1: proveedores de ejemplo -----
    db.add_all([
        Proveedor(razon_social="Limpieza S.A.", nombre_fantasia="Limpieza", cuit="30-11111111-1"),
        Proveedor(razon_social="Ascensores SRL", nombre_fantasia="Ascensores", cuit="30-22222222-2"),
        Proveedor(razon_social="Seguros del Hogar", nombre_fantasia="SeguHogar", cuit="30-33333333-3"),
        Proveedor(razon_social="Banco Río", nombre_fantasia="Banco", cuit="30-44444444-4"),
        Proveedor(razon_social="Admin Consorcios", nombre_fantasia="Admin", cuit="30-55555555-5"),
    ])
    db.flush()

    # ----- Fase 1: configuración singleton -----
    db.add(ConfiguracionConsorcio(
        id=1,
        consorcio_nombre="PENDIENTE",
        consorcio_domicilio="PENDIENTE",
        consorcio_cuit="00-00000000-0",
        consorcio_convenio_suterh=None,
        admin_nombre="PENDIENTE",
        admin_domicilio="PENDIENTE",
        admin_email="pendiente@local",
        admin_telefono="PENDIENTE",
        admin_cuit="00-00000000-0",
        admin_rpa="PENDIENTE",
        admin_situacion_fiscal="PENDIENTE",
        banco_titular="PENDIENTE",
        banco_nombre="PENDIENTE",
        banco_sucursal=None,
        banco_numero_cuenta="PENDIENTE",
        banco_cbu="0000000000000000000000",
        banco_alias=None,
    ))

    # ----- Fase 2: plantillas de gastos habituales -----
    # Tomamos proveedores sembrados por id (orden de creación = orden alfabético del seed).
    proveedores_seed = db.scalars(
        select(Proveedor).order_by(Proveedor.id)
    ).all()
    prov_limpieza = proveedores_seed[0]
    prov_ascensor = proveedores_seed[1]
    prov_admin = proveedores_seed[4]

    plantilla_sueldo = GastoHabitual(
        nombre="Sueldo encargado",
        rubro=Rubro.sueldos_y_cargas_sociales,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_admin.id,
        concepto="Sueldo mensual del encargado",
        monto=800000.0,
        forma_pago=FormaPago.transferencia,
        activa=True,
    )
    plantilla_limpieza = GastoHabitual(
        nombre="Servicio de limpieza",
        rubro=Rubro.abonos_y_servicios,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_limpieza.id,
        concepto="Limpieza mensual de áreas comunes",
        monto=200000.0,
        forma_pago=FormaPago.transferencia,
        activa=True,
    )
    plantilla_ascensor = GastoHabitual(
        nombre="Mantenimiento ascensores",
        rubro=Rubro.abonos_y_servicios,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_ascensor.id,
        concepto="Mantenimiento mensual de ascensores",
        monto=50000.0,
        forma_pago=FormaPago.transferencia,
        activa=True,
    )
    db.add_all([plantilla_sueldo, plantilla_limpieza, plantilla_ascensor])
    db.flush()

    # ----- Fase 2: gastos puntuales de ejemplo (período 2026-06) -----
    db.add_all([
        # Generado a partir de plantilla.
        Gasto(
            periodo="2026-06",
            rubro=Rubro.sueldos_y_cargas_sociales,
            clase_prorrateo_id=clase_a.id,
            proveedor_id=prov_admin.id,
            concepto="Sueldo mensual del encargado",
            monto=800000.0,
            forma_pago=FormaPago.transferencia,
            fecha_pago=date(2026, 6, 1),
            gasto_habitual_id=plantilla_sueldo.id,
        ),
        # Prorrateable puntual.
        Gasto(
            periodo="2026-06",
            rubro=Rubro.mantenimiento_partes_comunes,
            clase_prorrateo_id=clase_a.id,
            proveedor_id=prov_limpieza.id,
            concepto="Reparación cañería común",
            monto=120000.0,
            forma_pago=FormaPago.transferencia,
            fecha_pago=date(2026, 6, 8),
        ),
        # Particular a un depto.
        Gasto(
            periodo="2026-06",
            rubro=Rubro.trabajos_reparaciones_unidades,
            departamento_id=depto_a.id,
            proveedor_id=prov_limpieza.id,
            concepto="Arreglo plomería - UF 1A",
            monto=80000.0,
            forma_pago=FormaPago.transferencia,
            fecha_pago=date(2026, 6, 12),
        ),
        # En cuotas (cuota 1/3 cargada manualmente).
        Gasto(
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
        ),
    ])

    # ----- Fase 3: 4 proveedores institucionales -----
    afip = Proveedor(razon_social="AFIP", nombre_fantasia="AFIP", cuit="30-00000001-7")
    arca = Proveedor(razon_social="ARCA", nombre_fantasia="ARCA", cuit="30-00000002-5")
    fateryh = Proveedor(razon_social="FATERYH", nombre_fantasia="FATERYH", cuit="30-00000003-3")
    suterh_prov = Proveedor(razon_social="SUTERH", nombre_fantasia="SUTERH", cuit="30-00000004-1")
    db.add_all([afip, arca, fateryh, suterh_prov])
    db.flush()

    # ----- Fase 3: proveedor + empleado de ejemplo -----
    prov_empleado = Proveedor(razon_social="Pérez, Juan", nombre_fantasia="Pérez Juan", cuit="20-12345678-9")
    db.add(prov_empleado)
    db.flush()

    empleado_ej = Empleado(
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
        Haber(nombre="Básico", tipo=TipoHaber.porcentaje_sobre_basico, valor_default=100.0, orden=1, activo=True),
        Haber(nombre="Antigüedad", tipo=TipoHaber.porcentaje_sobre_basico, valor_default=1.0, orden=2, activo=True),
        Haber(nombre="Presentismo", tipo=TipoHaber.porcentaje_sobre_basico, valor_default=8.33, orden=3, activo=True),
        Haber(nombre="Adicional vivienda", tipo=TipoHaber.monto_fijo, valor_default=0.0, orden=4, activo=True),
        Haber(nombre="Horas extra 50%", tipo=TipoHaber.cantidad_x_valor, valor_default=0.0, orden=5, activo=True),
        Haber(nombre="Horas extra 100%", tipo=TipoHaber.cantidad_x_valor, valor_default=0.0, orden=6, activo=True),
    ])

    # ----- Fase 3: 12 conceptos SUTERH (paritarias 2026 referencia) -----
    db.add_all([
        # Descuentos (salen del bruto)
        ConceptoLiquidacion(nombre="Jubilación", tipo=TipoConcepto.descuento, porcentaje=11.0, proveedor_id=afip.id, orden=1, activo=True),
        ConceptoLiquidacion(nombre="ISSPJ Ley 19032", tipo=TipoConcepto.descuento, porcentaje=3.0, proveedor_id=afip.id, orden=2, activo=True),
        ConceptoLiquidacion(nombre="OSPERyHA", tipo=TipoConcepto.descuento, porcentaje=2.55, proveedor_id=afip.id, orden=3, activo=True),
        ConceptoLiquidacion(nombre="ANSSAL", tipo=TipoConcepto.descuento, porcentaje=0.45, proveedor_id=afip.id, orden=4, activo=True),
        ConceptoLiquidacion(nombre="Caja Protección Familia", tipo=TipoConcepto.descuento, porcentaje=1.0, proveedor_id=fateryh.id, orden=5, activo=True),
        ConceptoLiquidacion(nombre="Cuota Sindical SUTERH", tipo=TipoConcepto.descuento, porcentaje=2.0, proveedor_id=suterh_prov.id, orden=6, activo=True),
        ConceptoLiquidacion(nombre="FMVDD art. 27 CCT", tipo=TipoConcepto.descuento, porcentaje=1.75, proveedor_id=fateryh.id, orden=7, activo=True),
        # Contribuciones (paga el consorcio aparte)
        ConceptoLiquidacion(nombre="AFIP F931", tipo=TipoConcepto.contribucion, porcentaje=16.0, proveedor_id=afip.id, orden=10, activo=True),
        ConceptoLiquidacion(nombre="ARCA VEP", tipo=TipoConcepto.contribucion, porcentaje=10.78, proveedor_id=arca.id, orden=11, activo=True),
        ConceptoLiquidacion(nombre="FATERYH", tipo=TipoConcepto.contribucion, porcentaje=8.535, proveedor_id=fateryh.id, orden=12, activo=True),
        ConceptoLiquidacion(nombre="FATERYH-SERACARH", tipo=TipoConcepto.contribucion, porcentaje=0.5, proveedor_id=fateryh.id, orden=13, activo=True),
        ConceptoLiquidacion(nombre="SUTERH patronal", tipo=TipoConcepto.contribucion, porcentaje=4.51, proveedor_id=suterh_prov.id, orden=14, activo=True),
    ])

    db.add_all(
        [
            Peticion(
                departamento_id=depto_a.id,
                titulo="Filtración en cocina",
                descripcion="Hay una filtración del piso de arriba en la cocina.",
                estado=EstadoPeticion.abierta,
            ),
            Peticion(
                departamento_id=depto_b.id,
                titulo="Luz quemada en pasillo",
                descripcion="La lámpara del pasillo del 2do piso está quemada.",
                estado=EstadoPeticion.abierta,
            ),
        ]
    )
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

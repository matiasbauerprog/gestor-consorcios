import enum
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Rol(str, enum.Enum):
    administracion = "administracion"
    representante = "representante"
    departamento = "departamento"


class EstadoPeticion(str, enum.Enum):
    abierta = "abierta"
    convertida_en_trabajo = "convertida_en_trabajo"
    rechazada = "rechazada"


class EstadoTrabajo(str, enum.Enum):
    en_curso = "en_curso"
    finalizado = "finalizado"
    cancelado = "cancelado"


class EstadoPresupuesto(str, enum.Enum):
    presentado = "presentado"
    aprobado = "aprobado"
    rechazado = "rechazado"


class EstadoExpensa(str, enum.Enum):
    pendiente = "pendiente"
    parcial = "parcial"
    pagada = "pagada"
    vencida = "vencida"


class EstadoComprobante(str, enum.Enum):
    pendiente_verificacion = "pendiente_verificacion"
    aprobado = "aprobado"
    rechazado = "rechazado"


class TipoMovimiento(str, enum.Enum):
    expensa_emitida = "expensa_emitida"
    pago_recibido = "pago_recibido"
    interes_punitorio = "interes_punitorio"
    nota_debito = "nota_debito"
    nota_credito = "nota_credito"


TIPOS_DEBITO = frozenset({
    TipoMovimiento.expensa_emitida,
    TipoMovimiento.interes_punitorio,
    TipoMovimiento.nota_debito,
})
TIPOS_CREDITO = frozenset({
    TipoMovimiento.pago_recibido,
    TipoMovimiento.nota_credito,
})


class EstadoReserva(str, enum.Enum):
    confirmada = "confirmada"
    cancelada = "cancelada"


class Rubro(str, enum.Enum):
    sueldos_y_cargas_sociales = "sueldos_y_cargas_sociales"
    servicios_publicos = "servicios_publicos"
    abonos_y_servicios = "abonos_y_servicios"
    mantenimiento_partes_comunes = "mantenimiento_partes_comunes"
    trabajos_reparaciones_unidades = "trabajos_reparaciones_unidades"
    gastos_bancarios = "gastos_bancarios"
    gastos_administracion = "gastos_administracion"
    seguros = "seguros"
    gastos_generales = "gastos_generales"


class FormaPago(str, enum.Enum):
    transferencia = "transferencia"
    debito_automatico = "debito_automatico"
    cheque = "cheque"
    efectivo = "efectivo"
    otro = "otro"


class CategoriaEmpleado(str, enum.Enum):
    encargado_permanente_con_vivienda = "encargado_permanente_con_vivienda"
    encargado_permanente_sin_vivienda = "encargado_permanente_sin_vivienda"
    encargado_suplente = "encargado_suplente"
    ayudante = "ayudante"


class TipoConcepto(str, enum.Enum):
    descuento = "descuento"
    contribucion = "contribucion"


class TipoHaber(str, enum.Enum):
    monto_fijo = "monto_fijo"
    porcentaje_sobre_basico = "porcentaje_sobre_basico"
    cantidad_x_valor = "cantidad_x_valor"


class Departamento(Base):
    __tablename__ = "departamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255))

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="departamento")
    peticiones: Mapped[list["Peticion"]] = relationship(back_populates="departamento")
    expensas: Mapped[list["Expensa"]] = relationship(back_populates="departamento")
    coeficientes: Mapped[list["CoeficienteDepartamento"]] = relationship(
        back_populates="departamento", cascade="all, delete-orphan"
    )


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[Rol] = mapped_column(SqlEnum(Rol, name="rol"), nullable=False)
    departamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=True,
    )

    departamento: Mapped["Departamento | None"] = relationship(back_populates="usuarios")


class Peticion(Base):
    __tablename__ = "peticiones"

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(2000), nullable=False)
    estado: Mapped[EstadoPeticion] = mapped_column(
        SqlEnum(EstadoPeticion, name="estado_peticion"),
        nullable=False,
        default=EstadoPeticion.abierta,
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    departamento: Mapped["Departamento"] = relationship(back_populates="peticiones")
    trabajos: Mapped[list["Trabajo"]] = relationship(back_populates="peticion")


class Trabajo(Base):
    __tablename__ = "trabajos"

    id: Mapped[int] = mapped_column(primary_key=True)
    peticion_id: Mapped[int | None] = mapped_column(
        ForeignKey("peticiones.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    descripcion: Mapped[str] = mapped_column(String(2000), nullable=False)
    estado: Mapped[EstadoTrabajo] = mapped_column(
        SqlEnum(EstadoTrabajo, name="estado_trabajo"),
        nullable=False,
        default=EstadoTrabajo.en_curso,
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    peticion: Mapped["Peticion | None"] = relationship(back_populates="trabajos")
    presupuestos: Mapped[list["Presupuesto"]] = relationship(back_populates="trabajo")


class Presupuesto(Base):
    __tablename__ = "presupuestos"

    id: Mapped[int] = mapped_column(primary_key=True)
    trabajo_id: Mapped[int] = mapped_column(
        ForeignKey("trabajos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    proveedor: Mapped[str] = mapped_column(String(255), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    estado: Mapped[EstadoPresupuesto] = mapped_column(
        SqlEnum(EstadoPresupuesto, name="estado_presupuesto"),
        nullable=False,
        default=EstadoPresupuesto.presentado,
    )
    fecha_presentacion: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )

    trabajo: Mapped["Trabajo"] = relationship(back_populates="presupuestos")


class Comunicado(Base):
    __tablename__ = "comunicados"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    cuerpo: Mapped[str] = mapped_column(String(5000), nullable=False)
    fecha_publicacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    autor_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    eliminado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class Expensa(Base):
    __tablename__ = "expensas"
    __table_args__ = (
        UniqueConstraint("departamento_id", "periodo", name="uq_expensa_depto_periodo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)

    departamento: Mapped["Departamento"] = relationship(back_populates="expensas")


class Comprobante(Base):
    __tablename__ = "comprobantes"

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    archivo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estado: Mapped[EstadoComprobante] = mapped_column(
        SqlEnum(EstadoComprobante, name="estado_comprobante"),
        nullable=False,
        default=EstadoComprobante.pendiente_verificacion,
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    departamento: Mapped["Departamento"] = relationship()


class Amenity(Base):
    __tablename__ = "amenities"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500))

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="amenity")


class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[int] = mapped_column(primary_key=True)
    amenity_id: Mapped[int] = mapped_column(
        ForeignKey("amenities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[EstadoReserva] = mapped_column(
        SqlEnum(EstadoReserva, name="estado_reserva"),
        nullable=False,
        default=EstadoReserva.confirmada,
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    amenity: Mapped["Amenity"] = relationship(back_populates="reservas")


class ClaseProrrateo(Base):
    __tablename__ = "clases_prorrateo"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500))
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    coeficientes: Mapped[list["CoeficienteDepartamento"]] = relationship(
        back_populates="clase"
    )


class CoeficienteDepartamento(Base):
    __tablename__ = "coeficientes_departamento"
    __table_args__ = (
        UniqueConstraint(
            "departamento_id", "clase_prorrateo_id", name="uq_coef_depto_clase"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    clase_prorrateo_id: Mapped[int] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    porcentaje: Mapped[float] = mapped_column(Float, nullable=False)

    departamento: Mapped["Departamento"] = relationship(back_populates="coeficientes")
    clase: Mapped["ClaseProrrateo"] = relationship(back_populates="coeficientes")


class Proveedor(Base):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(primary_key=True)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_fantasia: Mapped[str | None] = mapped_column(String(255))
    cuit: Mapped[str] = mapped_column(String(13), unique=True, nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(500))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConfiguracionConsorcio(Base):
    __tablename__ = "configuracion_consorcio"

    id: Mapped[int] = mapped_column(primary_key=True)

    # consorcio
    consorcio_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    consorcio_domicilio: Mapped[str] = mapped_column(String(500), nullable=False)
    consorcio_cuit: Mapped[str] = mapped_column(String(13), nullable=False)
    consorcio_convenio_suterh: Mapped[str | None] = mapped_column(String(50))

    # administración
    admin_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_domicilio: Mapped[str] = mapped_column(String(500), nullable=False)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_telefono: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_cuit: Mapped[str] = mapped_column(String(13), nullable=False)
    admin_rpa: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_situacion_fiscal: Mapped[str] = mapped_column(String(100), nullable=False)

    # banco
    banco_titular: Mapped[str] = mapped_column(String(255), nullable=False)
    banco_nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    banco_sucursal: Mapped[str | None] = mapped_column(String(50))
    banco_numero_cuenta: Mapped[str] = mapped_column(String(50), nullable=False)
    banco_cbu: Mapped[str] = mapped_column(String(22), nullable=False)
    banco_alias: Mapped[str | None] = mapped_column(String(50))


class GastoHabitual(Base):
    __tablename__ = "gastos_habituales"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    rubro: Mapped[Rubro] = mapped_column(SqlEnum(Rubro, name="rubro"), nullable=False)
    clase_prorrateo_id: Mapped[int] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="RESTRICT"), nullable=False
    )
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False
    )
    concepto: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    forma_pago: Mapped[FormaPago] = mapped_column(
        SqlEnum(FormaPago, name="forma_pago"), nullable=False
    )
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Gasto(Base):
    __tablename__ = "gastos"

    id: Mapped[int] = mapped_column(primary_key=True)
    periodo: Mapped[str] = mapped_column(String(7), index=True, nullable=False)
    rubro: Mapped[Rubro] = mapped_column(SqlEnum(Rubro, name="rubro"), nullable=False)

    # Excluyentes: clase_prorrateo_id O departamento_id, nunca ambos, nunca ninguno.
    # La excluyencia se valida en el schema Pydantic, no a nivel DB.
    clase_prorrateo_id: Mapped[int | None] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="RESTRICT"), nullable=True
    )
    departamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=True
    )

    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    concepto: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)

    forma_pago: Mapped[FormaPago] = mapped_column(
        SqlEnum(FormaPago, name="forma_pago"), nullable=False
    )
    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)

    numero_factura: Mapped[str | None] = mapped_column(String(50))
    fecha_factura: Mapped[date | None] = mapped_column(Date)

    cuota_actual: Mapped[int | None] = mapped_column(Integer)
    cuota_total: Mapped[int | None] = mapped_column(Integer)

    gasto_habitual_id: Mapped[int | None] = mapped_column(
        ForeignKey("gastos_habituales.id", ondelete="SET NULL")
    )

    liquidacion_id: Mapped[int | None] = mapped_column(
        ForeignKey("liquidaciones_empleado.id", ondelete="SET NULL"), nullable=True
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Empleado(Base):
    __tablename__ = "empleados"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String(255), nullable=False)
    cuil: Mapped[str] = mapped_column(String(13), unique=True, nullable=False)
    categoria: Mapped[CategoriaEmpleado] = mapped_column(
        SqlEnum(CategoriaEmpleado, name="categoria_empleado"), nullable=False
    )
    fecha_ingreso: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_egreso: Mapped[date | None] = mapped_column(Date)
    sueldo_basico: Mapped[float] = mapped_column(Float, nullable=False)
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Haber(Base):
    __tablename__ = "haberes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    tipo: Mapped[TipoHaber] = mapped_column(SqlEnum(TipoHaber, name="tipo_haber"), nullable=False)
    valor_default: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ConceptoLiquidacion(Base):
    __tablename__ = "conceptos_liquidacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    tipo: Mapped[TipoConcepto] = mapped_column(SqlEnum(TipoConcepto, name="tipo_concepto"), nullable=False)
    porcentaje: Mapped[float] = mapped_column(Float, nullable=False)
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LiquidacionEmpleado(Base):
    __tablename__ = "liquidaciones_empleado"
    __table_args__ = (
        UniqueConstraint("empleado_id", "periodo", name="uq_liquidacion_empleado_periodo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empleado_id: Mapped[int] = mapped_column(
        ForeignKey("empleados.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    periodo: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    sueldo_bruto: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    haberes: Mapped[list["LiquidacionHaber"]] = relationship(
        back_populates="liquidacion",
        cascade="all, delete-orphan",
        order_by="LiquidacionHaber.orden",
    )
    detalle: Mapped[list["LiquidacionDetalle"]] = relationship(
        back_populates="liquidacion",
        cascade="all, delete-orphan",
        order_by="LiquidacionDetalle.orden",
    )


class LiquidacionHaber(Base):
    __tablename__ = "liquidaciones_haber"

    id: Mapped[int] = mapped_column(primary_key=True)
    liquidacion_id: Mapped[int] = mapped_column(
        ForeignKey("liquidaciones_empleado.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[TipoHaber | None] = mapped_column(
        SqlEnum(TipoHaber, name="tipo_haber"), nullable=True
    )
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    cantidad: Mapped[float | None] = mapped_column(Float, nullable=True)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    liquidacion: Mapped["LiquidacionEmpleado"] = relationship(back_populates="haberes")


class LiquidacionDetalle(Base):
    __tablename__ = "liquidaciones_detalle"

    id: Mapped[int] = mapped_column(primary_key=True)
    liquidacion_id: Mapped[int] = mapped_column(
        ForeignKey("liquidaciones_empleado.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concepto_nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    concepto_tipo: Mapped[TipoConcepto] = mapped_column(
        SqlEnum(TipoConcepto, name="tipo_concepto"), nullable=False
    )
    porcentaje_aplicado: Mapped[float] = mapped_column(Float, nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    liquidacion: Mapped["LiquidacionEmpleado"] = relationship(back_populates="detalle")


class MovimientoCuenta(Base):
    __tablename__ = "movimientos_cuenta"

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tipo: Mapped[TipoMovimiento] = mapped_column(
        SqlEnum(TipoMovimiento, name="tipo_movimiento"),
        nullable=False,
    )
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)

    expensa_id: Mapped[int | None] = mapped_column(
        ForeignKey("expensas.id", ondelete="SET NULL"),
        nullable=True,
    )
    comprobante_id: Mapped[int | None] = mapped_column(
        ForeignKey("comprobantes.id", ondelete="SET NULL"),
        nullable=True,
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    departamento: Mapped["Departamento"] = relationship()
    expensa: Mapped["Expensa | None"] = relationship()
    comprobante: Mapped["Comprobante | None"] = relationship()

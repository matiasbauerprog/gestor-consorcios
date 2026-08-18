import enum
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Rol(str, enum.Enum):
    administracion = "administracion"
    representante = "representante"
    departamento = "departamento"
    super_admin = "super_admin"


class EstadoPeticion(str, enum.Enum):
    abierta = "abierta"
    convertida_en_trabajo = "convertida_en_trabajo"
    rechazada = "rechazada"
    cancelada = "cancelada"


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
    recargo = "recargo"
    nota_debito = "nota_debito"
    nota_credito = "nota_credito"


TIPOS_DEBITO = frozenset({
    TipoMovimiento.expensa_emitida,
    TipoMovimiento.interes_punitorio,
    TipoMovimiento.recargo,
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


class TipoCaja(str, enum.Enum):
    efectivo = "efectivo"
    banco = "banco"
    fondo_reparacion = "fondo_reparacion"
    otro = "otro"


class TipoMovimientoCaja(str, enum.Enum):
    ingreso = "ingreso"
    egreso = "egreso"
    ajuste = "ajuste"


class FormaPago(str, enum.Enum):
    transferencia = "transferencia"
    debito_automatico = "debito_automatico"
    cheque = "cheque"
    efectivo = "efectivo"
    otro = "otro"


class PeriodicidadRecurrente(str, enum.Enum):
    mensual = "mensual"
    trimestral = "trimestral"
    semestral = "semestral"
    anual = "anual"


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
    __table_args__ = (
        UniqueConstraint("consorcio_id", "codigo", name="uq_depto_consorcio_codigo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    codigo: Mapped[str] = mapped_column(String(32), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255))

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="departamento")
    peticiones: Mapped[list["Peticion"]] = relationship(back_populates="departamento")
    expensas: Mapped[list["Expensa"]] = relationship(back_populates="departamento")
    comprobantes: Mapped[list["Comprobante"]] = relationship(back_populates="departamento")
    movimientos_cuenta: Mapped[list["MovimientoCuenta"]] = relationship(back_populates="departamento")
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
    administracion_id: Mapped[int | None] = mapped_column(
        ForeignKey("administraciones.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    consorcio_id: Mapped[int | None] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    departamento: Mapped["Departamento | None"] = relationship(back_populates="usuarios")


class ErrorRegistrado(Base):
    """Un error inesperado, con el contexto para poder rastrearlo.

    El `codigo` es lo que se le muestra al usuario y lo que después se busca en
    el panel: es la única pieza que viaja del vecino al soporte.

    Esta tabla es la copia cómoda de consultar, **no** la fuente de verdad: si
    el error fue una falla de base, la fila no se llega a escribir. Por eso
    `backend/errores.py` escribe siempre primero a la salida del servidor.
    """

    __tablename__ = "errores_registrados"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True, index=True
    )
    ocurrido_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    ruta: Mapped[str] = mapped_column(String(255), nullable=False)
    metodo: Mapped[str] = mapped_column(String(10), nullable=False)
    tipo: Mapped[str] = mapped_column(String(120), nullable=False)
    mensaje: Mapped[str] = mapped_column(String(1000), nullable=False)
    traza: Mapped[str] = mapped_column(Text, nullable=False)
    # Sin FK a usuarios: si el usuario se borra, el error tiene que sobrevivir
    # -- justamente puede ser la pista de por qué se borró.
    usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rol: Mapped[str | None] = mapped_column(String(40), nullable=True)
    consorcio_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


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


class Peticion(Base):
    __tablename__ = "peticiones"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
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
    # Lo que la administración escribe al rechazar. Queda en la petición para
    # que el departamento vea POR QUÉ le dijeron que no, no sólo que le dijeron
    # que no. Sólo tiene sentido en estado `rechazada`.
    motivo_rechazo: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    departamento: Mapped["Departamento"] = relationship(back_populates="peticiones")
    trabajos: Mapped[list["Trabajo"]] = relationship(back_populates="peticion")


class Trabajo(Base):
    __tablename__ = "trabajos"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    peticion_id: Mapped[int | None] = mapped_column(
        ForeignKey("peticiones.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    presupuesto_aprobado_id: Mapped[int | None] = mapped_column(
        ForeignKey("presupuestos.id"), nullable=True,
    )
    gasto_id: Mapped[int | None] = mapped_column(
        ForeignKey("gastos.id"), nullable=True,
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
    presupuestos: Mapped[list["Presupuesto"]] = relationship(
        back_populates="trabajo",
        foreign_keys="Presupuesto.trabajo_id"
    )


class Presupuesto(Base):
    __tablename__ = "presupuestos"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    trabajo_id: Mapped[int] = mapped_column(
        ForeignKey("trabajos.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    estado: Mapped[EstadoPresupuesto] = mapped_column(
        SqlEnum(EstadoPresupuesto, name="estado_presupuesto"),
        nullable=False, default=EstadoPresupuesto.presentado,
    )
    fecha_presentacion: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date(),
    )
    archivo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    trabajo: Mapped["Trabajo"] = relationship(
        back_populates="presupuestos",
        foreign_keys=[trabajo_id]
    )


class Comunicado(Base):
    __tablename__ = "comunicados"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
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
        UniqueConstraint("consorcio_id", "departamento_id", "periodo",
                         name="uq_expensa_consorcio_depto_periodo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)

    # renombrados desde el shape Fase 3.5:
    monto_primer_vencimiento: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_primer_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)

    # nuevos en Fase 4:
    monto_segundo_vencimiento: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_segundo_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)
    saldo_anterior: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # El recargo se decide una sola vez, el día del vencimiento, y la decisión
    # no cambia después. Marcar la expensa evita re-evaluarla en cada lectura.
    recargo_evaluado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    departamento: Mapped["Departamento"] = relationship(back_populates="expensas")
    detalle: Mapped[list["ExpensaDetalle"]] = relationship(
        back_populates="expensa", cascade="all, delete-orphan"
    )


class ExpensaDetalle(Base):
    __tablename__ = "expensa_detalle"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    expensa_id: Mapped[int] = mapped_column(
        ForeignKey("expensas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rubro: Mapped[Rubro] = mapped_column(SqlEnum(Rubro, name="rubro"), nullable=False)
    clase_prorrateo_id: Mapped[int | None] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="RESTRICT"), nullable=True
    )
    departamento_origen_id: Mapped[int | None] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=True
    )
    concepto: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)

    clase_prorrateo: Mapped["ClaseProrrateo | None"] = relationship()
    departamento_origen: Mapped["Departamento | None"] = relationship()
    expensa: Mapped["Expensa"] = relationship(back_populates="detalle")


class PeriodoCerrado(Base):
    __tablename__ = "periodos_cerrados"

    # PK compuesta: cada consorcio cierra sus propios períodos de forma
    # independiente. Un período cerrado en un consorcio no afecta a los demás.
    periodo: Mapped[str] = mapped_column(String(7), primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        primary_key=True, index=True,
    )
    fecha_cierre: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cerrado_por_usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    total_expensado: Mapped[float] = mapped_column(Float, nullable=False)
    total_intereses: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cantidad_expensas: Mapped[int] = mapped_column(Integer, nullable=False)

    cerrado_por_usuario: Mapped["Usuario"] = relationship()


class Comprobante(Base):
    __tablename__ = "comprobantes"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
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
    eliminado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    caja_destino_id: Mapped[int | None] = mapped_column(ForeignKey("cajas.id"))
    # Lo que la administración escribe al rechazar el pago presentado: el
    # departamento tiene que poder ver qué corregir (monto que no coincide,
    # comprobante ilegible, transferencia a otra cuenta). Sólo aplica en
    # estado `rechazado`.
    motivo_rechazo: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    departamento: Mapped["Departamento"] = relationship(back_populates="comprobantes")


class Amenity(Base):
    __tablename__ = "amenities"
    __table_args__ = (
        UniqueConstraint("consorcio_id", "nombre", name="uq_amenity_consorcio_nombre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500))

    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    precio_reserva: Mapped[float | None] = mapped_column(Float, nullable=True)
    duracion_maxima_horas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anticipacion_maxima_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_reservas_activas_por_depto: Mapped[int | None] = mapped_column(Integer, nullable=True)
    horas_minimas_cancelacion: Mapped[int | None] = mapped_column(Integer, nullable=True)

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="amenity")


class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
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
    movimiento_cuenta_id: Mapped[int | None] = mapped_column(
        ForeignKey("movimientos_cuenta.id", ondelete="SET NULL"),
        nullable=True,
    )

    amenity: Mapped["Amenity"] = relationship(back_populates="reservas")


class ClaseProrrateo(Base):
    __tablename__ = "clases_prorrateo"
    __table_args__ = (
        UniqueConstraint("consorcio_id", "codigo", name="uq_clase_consorcio_codigo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    codigo: Mapped[str] = mapped_column(String(8), nullable=False)
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
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
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
    __table_args__ = (
        UniqueConstraint("consorcio_id", "cuit", name="uq_proveedor_consorcio_cuit"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_fantasia: Mapped[str | None] = mapped_column(String(255))
    cuit: Mapped[str] = mapped_column(String(13), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(500))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GastoHabitual(Base):
    __tablename__ = "gastos_habituales"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
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
    caja_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id"), nullable=False
    )
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Gasto(Base):
    __tablename__ = "gastos"
    # Una plantilla recurrente materializa como mucho UN gasto por período.
    # `_materializar_habituales` corre dentro de un GET y FastAPI atiende los
    # endpoints sync en un threadpool: dos requests concurrentes pasan el
    # chequeo previo a la vez, y sin esta restricción ambos insertarían.
    # `gasto_habitual_id` es NULL en los gastos comunes y SQLite trata cada NULL
    # como distinto, así que no los alcanza.
    __table_args__ = (
        UniqueConstraint("consorcio_id", "periodo", "gasto_habitual_id",
                         name="uq_gasto_consorcio_periodo_habitual"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
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
    caja_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id"), nullable=False
    )
    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)

    # Un gasto puede existir (devengado, prorrateable) sin estar pagado todavía.
    # Sólo al pagarse genera su MovimientoCaja. Default True: los gastos que ya
    # existían fueron todos creados junto con su movimiento.
    pagado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

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
    __table_args__ = (
        UniqueConstraint("consorcio_id", "cuil", name="uq_empleado_consorcio_cuil"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    nombre_completo: Mapped[str] = mapped_column(String(255), nullable=False)
    cuil: Mapped[str] = mapped_column(String(13), nullable=False)
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
    __table_args__ = (
        UniqueConstraint("consorcio_id", "nombre", name="uq_haber_consorcio_nombre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[TipoHaber] = mapped_column(SqlEnum(TipoHaber, name="tipo_haber"), nullable=False)
    valor_default: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ConceptoLiquidacion(Base):
    __tablename__ = "conceptos_liquidacion"
    __table_args__ = (
        UniqueConstraint("consorcio_id", "nombre", name="uq_concepto_consorcio_nombre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
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
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    empleado_id: Mapped[int] = mapped_column(
        ForeignKey("empleados.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    periodo: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    sueldo_bruto: Mapped[float] = mapped_column(Float, nullable=False)
    caja_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id"), nullable=False
    )
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
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
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
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
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
    # Los movimientos atados a una expensa son uno solo por tipo: la emisión y
    # el recargo. `_devengar` inserta el recargo tras un chequeo previo, y dos
    # lecturas concurrentes lo pasarían las dos; la restricción lo impide.
    # Se incluye `tipo` para no chocar la emisión con el recargo de la misma
    # expensa. Los movimientos sin expensa (pagos, notas, intereses) llevan
    # `expensa_id` NULL y SQLite trata cada NULL como distinto: no los alcanza.
    __table_args__ = (
        UniqueConstraint("departamento_id", "expensa_id", "tipo",
                         name="uq_movimiento_depto_expensa_tipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
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
        index=True,
    )
    comprobante_id: Mapped[int | None] = mapped_column(
        ForeignKey("comprobantes.id", ondelete="SET NULL"),
        index=True,
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    departamento: Mapped["Departamento"] = relationship(back_populates="movimientos_cuenta")
    expensa: Mapped["Expensa | None"] = relationship()
    comprobante: Mapped["Comprobante | None"] = relationship()


class Caja(Base):
    __tablename__ = "cajas"
    __table_args__ = (
        UniqueConstraint("consorcio_id", "nombre", name="uq_caja_consorcio_nombre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[TipoCaja] = mapped_column(
        SqlEnum(TipoCaja, name="tipo_caja"), nullable=False
    )
    descripcion: Mapped[str | None] = mapped_column(String(500))
    saldo_inicial: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    movimientos: Mapped[list["MovimientoCaja"]] = relationship(back_populates="caja")


class MovimientoCaja(Base):
    __tablename__ = "movimientos_caja"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    caja_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id", ondelete="RESTRICT"), nullable=False
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tipo: Mapped[TipoMovimientoCaja] = mapped_column(
        SqlEnum(TipoMovimientoCaja, name="tipo_movimiento_caja"), nullable=False
    )
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)

    gasto_id: Mapped[int | None] = mapped_column(ForeignKey("gastos.id"))
    comprobante_id: Mapped[int | None] = mapped_column(ForeignKey("comprobantes.id"))
    transferencia_id: Mapped[int | None] = mapped_column(
        ForeignKey("transferencias_caja.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    caja: Mapped["Caja"] = relationship(back_populates="movimientos")


class TransferenciaCaja(Base):
    __tablename__ = "transferencias_caja"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    caja_origen_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id"), nullable=False
    )
    caja_destino_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id"), nullable=False
    )
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class TrabajoRecurrente(Base):
    __tablename__ = "trabajos_recurrentes"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(2000), nullable=False)
    periodicidad: Mapped[PeriodicidadRecurrente] = mapped_column(
        SqlEnum(PeriodicidadRecurrente, name="periodicidad_recurrente"),
        nullable=False,
    )
    proveedor_sugerido_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id"), nullable=True,
    )
    monto_estimado: Mapped[float | None] = mapped_column(Float, nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tipo: Mapped[str] = mapped_column(
        String(60), nullable=False, server_default="legacy", index=True,
    )
    mensaje: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Entero suelto a propósito, NO foreign key: la notificación tiene que
    # sobrevivir al borrado de la cosa que la originó (una petición borrada
    # por el depto deja su aviso en el historial del administrador).
    entidad_tipo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entidad_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_notificaciones_pendiente",
            "consorcio_id", "entidad_tipo", "entidad_id", "leida",
        ),
    )


class PreferenciaNotificacion(Base):
    """Diferencia contra el default del catálogo, no la tabla completa.

    Un usuario que nunca tocó un interruptor no tiene fila y le vale
    `email_por_defecto` del evento. Eso permite cambiar un default más
    adelante y que alcance a todos los que no opinaron, respetando a los
    que sí. Poner un interruptor en su valor por defecto borra la fila.
    """
    __tablename__ = "preferencias_notificacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    email_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        UniqueConstraint("usuario_id", "tipo", name="uq_preferencia_usuario_tipo"),
    )


class Administracion(Base):
    __tablename__ = "administraciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    cuit: Mapped[str] = mapped_column(String(13), unique=True, nullable=False)
    email_contacto: Mapped[str] = mapped_column(String(255), nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
    # JSON array de keys de módulos habilitados; NULL = todos habilitados.
    modulos_habilitados: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    consorcios: Mapped[list["Consorcio"]] = relationship(back_populates="administracion")


class Consorcio(Base):
    __tablename__ = "consorcios"

    id: Mapped[int] = mapped_column(primary_key=True)
    administracion_id: Mapped[int] = mapped_column(
        ForeignKey("administraciones.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    usa_personal_propio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Datos del consorcio (heredado de ConfiguracionConsorcio)
    consorcio_domicilio: Mapped[str] = mapped_column(String(500), nullable=False)
    consorcio_cuit: Mapped[str] = mapped_column(String(13), nullable=False)
    consorcio_convenio_suterh: Mapped[str | None] = mapped_column(String(50))

    # Administración
    admin_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_domicilio: Mapped[str] = mapped_column(String(500), nullable=False)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_telefono: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_cuit: Mapped[str] = mapped_column(String(13), nullable=False)
    admin_rpa: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_situacion_fiscal: Mapped[str] = mapped_column(String(100), nullable=False)

    # Banco
    banco_titular: Mapped[str] = mapped_column(String(255), nullable=False)
    banco_nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    banco_sucursal: Mapped[str | None] = mapped_column(String(50))
    banco_numero_cuenta: Mapped[str] = mapped_column(String(50), nullable=False)
    banco_cbu: Mapped[str] = mapped_column(String(22), nullable=False)
    banco_alias: Mapped[str | None] = mapped_column(String(50))

    # Vencimientos
    dia_primer_vencimiento: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    dias_entre_vencimientos: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    recargo_segundo_vencimiento_pct: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
    tasa_interes_mensual_pct: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    caja_default_pagos_id: Mapped[int | None] = mapped_column(ForeignKey("cajas.id"), nullable=True)
    reportes_visibles_a_depto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Si está en False, cada departamento ve únicamente sus propias peticiones.
    # Default True: es el comportamiento que el sistema tuvo siempre (todos los
    # roles veían todas las peticiones, para coordinación entre vecinos), así
    # que apagarlo tiene que ser una decisión explícita de la administración.
    peticiones_visibles_a_depto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    administracion: Mapped["Administracion"] = relationship(back_populates="consorcios")


class AuditLogSuperAdmin(Base):
    __tablename__ = "audit_log_super_admin"

    id: Mapped[int] = mapped_column(primary_key=True)
    super_admin_usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    accion: Mapped[str] = mapped_column(String(80), nullable=False)
    administracion_id_afectada: Mapped[int | None] = mapped_column(
        ForeignKey("administraciones.id", ondelete="SET NULL"), nullable=True
    )
    motivo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detalles: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

import enum
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
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
    pagada = "pagada"
    vencida = "vencida"


class EstadoComprobante(str, enum.Enum):
    pendiente_verificacion = "pendiente_verificacion"
    aprobado = "aprobado"
    rechazado = "rechazado"


class EstadoReserva(str, enum.Enum):
    confirmada = "confirmada"
    cancelada = "cancelada"


class Departamento(Base):
    __tablename__ = "departamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255))

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="departamento")
    peticiones: Mapped[list["Peticion"]] = relationship(back_populates="departamento")
    expensas: Mapped[list["Expensa"]] = relationship(back_populates="departamento")


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
    estado: Mapped[EstadoExpensa] = mapped_column(
        SqlEnum(EstadoExpensa, name="estado_expensa"),
        nullable=False,
        default=EstadoExpensa.pendiente,
    )
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)

    departamento: Mapped["Departamento"] = relationship(back_populates="expensas")
    comprobantes: Mapped[list["Comprobante"]] = relationship(
        back_populates="expensa",
        order_by="desc(Comprobante.fecha_creacion), desc(Comprobante.id)",
        lazy="selectin",
    )


class Comprobante(Base):
    __tablename__ = "comprobantes"

    id: Mapped[int] = mapped_column(primary_key=True)
    expensa_id: Mapped[int] = mapped_column(
        ForeignKey("expensas.id", ondelete="RESTRICT"),
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

    expensa: Mapped["Expensa"] = relationship(back_populates="comprobantes")


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

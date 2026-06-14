from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import (
    EstadoComprobante,
    EstadoExpensa,
    EstadoPeticion,
    EstadoPresupuesto,
    EstadoReserva,
    EstadoTrabajo,
    Rol,
)


class ErrorOut(BaseModel):
    detail: str


class LoginIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class CambiarPasswordIn(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    rol: Rol
    departamento_id: int | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UsuarioOut


class PeticionCrear(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=255)
    descripcion: str = Field(..., min_length=1, max_length=2000)


class PeticionActualizar(BaseModel):
    estado: Literal[EstadoPeticion.rechazada]


class PeticionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    departamento_id: int
    titulo: str
    descripcion: str
    estado: EstadoPeticion
    fecha_creacion: datetime


class TrabajoCrear(BaseModel):
    peticion_id: int | None = Field(default=None, gt=0)
    descripcion: str = Field(..., min_length=1, max_length=2000)


class TrabajoActualizar(BaseModel):
    estado: Literal[EstadoTrabajo.finalizado, EstadoTrabajo.cancelado]


class TrabajoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    peticion_id: int | None
    descripcion: str
    estado: EstadoTrabajo
    fecha_creacion: datetime


class PresupuestoCrear(BaseModel):
    proveedor: str = Field(..., min_length=1, max_length=255)
    monto: float = Field(..., gt=0)
    aprobado: bool = False


class PresupuestoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trabajo_id: int
    proveedor: str
    monto: float
    estado: EstadoPresupuesto
    fecha_presentacion: date


class ComunicadoCrear(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=255)
    cuerpo: str = Field(..., min_length=1, max_length=5000)


class ComunicadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    cuerpo: str
    fecha_publicacion: datetime
    autor_id: int


_PERIODO_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class ExpensaCrear(BaseModel):
    departamento_id: int = Field(..., gt=0)
    periodo: str = Field(..., pattern=_PERIODO_PATTERN)
    monto: float = Field(..., gt=0)
    fecha_vencimiento: date


class ComprobanteCrear(BaseModel):
    fecha_pago: date
    monto: float = Field(..., gt=0)
    archivo_url: str | None = Field(default=None, max_length=2048)


class ComprobanteActualizar(BaseModel):
    estado: Literal[EstadoComprobante.aprobado, EstadoComprobante.rechazado]


class ExpensaResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    departamento_id: int
    periodo: str
    monto: float


class ComprobanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    expensa_id: int
    fecha_pago: date
    monto: float
    archivo_url: str | None
    estado: EstadoComprobante
    expensa: ExpensaResumen | None = None


class ExpensaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    departamento_id: int
    periodo: str
    monto: float
    estado: EstadoExpensa
    fecha_vencimiento: date
    ultimo_comprobante: ComprobanteOut | None = None


class ReservaCrear(BaseModel):
    inicio: datetime
    fin: datetime

    @model_validator(mode="after")
    def _validar_orden_temporal(self) -> "ReservaCrear":
        if self.inicio >= self.fin:
            raise ValueError("El campo `inicio` debe ser estrictamente anterior a `fin`.")
        return self


class ReservaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amenity_id: int
    usuario_id: int
    inicio: datetime
    fin: datetime
    estado: EstadoReserva


class BloqueHorarioOut(BaseModel):
    inicio: datetime
    fin: datetime
    disponible: bool


class DisponibilidadOut(BaseModel):
    amenity_id: int
    bloques: list[BloqueHorarioOut]


class AmenityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    descripcion: str | None


class AmenityCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)


class AmenityActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)


class DepartamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    descripcion: str | None


class DepartamentoCrear(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=32)
    descripcion: str | None = Field(default=None, max_length=255)


class DepartamentoActualizar(BaseModel):
    # codigo es inmutable: identifica la unidad funcional en documentos externos.
    descripcion: str | None = Field(default=None, max_length=255)


class UsuarioCrear(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    rol: Rol
    departamento_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validar_consistencia_rol_depto(self) -> "UsuarioCrear":
        if self.rol == Rol.departamento and self.departamento_id is None:
            raise ValueError(
                "Los usuarios con rol `departamento` requieren `departamento_id`."
            )
        if self.rol != Rol.departamento and self.departamento_id is not None:
            raise ValueError(
                "Solo los usuarios con rol `departamento` pueden tener `departamento_id`."
            )
        return self


class UsuarioActualizar(BaseModel):
    # password no editable acá: el propio usuario lo cambia vía /auth/cambiar-password.
    email: str | None = Field(default=None, min_length=3, max_length=255)
    rol: Rol | None = None
    departamento_id: int | None = Field(default=None, gt=0)

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from .models import (
    CategoriaEmpleado,
    EstadoComprobante,
    EstadoExpensa,
    EstadoPeticion,
    EstadoPresupuesto,
    EstadoReserva,
    EstadoTrabajo,
    FormaPago,
    Rol,
    Rubro,
    TipoConcepto,
    TipoHaber,
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
    archivo_path: str | None
    estado: EstadoComprobante
    expensa: ExpensaResumen | None = None

    @field_serializer("archivo_path")
    def _archivo_path_to_url(self, v: str | None) -> str | None:
        if v is None:
            return None
        return f"/uploads/{v}"


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


class ClaseProrrateoCrear(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=8)
    nombre: str = Field(..., min_length=1, max_length=120)
    descripcion: str | None = Field(default=None, max_length=500)


class ClaseProrrateoActualizar(BaseModel):
    # codigo es inmutable
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    descripcion: str | None = Field(default=None, max_length=500)
    activa: bool | None = None


class ClaseProrrateoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str
    descripcion: str | None
    activa: bool


_CUIT_PATTERN = r"^\d{2}-\d{8}-\d{1}$"


class ProveedorCrear(BaseModel):
    razon_social: str = Field(..., min_length=1, max_length=255)
    nombre_fantasia: str | None = Field(default=None, max_length=255)
    cuit: str = Field(..., pattern=_CUIT_PATTERN)
    direccion: str | None = Field(default=None, max_length=500)


class ProveedorActualizar(BaseModel):
    # cuit es inmutable
    razon_social: str | None = Field(default=None, min_length=1, max_length=255)
    nombre_fantasia: str | None = Field(default=None, max_length=255)
    direccion: str | None = Field(default=None, max_length=500)
    activo: bool | None = None


class ProveedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    razon_social: str
    nombre_fantasia: str | None
    cuit: str
    direccion: str | None
    activo: bool


class ConfiguracionConsorcioActualizar(BaseModel):
    consorcio_nombre: str = Field(..., min_length=1, max_length=255)
    consorcio_domicilio: str = Field(..., min_length=1, max_length=500)
    consorcio_cuit: str = Field(..., pattern=_CUIT_PATTERN)
    consorcio_convenio_suterh: str | None = Field(default=None, max_length=50)

    admin_nombre: str = Field(..., min_length=1, max_length=255)
    admin_domicilio: str = Field(..., min_length=1, max_length=500)
    admin_email: str = Field(..., min_length=3, max_length=255)
    admin_telefono: str = Field(..., min_length=1, max_length=50)
    admin_cuit: str = Field(..., pattern=_CUIT_PATTERN)
    admin_rpa: str = Field(..., min_length=1, max_length=50)
    admin_situacion_fiscal: str = Field(..., min_length=1, max_length=100)

    banco_titular: str = Field(..., min_length=1, max_length=255)
    banco_nombre: str = Field(..., min_length=1, max_length=100)
    banco_sucursal: str | None = Field(default=None, max_length=50)
    banco_numero_cuenta: str = Field(..., min_length=1, max_length=50)
    banco_cbu: str = Field(..., min_length=22, max_length=22)
    banco_alias: str | None = Field(default=None, max_length=50)


class ConfiguracionConsorcioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    consorcio_nombre: str
    consorcio_domicilio: str
    consorcio_cuit: str
    consorcio_convenio_suterh: str | None
    admin_nombre: str
    admin_domicilio: str
    admin_email: str
    admin_telefono: str
    admin_cuit: str
    admin_rpa: str
    admin_situacion_fiscal: str
    banco_titular: str
    banco_nombre: str
    banco_sucursal: str | None
    banco_numero_cuenta: str
    banco_cbu: str
    banco_alias: str | None


class CoeficienteItem(BaseModel):
    clase_prorrateo_id: int = Field(..., gt=0)
    porcentaje: float = Field(..., ge=0, le=100)


class CoeficientesReemplazar(BaseModel):
    coeficientes: list[CoeficienteItem]

    @model_validator(mode="after")
    def _validar_clases_unicas(self) -> "CoeficientesReemplazar":
        ids = [c.clase_prorrateo_id for c in self.coeficientes]
        if len(ids) != len(set(ids)):
            raise ValueError("No puede repetirse `clase_prorrateo_id` en el payload.")
        return self


class CoeficienteOut(BaseModel):
    clase_prorrateo_id: int
    codigo: str
    nombre: str
    porcentaje: float


class GastoHabitualCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    rubro: Rubro
    clase_prorrateo_id: int = Field(..., gt=0)
    proveedor_id: int = Field(..., gt=0)
    concepto: str = Field(..., min_length=1, max_length=500)
    monto: float = Field(..., gt=0)
    forma_pago: FormaPago


class GastoHabitualActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    rubro: Rubro | None = None
    clase_prorrateo_id: int | None = Field(default=None, gt=0)
    proveedor_id: int | None = Field(default=None, gt=0)
    concepto: str | None = Field(default=None, min_length=1, max_length=500)
    monto: float | None = Field(default=None, gt=0)
    forma_pago: FormaPago | None = None
    activa: bool | None = None


class GastoHabitualOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    rubro: Rubro
    clase_prorrateo_id: int
    proveedor_id: int
    concepto: str
    monto: float
    forma_pago: FormaPago
    activa: bool


_PERIODO_PATTERN_GASTO = r"^\d{4}-(0[1-9]|1[0-2])$"


class GastoCrear(BaseModel):
    periodo: str = Field(..., pattern=_PERIODO_PATTERN_GASTO)
    rubro: Rubro
    clase_prorrateo_id: int | None = Field(default=None, gt=0)
    departamento_id: int | None = Field(default=None, gt=0)
    proveedor_id: int = Field(..., gt=0)
    concepto: str = Field(..., min_length=1, max_length=500)
    monto: float = Field(..., gt=0)
    forma_pago: FormaPago
    fecha_pago: date
    numero_factura: str | None = Field(default=None, max_length=50)
    fecha_factura: date | None = None
    cuota_actual: int | None = Field(default=None, ge=1)
    cuota_total: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validar_clase_o_depto(self) -> "GastoCrear":
        tiene_clase = self.clase_prorrateo_id is not None
        tiene_depto = self.departamento_id is not None
        if tiene_clase == tiene_depto:
            raise ValueError(
                "Debe indicarse exactamente uno de `clase_prorrateo_id` "
                "o `departamento_id` (excluyentes)."
            )
        return self

    @model_validator(mode="after")
    def _validar_cuotas(self) -> "GastoCrear":
        a = self.cuota_actual
        t = self.cuota_total
        if (a is None) != (t is None):
            raise ValueError(
                "`cuota_actual` y `cuota_total` deben ir ambos o ninguno."
            )
        if a is not None and t is not None and a > t:
            raise ValueError("`cuota_actual` no puede exceder `cuota_total`.")
        return self


class GastoActualizar(BaseModel):
    periodo: str | None = Field(default=None, pattern=_PERIODO_PATTERN_GASTO)
    rubro: Rubro | None = None
    clase_prorrateo_id: int | None = Field(default=None, gt=0)
    departamento_id: int | None = Field(default=None, gt=0)
    proveedor_id: int | None = Field(default=None, gt=0)
    concepto: str | None = Field(default=None, min_length=1, max_length=500)
    monto: float | None = Field(default=None, gt=0)
    forma_pago: FormaPago | None = None
    fecha_pago: date | None = None
    numero_factura: str | None = Field(default=None, max_length=50)
    fecha_factura: date | None = None
    cuota_actual: int | None = Field(default=None, ge=1)
    cuota_total: int | None = Field(default=None, ge=1)


class GastoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    periodo: str
    rubro: Rubro
    clase_prorrateo_id: int | None
    departamento_id: int | None
    proveedor_id: int
    concepto: str
    monto: float
    forma_pago: FormaPago
    fecha_pago: date
    numero_factura: str | None
    fecha_factura: date | None
    cuota_actual: int | None
    cuota_total: int | None
    gasto_habitual_id: int | None
    liquidacion_id: int | None = None


class PlanCuotasCrear(BaseModel):
    """Body para POST /gastos/plan-cuotas. Reutiliza casi todos los campos de
    GastoCrear pero exige cuota_total ≥ 2 (uno solo no es un plan)."""
    periodo: str = Field(..., pattern=_PERIODO_PATTERN_GASTO)
    rubro: Rubro
    clase_prorrateo_id: int | None = Field(default=None, gt=0)
    departamento_id: int | None = Field(default=None, gt=0)
    proveedor_id: int = Field(..., gt=0)
    concepto: str = Field(..., min_length=1, max_length=500)
    monto: float = Field(..., gt=0)
    forma_pago: FormaPago
    fecha_pago: date
    numero_factura: str | None = Field(default=None, max_length=50)
    fecha_factura: date | None = None
    cuota_total: int = Field(..., ge=2)

    @model_validator(mode="after")
    def _validar_clase_o_depto(self) -> "PlanCuotasCrear":
        if (self.clase_prorrateo_id is None) == (self.departamento_id is None):
            raise ValueError(
                "Debe indicarse exactamente uno de `clase_prorrateo_id` "
                "o `departamento_id` (excluyentes)."
            )
        return self


class CargarHabitualesIn(BaseModel):
    periodo: str = Field(..., pattern=_PERIODO_PATTERN_GASTO)


# El CUIL/CUIT comparte el mismo formato XX-XXXXXXXX-X. Reutilizamos el pattern.
_CUIL_PATTERN = _CUIT_PATTERN


class EmpleadoCrear(BaseModel):
    nombre_completo: str = Field(..., min_length=1, max_length=255)
    cuil: str = Field(..., pattern=_CUIL_PATTERN)
    categoria: CategoriaEmpleado
    fecha_ingreso: date
    fecha_egreso: date | None = None
    sueldo_basico: float = Field(..., gt=0)
    proveedor_id: int = Field(..., gt=0)


class EmpleadoActualizar(BaseModel):
    # cuil inmutable
    nombre_completo: str | None = Field(default=None, min_length=1, max_length=255)
    categoria: CategoriaEmpleado | None = None
    fecha_ingreso: date | None = None
    fecha_egreso: date | None = None
    sueldo_basico: float | None = Field(default=None, gt=0)
    proveedor_id: int | None = Field(default=None, gt=0)
    activo: bool | None = None


class EmpleadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_completo: str
    cuil: str
    categoria: CategoriaEmpleado
    fecha_ingreso: date
    fecha_egreso: date | None
    sueldo_basico: float
    proveedor_id: int
    activo: bool


class HaberCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    tipo: TipoHaber
    valor_default: float = Field(default=0, ge=0)
    orden: int = Field(default=0, ge=0)


class HaberActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: TipoHaber | None = None
    valor_default: float | None = Field(default=None, ge=0)
    orden: int | None = Field(default=None, ge=0)
    activo: bool | None = None


class HaberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoHaber
    valor_default: float
    orden: int
    activo: bool


class ConceptoLiquidacionCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    tipo: TipoConcepto
    porcentaje: float = Field(..., ge=0, le=100)
    proveedor_id: int | None = Field(default=None, gt=0)
    orden: int = Field(default=0, ge=0)


class ConceptoLiquidacionActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: TipoConcepto | None = None
    porcentaje: float | None = Field(default=None, ge=0, le=100)
    proveedor_id: int | None = Field(default=None, gt=0)
    orden: int | None = Field(default=None, ge=0)
    activo: bool | None = None


class ConceptoLiquidacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoConcepto
    porcentaje: float
    proveedor_id: int | None
    orden: int
    activo: bool


class LiquidacionHaberItem(BaseModel):
    """Item de haber del catálogo a aplicar en la liquidación."""
    haber_id: int = Field(..., gt=0)
    valor_override: float | None = Field(default=None, ge=0)
    cantidad: float | None = Field(default=None, ge=0)


class LiquidacionHaberAdHoc(BaseModel):
    """Haber suelto sin catálogo (ej. SAC)."""
    nombre: str = Field(..., min_length=1, max_length=120)
    monto: float = Field(..., gt=0)


class LiquidacionEmpleadoCrear(BaseModel):
    empleado_id: int = Field(..., gt=0)
    periodo: str = Field(..., pattern=_PERIODO_PATTERN_GASTO)
    haberes: list[LiquidacionHaberItem] = Field(default_factory=list)
    haberes_ad_hoc: list[LiquidacionHaberAdHoc] = Field(default_factory=list)


class LiquidacionEmpleadoActualizar(BaseModel):
    haberes: list[LiquidacionHaberItem] = Field(default_factory=list)
    haberes_ad_hoc: list[LiquidacionHaberAdHoc] = Field(default_factory=list)


class LiquidacionHaberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoHaber | None
    valor: float | None
    cantidad: float | None
    monto: float
    orden: int


class LiquidacionDetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    concepto_nombre: str
    concepto_tipo: TipoConcepto
    porcentaje_aplicado: float
    monto: float
    proveedor_id: int | None
    orden: int


class LiquidacionEmpleadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    empleado_id: int
    periodo: str
    sueldo_bruto: float
    fecha_creacion: datetime
    haberes: list[LiquidacionHaberOut]
    detalle: list[LiquidacionDetalleOut]

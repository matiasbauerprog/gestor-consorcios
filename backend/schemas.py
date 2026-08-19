from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

from .models import (
    CategoriaEmpleado,
    EstadoComprobante,
    EstadoExpensa,
    EstadoPeticion,
    EstadoPresupuesto,
    EstadoReserva,
    EstadoTrabajo,
    FormaPago,
    PeriodicidadRecurrente,
    Rol,
    Rubro,
    TipoCaja,
    TipoConcepto,
    TipoHaber,
    TipoMovimiento,
    TipoMovimientoCaja,
)


def _marcar_utc(valor: datetime) -> datetime:
    """Le pone la zona UTC al instante si viene sin ella.

    Todo lo que la base guarda es UTC —lo escriba ella con `func.now()` o lo
    escriba Python—, pero SQLite no guarda la zona, así que vuelve sin marca.
    Serializado sin marca, el navegador lo lee como hora LOCAL y se corre por
    el offset del huso: la campanita calculaba "hace cuánto" con una resta
    negativa y mostraba "recién" en avisos de hace horas.
    """
    return valor if valor.tzinfo is not None else valor.replace(tzinfo=timezone.utc)


#: Instante que sale al navegador. Usar en TODA salida de fecha y hora que
#: venga de la base; las fechas comerciales (pago, factura, vencimiento) son
#: `date` local y no llevan esto.
InstanteUtc = Annotated[datetime, PlainSerializer(_marcar_utc, return_type=datetime)]


class ErrorOut(BaseModel):
    detail: str


class LoginIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class DemoLoginIn(BaseModel):
    """Body de POST /auth/demo-login.

    `Literal` cierra la lista blanca a nivel schema: cualquier otro valor lo
    rechaza Pydantic con 400 antes de llegar al router.
    """
    rol: Literal["administracion", "propietario_al_dia", "propietario_moroso"]


class CambiarPasswordIn(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)


class RecuperarPasswordIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


class RestablecerPasswordIn(BaseModel):
    token: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    rol: Rol
    departamento_id: int | None
    activa: bool
    must_change_password: bool


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
    # Opcional: rechazar sin explicación sigue siendo válido (es lo que hacía
    # el sistema antes de que existiera este campo), pero la UI lo pide.
    motivo_rechazo: str | None = Field(default=None, max_length=1000)


class PeticionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    departamento_id: int
    titulo: str
    descripcion: str
    estado: EstadoPeticion
    motivo_rechazo: str | None = None
    fecha_creacion: InstanteUtc


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
    fecha_creacion: InstanteUtc
    # La pantalla de Trabajos tiene una columna para cada uno. Sin devolverlos
    # muestran un guión siempre, incluso en un trabajo finalizado que sí tiene
    # presupuesto aprobado y gasto asociado.
    presupuesto_aprobado_id: int | None
    gasto_id: int | None


class PresupuestoCrear(BaseModel):
    proveedor_id: int = Field(..., gt=0)
    monto: float = Field(..., gt=0)
    aprobado: bool = False


class PresupuestoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trabajo_id: int
    proveedor_id: int
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
    fecha_publicacion: InstanteUtc
    autor_id: int


_PERIODO_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class ExpensaCrear(BaseModel):
    departamento_id: int = Field(..., gt=0)
    periodo: str = Field(..., pattern=_PERIODO_PATTERN)
    monto_primer_vencimiento: float = Field(..., gt=0)
    fecha_primer_vencimiento: date
    monto_segundo_vencimiento: float = Field(..., gt=0)
    fecha_segundo_vencimiento: date



class ComprobanteActualizar(BaseModel):
    estado: Literal[EstadoComprobante.aprobado, EstadoComprobante.rechazado]
    caja_destino_id: int | None = None
    # Sólo se guarda al rechazar; en una aprobación se ignora.
    motivo_rechazo: str | None = Field(default=None, max_length=1000)


class ErrorRegistradoOut(BaseModel):
    """Un error inesperado, tal como lo ve el super admin.

    Incluye la traza a propósito: el destinatario es quien mantiene el sistema,
    y sin la traza la pantalla no serviría para diagnosticar. Nunca se expone a
    ningún otro rol.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    ocurrido_at: InstanteUtc
    ruta: str
    metodo: str
    tipo: str
    mensaje: str
    traza: str
    usuario_id: int | None
    rol: str | None
    consorcio_id: int | None


class ArchivoUrlOut(BaseModel):
    """URL de vida corta para abrir un archivo adjunto.

    Se entrega por separado del recurso porque `<img src>` no manda headers:
    el frontend pide esto con su token y usa la URL resultante como src.
    """

    url: str
    expira_en: int


class ComprobanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    departamento_id: int
    departamento_codigo: str
    fecha_pago: date
    monto: float
    archivo_path: str | None
    estado: EstadoComprobante
    motivo_rechazo: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _inject_depto_codigo(cls, data):
        # from_attributes: si viene un ORM sin `departamento_codigo`, lo
        # derivamos de la relación `departamento`.
        if hasattr(data, "departamento") and not isinstance(data, dict):
            cols = {c.name: getattr(data, c.name, None) for c in data.__table__.columns}
            cols["departamento_codigo"] = data.departamento.codigo if data.departamento else "?"
            return cols
        return data


class ComprobantePresentar(BaseModel):
    fecha_pago: date
    monto: float = Field(gt=0)


class LineaDetalleExpensaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rubro: Rubro
    clase_prorrateo_id: int | None
    departamento_origen_id: int | None
    concepto: str
    monto: float


class ExpensaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    departamento_id: int
    periodo: str
    monto_primer_vencimiento: float
    fecha_primer_vencimiento: date
    monto_segundo_vencimiento: float
    fecha_segundo_vencimiento: date
    saldo_anterior: float
    estado_calculado: EstadoExpensa
    monto_pendiente: float
    monto_exigible: float
    interes_acumulado: float
    detalle: list[LineaDetalleExpensaOut]


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
    movimiento_cuenta_id: int | None


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
    activo: bool
    precio_reserva: float | None
    duracion_maxima_horas: int | None
    anticipacion_maxima_dias: int | None
    max_reservas_activas_por_depto: int | None
    horas_minimas_cancelacion: int | None


class AmenityCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)
    precio_reserva: float | None = Field(default=None, ge=0)
    duracion_maxima_horas: int | None = Field(default=None, gt=0)
    anticipacion_maxima_dias: int | None = Field(default=None, gt=0)
    max_reservas_activas_por_depto: int | None = Field(default=None, gt=0)
    horas_minimas_cancelacion: int | None = Field(default=None, ge=0)


class AmenityActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)
    activo: bool | None = None
    precio_reserva: float | None = Field(default=None, ge=0)
    duracion_maxima_horas: int | None = Field(default=None, gt=0)
    anticipacion_maxima_dias: int | None = Field(default=None, gt=0)
    max_reservas_activas_por_depto: int | None = Field(default=None, gt=0)
    horas_minimas_cancelacion: int | None = Field(default=None, ge=0)


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


class CoeficienteBulkItem(BaseModel):
    departamento_id: int = Field(..., gt=0)
    clase_prorrateo_id: int = Field(..., gt=0)
    porcentaje: float = Field(..., ge=0, le=100)


class CoeficientesBulkIn(BaseModel):
    coeficientes: list[CoeficienteBulkItem]

    @model_validator(mode="after")
    def _sin_duplicados(self) -> "CoeficientesBulkIn":
        pares = {(c.departamento_id, c.clase_prorrateo_id) for c in self.coeficientes}
        if len(pares) != len(self.coeficientes):
            raise ValueError(
                "Hay pares (departamento_id, clase_prorrateo_id) duplicados."
            )
        return self


class PadronImportItemOut(BaseModel):
    codigo: str
    ubicacion: str | None = None
    email: str | None = None
    depto_status: Literal["creado", "reutilizado", "error"]
    usuario_status: Literal["creado", "sin_usuario", "error"]
    password_generada: str | None = None
    error: str | None = None


class PadronImportarResultado(BaseModel):
    resultados: list[PadronImportItemOut]


class CuentaResumenOut(BaseModel):
    departamento_id: int
    codigo: str
    ubicacion: str | None
    saldo_total: float
    en_mora: bool


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


class UsuarioEstado(BaseModel):
    activa: bool


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

    # vencimientos e intereses (Fase 4)
    dia_primer_vencimiento: int = Field(..., ge=1, le=28)
    dias_entre_vencimientos: int = Field(..., ge=1)
    recargo_segundo_vencimiento_pct: float = Field(..., ge=0)
    tasa_interes_mensual_pct: float = Field(..., ge=0)

    # cajas (Fase 5)
    caja_default_pagos_id: int | None = None

    # visibilidad de reportes para departamentos (Fase 6b)
    reportes_visibles_a_depto: bool = False

    # ¿un departamento ve las peticiones de los demás, o sólo las suyas?
    # Default True porque es el comportamiento histórico: un PUT viejo que no
    # mande el campo no debe apagar la visibilidad sin que nadie lo pida.
    peticiones_visibles_a_depto: bool = True


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
    dia_primer_vencimiento: int
    dias_entre_vencimientos: int
    recargo_segundo_vencimiento_pct: float
    tasa_interes_mensual_pct: float
    caja_default_pagos_id: int | None
    reportes_visibles_a_depto: bool
    peticiones_visibles_a_depto: bool


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
    caja_id: int


class GastoHabitualActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    rubro: Rubro | None = None
    clase_prorrateo_id: int | None = Field(default=None, gt=0)
    proveedor_id: int | None = Field(default=None, gt=0)
    concepto: str | None = Field(default=None, min_length=1, max_length=500)
    monto: float | None = Field(default=None, gt=0)
    forma_pago: FormaPago | None = None
    caja_id: int | None = None
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
    caja_id: int
    fecha_pago: date
    numero_factura: str | None = Field(default=None, max_length=50)
    fecha_factura: date | None = None
    cuota_actual: int | None = Field(default=None, ge=1)
    cuota_total: int | None = Field(default=None, ge=1)
    trabajo_id: int | None = None  # Fase 11: marca el trabajo como completado

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
    caja_id: int | None = None
    fecha_pago: date | None = None
    numero_factura: str | None = Field(default=None, max_length=50)
    fecha_factura: date | None = None
    cuota_actual: int | None = Field(default=None, ge=1)
    cuota_total: int | None = Field(default=None, ge=1)


class GastoPagar(BaseModel):
    """Confirma el pago real de un gasto devengado. El monto puede diferir del
    de la plantilla: la factura manda."""
    monto: float = Field(..., gt=0)
    fecha_pago: date
    caja_id: int = Field(..., gt=0)


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
    pagado: bool
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
    caja_id: int
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
    caja_id: int
    haberes: list[LiquidacionHaberItem] = Field(default_factory=list)
    haberes_ad_hoc: list[LiquidacionHaberAdHoc] = Field(default_factory=list)


class LiquidacionEmpleadoActualizar(BaseModel):
    caja_id: int | None = None
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
    fecha_creacion: InstanteUtc
    haberes: list[LiquidacionHaberOut]
    detalle: list[LiquidacionDetalleOut]


class MovimientoCuentaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    departamento_id: int
    fecha: date
    tipo: TipoMovimiento
    descripcion: str
    monto: float
    expensa_id: int | None = None
    comprobante_id: int | None = None
    fecha_creacion: InstanteUtc


class EstadoCuentaOut(BaseModel):
    departamento_id: int
    departamento_codigo: str
    departamento_ubicacion: str | None
    saldo_total: float
    movimientos: list[MovimientoCuentaOut]


class NotaCrear(BaseModel):
    departamento_id: int
    tipo: TipoMovimiento
    monto: float = Field(gt=0)
    descripcion: str = Field(min_length=1, max_length=500)
    fecha: date | None = None

    @field_validator("tipo")
    @classmethod
    def solo_nota(cls, v: TipoMovimiento) -> TipoMovimiento:
        if v not in (TipoMovimiento.nota_credito, TipoMovimiento.nota_debito):
            raise ValueError("tipo debe ser nota_credito o nota_debito")
        return v


# ─── Fase 4: Cierre de período ────────────────────────────────────────────

class ValidacionOut(BaseModel):
    tipo: Literal["bloqueante", "warning"]
    codigo: str
    mensaje: str


class InteresACrearOut(BaseModel):
    departamento_id: int
    monto: float
    descripcion: str


class ExpensaACrearOut(BaseModel):
    departamento_id: int
    saldo_anterior: float
    monto_primer_vencimiento: float
    monto_segundo_vencimiento: float
    detalle: list[LineaDetalleExpensaOut]


class PreviewCierreOut(BaseModel):
    periodo: str
    cerrado: bool
    fecha_primer_vencimiento: date
    fecha_segundo_vencimiento: date
    validaciones: list[ValidacionOut]
    puede_cerrar: bool
    expensas: list[ExpensaACrearOut]
    intereses: list[InteresACrearOut]
    total_expensado: float
    total_intereses: float


class EstadoCierreOut(BaseModel):
    """Subset de PreviewCierreOut: solo validaciones, sin números."""
    periodo: str
    cerrado: bool
    validaciones: list[ValidacionOut]
    puede_cerrar: bool


class CerrarPeriodoIn(BaseModel):
    fecha_primer_vencimiento: date | None = None
    fecha_segundo_vencimiento: date | None = None


class PeriodoCerradoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    periodo: str
    fecha_cierre: InstanteUtc
    cerrado_por_usuario_id: int
    total_expensado: float
    total_intereses: float
    cantidad_expensas: int


# === Cajas (Fase 5) ===

class CajaCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    tipo: TipoCaja
    descripcion: str | None = Field(None, max_length=500)
    saldo_inicial: float = Field(default=0.0)
    activa: bool = Field(default=True)


class CajaActualizar(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=100)
    descripcion: str | None = Field(None, max_length=500)
    activa: bool | None = None


class CajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoCaja
    descripcion: str | None
    saldo_inicial: float
    saldo_actual: float  # calculado en el router
    activa: bool


class AjusteCrear(BaseModel):
    fecha: date
    monto: float = Field(..., description="Positivo o negativo. Suma/resta al saldo.")
    descripcion: str = Field(..., min_length=5, max_length=500)


class MovimientoCajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    caja_id: int
    fecha: date
    tipo: TipoMovimientoCaja
    monto: float
    descripcion: str
    gasto_id: int | None
    comprobante_id: int | None
    transferencia_id: int | None


class TransferenciaCajaCrear(BaseModel):
    caja_origen_id: int
    caja_destino_id: int
    monto: float = Field(..., gt=0)
    fecha: date
    descripcion: str = Field(..., min_length=1, max_length=500)


class TransferenciaCajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    caja_origen_id: int
    caja_destino_id: int
    monto: float
    fecha: date
    descripcion: str


class ResumenTesoreriaOut(BaseModel):
    cajas: list[CajaOut]
    total: float
    ultimos_movimientos: list[MovimientoCajaOut]


# === Fase 6a — envío masivo PDFs ===

class EnviarPdfsIn(BaseModel):
    confirmar_sin_cerrar: bool = False


class ErrorEnvioOut(BaseModel):
    depto_id: int
    email: str | None
    motivo: str


class EnviarPdfsOut(BaseModel):
    enviados: int
    fallaron: int
    errores: list[ErrorEnvioOut]


# === Fase 6b — Reportes ===

class ItemMorosoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    departamento_id: int
    departamento_codigo: str
    saldo: float
    periodos_vencidos_impagos: int
    primer_vencimiento_impago: date | None


class ItemActivoCajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    caja_id: int
    nombre: str
    saldo: float


class ItemPasivoGastoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    gasto_id: int
    proveedor: str
    concepto: str
    monto: float
    fecha_registrada: date


class EstadoFinancieroReporteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    fecha_corte: date
    cajas: list[ItemActivoCajaOut]
    deudores_total: float
    pasivos: list[ItemPasivoGastoOut]
    activo_total: float
    pasivo_total: float
    patrimonio_neto: float


class ItemGastoDetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    fecha: date
    concepto: str
    rubro: str
    proveedor: str
    forma_pago: str
    caja: str
    monto: float
    es_particular: bool


class GastosDelPeriodoReporteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    periodo: str
    por_rubro: dict[str, list[ItemGastoDetalleOut]]
    particulares: list[ItemGastoDetalleOut]
    subtotales_por_rubro: dict[str, float]
    total_general: float


class ItemProveedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    proveedor_id: int
    razon_social: str
    cuit: str
    cantidad_gastos: int
    total_facturado: float
    ultimo_gasto: date | None


# === Fase 11 — Tareas y Presupuestos ===

class PresupuestoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    trabajo_id: int
    proveedor_id: int
    monto: float
    estado: EstadoPresupuesto
    fecha_presentacion: date
    archivo_path: str | None
    observaciones: str | None


class PresupuestoActualizar(BaseModel):
    proveedor_id: int | None = None
    monto: float | None = Field(None, gt=0)
    fecha_presentacion: date | None = None
    observaciones: str | None = Field(None, max_length=1000)


class TrabajoRecurrenteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    descripcion: str
    periodicidad: PeriodicidadRecurrente
    proveedor_sugerido_id: int | None
    monto_estimado: float | None
    activa: bool


class TrabajoRecurrenteCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=255)
    descripcion: str = Field(..., min_length=1, max_length=2000)
    periodicidad: PeriodicidadRecurrente
    proveedor_sugerido_id: int | None = None
    monto_estimado: float | None = Field(None, ge=0)
    activa: bool = True


class TrabajoRecurrenteActualizar(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=255)
    descripcion: str | None = Field(None, min_length=1, max_length=2000)
    periodicidad: PeriodicidadRecurrente | None = None
    proveedor_sugerido_id: int | None = None
    monto_estimado: float | None = Field(None, ge=0)
    activa: bool | None = None


class NotificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    usuario_id: int
    tipo: str
    mensaje: str
    link: str | None
    leida: bool
    created_at: InstanteUtc


class NotificacionesCountOut(BaseModel):
    count: int
    # No leídas del usuario en los OTROS consorcios de su administración.
    # Siempre 0 para departamento y representante: tienen uno solo.
    otros_consorcios: int = 0


class PreferenciaNotificacionOut(BaseModel):
    tipo: str
    etiqueta: str
    email_activo: bool
    # False ⇒ el interruptor se muestra pero no se puede tocar.
    editable: bool
    motivo_no_editable: str | None


class PreferenciaNotificacionIn(BaseModel):
    tipo: str
    email_activo: bool


class CompletarTrabajoOut(BaseModel):
    proveedor_id: int
    monto: float
    concepto_sugerido: str
    trabajo_id: int


# ---------------------------------------------------------------------------
# Super-admin (Plan B)
# ---------------------------------------------------------------------------


class AdministracionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    razon_social: str
    cuit: str
    email_contacto: str
    activa: bool
    plan: str
    fecha_creacion: InstanteUtc


class AdministracionCrear(BaseModel):
    razon_social: str = Field(min_length=1, max_length=255)
    cuit: str = Field(min_length=1, max_length=13)
    email_contacto: str = Field(min_length=3, max_length=255)
    admin_email: str = Field(min_length=3, max_length=255)
    admin_password_inicial: str = Field(min_length=8, max_length=128)


class AdministracionActualizar(BaseModel):
    razon_social: str | None = Field(default=None, min_length=1, max_length=255)
    email_contacto: str | None = Field(default=None, min_length=3, max_length=255)
    plan: str | None = Field(default=None, max_length=50)


class ModulosAdministracionIn(BaseModel):
    habilitados: list[str]


class ModulosAdministracionOut(BaseModel):
    disponibles: list[str]
    habilitados: list[str]


class ResetPasswordOut(BaseModel):
    password_temporal: str


class UsuarioAdminOut(BaseModel):
    id: int
    email: str
    rol: Rol
    departamento_id: int | None = None
    consorcio_id: int | None = None
    must_change_password: bool

    model_config = ConfigDict(from_attributes=True)


class ImpersonateStartIn(BaseModel):
    usuario_id: int = Field(ge=1)
    motivo: str = Field(min_length=10, max_length=500)


class ImpersonateStartOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    impersonated_user_id: int


class MetricasOut(BaseModel):
    administraciones: dict
    consorcios: dict
    departamentos: dict
    expensas_ultimo_mes: dict
    impersonates_ultimos_30_dias: int


class AuditLogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    super_admin_usuario_id: int
    accion: str
    administracion_id_afectada: int | None
    motivo: str | None
    detalles: str | None
    fecha: InstanteUtc


# ---------------------------------------------------------------------------
# Consorcios (Plan D — reemplaza los endpoints singleton /configuracion)
# ---------------------------------------------------------------------------


class ConsorcioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    administracion_id: int
    nombre: str
    usa_personal_propio: bool
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
    dia_primer_vencimiento: int
    dias_entre_vencimientos: int
    recargo_segundo_vencimiento_pct: float
    tasa_interes_mensual_pct: float
    caja_default_pagos_id: int | None
    reportes_visibles_a_depto: bool
    peticiones_visibles_a_depto: bool
    fecha_creacion: InstanteUtc
    modulos_habilitados: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _inject_modulos(cls, data):
        # from_attributes: si viene un ORM con la relación `administracion`,
        # derivamos `modulos_habilitados` desde ella.
        if hasattr(data, "administracion") and not isinstance(data, dict):
            from .modulos import modulos_habilitados_de
            cols = {c.name: getattr(data, c.name, None) for c in data.__table__.columns}
            admin = data.administracion
            cols["modulos_habilitados"] = sorted(modulos_habilitados_de(admin)) if admin else []
            return cols
        return data


class ConsorcioCrear(BaseModel):
    # Paso 1
    nombre: str = Field(min_length=1, max_length=255)
    consorcio_domicilio: str = Field(min_length=1, max_length=500)
    consorcio_cuit: str = Field(min_length=1, max_length=13)
    consorcio_convenio_suterh: str | None = Field(default=None, max_length=50)
    usa_personal_propio: bool = True

    # Paso 2
    admin_nombre: str = Field(min_length=1, max_length=255)
    admin_domicilio: str = Field(min_length=1, max_length=500)
    admin_email: str = Field(min_length=3, max_length=255)
    admin_telefono: str = Field(min_length=1, max_length=50)
    admin_cuit: str = Field(min_length=1, max_length=13)
    admin_rpa: str = Field(min_length=1, max_length=50)
    admin_situacion_fiscal: str = Field(min_length=1, max_length=100)

    # Paso 3
    banco_titular: str = Field(min_length=1, max_length=255)
    banco_nombre: str = Field(min_length=1, max_length=100)
    banco_sucursal: str | None = Field(default=None, max_length=50)
    banco_numero_cuenta: str = Field(min_length=1, max_length=50)
    banco_cbu: str = Field(min_length=1, max_length=22)
    banco_alias: str | None = Field(default=None, max_length=50)

    # Paso 4
    dia_primer_vencimiento: int = Field(default=10, ge=1, le=28)
    dias_entre_vencimientos: int = Field(default=10, ge=1, le=30)
    recargo_segundo_vencimiento_pct: float = Field(default=7.0, ge=0, le=100)
    tasa_interes_mensual_pct: float = Field(default=3.0, ge=0, le=100)
    reportes_visibles_a_depto: bool = False
    peticiones_visibles_a_depto: bool = True


class ConsorcioActualizar(BaseModel):
    # Solo campos editables por el admin desde "Datos del consorcio".
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    usa_personal_propio: bool | None = None
    consorcio_domicilio: str | None = Field(default=None, min_length=1, max_length=500)
    consorcio_cuit: str | None = Field(default=None, min_length=1, max_length=13)
    consorcio_convenio_suterh: str | None = Field(default=None, max_length=50)
    admin_nombre: str | None = Field(default=None, min_length=1, max_length=255)
    admin_domicilio: str | None = Field(default=None, min_length=1, max_length=500)
    admin_email: str | None = Field(default=None, min_length=3, max_length=255)
    admin_telefono: str | None = Field(default=None, min_length=1, max_length=50)
    admin_cuit: str | None = Field(default=None, min_length=1, max_length=13)
    admin_rpa: str | None = Field(default=None, min_length=1, max_length=50)
    admin_situacion_fiscal: str | None = Field(default=None, min_length=1, max_length=100)
    banco_titular: str | None = Field(default=None, min_length=1, max_length=255)
    banco_nombre: str | None = Field(default=None, min_length=1, max_length=100)
    banco_sucursal: str | None = Field(default=None, max_length=50)
    banco_numero_cuenta: str | None = Field(default=None, min_length=1, max_length=50)
    banco_cbu: str | None = Field(default=None, min_length=1, max_length=22)
    banco_alias: str | None = Field(default=None, max_length=50)
    dia_primer_vencimiento: int | None = Field(default=None, ge=1, le=28)
    dias_entre_vencimientos: int | None = Field(default=None, ge=1, le=30)
    recargo_segundo_vencimiento_pct: float | None = Field(default=None, ge=0, le=100)
    tasa_interes_mensual_pct: float | None = Field(default=None, ge=0, le=100)
    caja_default_pagos_id: int | None = Field(default=None, ge=1)
    reportes_visibles_a_depto: bool | None = None
    peticiones_visibles_a_depto: bool | None = None

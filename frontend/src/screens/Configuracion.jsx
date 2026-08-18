import { useEffect, useState } from "react";
import { obtenerConfiguracion, actualizarConfiguracion } from "../api/configuracion";
import { listarCajas } from "../api/cajas";

const CAMPOS_VACIOS = {
  consorcio_nombre: "",
  consorcio_domicilio: "",
  consorcio_cuit: "",
  consorcio_convenio_suterh: "",
  admin_nombre: "",
  admin_domicilio: "",
  admin_email: "",
  admin_telefono: "",
  admin_cuit: "",
  admin_rpa: "",
  admin_situacion_fiscal: "",
  banco_titular: "",
  banco_nombre: "",
  banco_sucursal: "",
  banco_numero_cuenta: "",
  banco_cbu: "",
  banco_alias: "",
  dia_primer_vencimiento: 10,
  dias_entre_vencimientos: 10,
  recargo_segundo_vencimiento_pct: 7.0,
  tasa_interes_mensual_pct: 3.0,
  caja_default_pagos_id: null,
  reportes_visibles_a_depto: false,
  peticiones_visibles_a_depto: true,
};

export default function Configuracion() {
  const [form, setForm] = useState(CAMPOS_VACIOS);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [cajas, setCajas] = useState([]);

  useEffect(() => {
    let cancelado = false;
    async function cargar() {
      const [configRes, cajasRes] = await Promise.all([
        obtenerConfiguracion(),
        listarCajas(),
      ]);
      if (cancelado) return;
      if (configRes.status === 200) {
        const limpio = { ...CAMPOS_VACIOS };
        for (const k of Object.keys(CAMPOS_VACIOS)) {
          const def = CAMPOS_VACIOS[k];
          const val = configRes.data[k];
          // Mantener tipo del default: números se cargan como números, strings como strings
          limpio[k] = val !== undefined && val !== null ? val : def;
        }
        setForm(limpio);
      } else if (configRes.status !== 401) {
        setError(configRes.data?.detail || "No se pudo cargar la configuración.");
      }
      if (cajasRes.status === 200) {
        setCajas(cajasRes.data || []);
      }
      setCargando(false);
    }
    cargar();
    return () => {
      cancelado = true;
    };
  }, []);

  function cambiar(campo) {
    return (e) => {
      setForm({ ...form, [campo]: e.target.value });
      setMensaje(null);
    };
  }

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    setMensaje(null);
    const payload = { ...form };
    for (const k of ["consorcio_convenio_suterh", "banco_sucursal", "banco_alias"]) {
      if (payload[k] === "") payload[k] = null;
    }
    const r = await actualizarConfiguracion(payload);
    if (r.status === 200) {
      setMensaje("Configuración guardada.");
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudo guardar la configuración.");
    }
    setGuardando(false);
  }

  if (cargando) return <section><p>Cargando…</p></section>;

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Datos del consorcio</h2>
      </header>

      <form onSubmit={onSubmit} className="formulario-configuracion">
        <fieldset>
          <legend>Consorcio</legend>
          <label>Nombre <input value={form.consorcio_nombre} onChange={cambiar("consorcio_nombre")} required /></label>
          <label>Domicilio <input value={form.consorcio_domicilio} onChange={cambiar("consorcio_domicilio")} required /></label>
          <label>CUIT <input value={form.consorcio_cuit} onChange={cambiar("consorcio_cuit")} placeholder="30-12345678-9" required /></label>
          <label>Convenio SUTERH <input value={form.consorcio_convenio_suterh} onChange={cambiar("consorcio_convenio_suterh")} /></label>
        </fieldset>

        <fieldset>
          <legend>Administración</legend>
          <label>Nombre <input value={form.admin_nombre} onChange={cambiar("admin_nombre")} required /></label>
          <label>Domicilio <input value={form.admin_domicilio} onChange={cambiar("admin_domicilio")} required /></label>
          <label>Email <input type="email" value={form.admin_email} onChange={cambiar("admin_email")} required /></label>
          <label>Teléfono <input value={form.admin_telefono} onChange={cambiar("admin_telefono")} required /></label>
          <label>CUIT <input value={form.admin_cuit} onChange={cambiar("admin_cuit")} required /></label>
          <label>RPA/C <input value={form.admin_rpa} onChange={cambiar("admin_rpa")} required /></label>
          <label>Situación fiscal <input value={form.admin_situacion_fiscal} onChange={cambiar("admin_situacion_fiscal")} required /></label>
        </fieldset>

        <fieldset>
          <legend>Datos bancarios</legend>
          <label>Titular <input value={form.banco_titular} onChange={cambiar("banco_titular")} required /></label>
          <label>Banco <input value={form.banco_nombre} onChange={cambiar("banco_nombre")} required /></label>
          <label>Sucursal <input value={form.banco_sucursal} onChange={cambiar("banco_sucursal")} /></label>
          <label>N° cuenta <input value={form.banco_numero_cuenta} onChange={cambiar("banco_numero_cuenta")} required /></label>
          <label>CBU <input value={form.banco_cbu} onChange={cambiar("banco_cbu")} minLength={22} maxLength={22} required /></label>
          <label>Alias <input value={form.banco_alias} onChange={cambiar("banco_alias")} /></label>
        </fieldset>

        <fieldset>
          <legend>Vencimientos e intereses</legend>
          <label>Día del 1° vencimiento <input type="number" min="1" max="28" value={form.dia_primer_vencimiento} onChange={(e) => setForm({ ...form, dia_primer_vencimiento: Number(e.target.value) })} required /></label>
          <label>Días entre 1° y 2° vencimiento <input type="number" min="1" value={form.dias_entre_vencimientos} onChange={(e) => setForm({ ...form, dias_entre_vencimientos: Number(e.target.value) })} required /></label>
          <label>% recargo del 2° vencimiento <input type="number" step="0.5" min="0" value={form.recargo_segundo_vencimiento_pct} onChange={(e) => setForm({ ...form, recargo_segundo_vencimiento_pct: Number(e.target.value) })} required /></label>
          <label>% interés mensual punitorio <input type="number" step="0.5" min="0" value={form.tasa_interes_mensual_pct} onChange={(e) => setForm({ ...form, tasa_interes_mensual_pct: Number(e.target.value) })} required /></label>
        </fieldset>

        <fieldset>
          <legend>Tesorería</legend>
          <label>Caja default para pagos recibidos
            <select
              value={form.caja_default_pagos_id || ""}
              onChange={(e) => setForm({ ...form, caja_default_pagos_id: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">— Ninguna —</option>
              {cajas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
          </label>
        </fieldset>

        <fieldset>
          <legend>Visibilidad de reportes para departamentos</legend>
          <label>
            <input
              type="checkbox"
              checked={!!form.reportes_visibles_a_depto}
              onChange={(e) => setForm({ ...form, reportes_visibles_a_depto: e.target.checked })}
            />
            {" "}Permitir que los departamentos vean los reportes (morosos, estado financiero, gastos, proveedores)
          </label>
          <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted, #666)", marginTop: "0.5rem" }}>
            Por default los reportes son solo para administración. Activá esta opción para transparencia total con los copropietarios.
          </p>
        </fieldset>

        <fieldset>
          <legend>Visibilidad de peticiones entre departamentos</legend>
          <label>
            <input
              type="checkbox"
              checked={!!form.peticiones_visibles_a_depto}
              onChange={(e) => setForm({ ...form, peticiones_visibles_a_depto: e.target.checked })}
            />
            {" "}Permitir que cada departamento vea también las peticiones de los demás
          </label>
          <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted, #666)", marginTop: "0.5rem" }}>
            Activada, cada vecino ve qué reclamos hay abiertos en el edificio y
            evita duplicarlos. Desactivada, cada departamento ve únicamente sus
            propias peticiones. Administración y representantes las ven todas en
            los dos casos.
          </p>
        </fieldset>

        {error && <p className="error">{error}</p>}
        {mensaje && <p className="exito">{mensaje}</p>}

        <button type="submit" disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar"}
        </button>
      </form>
    </section>
  );
}

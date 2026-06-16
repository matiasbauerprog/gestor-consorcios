import { useEffect, useState } from "react";
import { obtenerConfiguracion, actualizarConfiguracion } from "../api/configuracion";

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
};

export default function Configuracion() {
  const [form, setForm] = useState(CAMPOS_VACIOS);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);

  useEffect(() => {
    let cancelado = false;
    async function cargar() {
      const r = await obtenerConfiguracion();
      if (cancelado) return;
      if (r.status === 200) {
        const limpio = { ...CAMPOS_VACIOS };
        for (const k of Object.keys(CAMPOS_VACIOS)) {
          limpio[k] = r.data[k] ?? "";
        }
        setForm(limpio);
      } else if (r.status !== 401) {
        setError(r.data?.detail || "No se pudo cargar la configuración.");
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

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
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

        {error && <p className="error">{error}</p>}
        {mensaje && <p className="exito">{mensaje}</p>}

        <button type="submit" disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar"}
        </button>
      </form>
    </main>
  );
}

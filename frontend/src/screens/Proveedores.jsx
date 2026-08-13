import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import TablaResponsive from "../components/TablaResponsive";
import {
  listarProveedores,
  crearProveedor,
  actualizarProveedor,
  eliminarProveedor,
} from "../api/proveedores";
import { ANCHO_CUIT } from "../utils/anchosColumnas";

// "Inactivo" (8 caracteres) es el string más largo de esta columna. Mismo
// cálculo que el ANCHO_ESTADO local de GastosHabituales.jsx y
// ClasesProrrateo.jsx — no se centraliza en anchosColumnas.js porque el
// texto exacto ("Activo/Inactivo" acá vs. "Activa/Inactiva" en
// ClasesProrrateo.jsx) cambia de pantalla a pantalla, a diferencia de una
// fecha, un monto o un CUIT que sí tienen un formato fijo único:
// (8×8.2×1.2 + 24) / 7.15 ≈ 14.4 → 15ch.
const ANCHO_ESTADO = "15ch";

// Dos botones sueltos en la celda, NO MenuAcciones: esta fila solo tiene
// dos acciones (Editar / Activar-Desactivar, sin Eliminar — Proveedores no
// tiene esa acción), y el menú "⋯" se reserva para filas con tres o más
// (ver Cajas.jsx / Amenities.jsx / GastosHabituales.jsx). "Desactivar" (10
// caracteres) es la etiqueta más larga de las dos; 11rem reusa el ancho ya
// probado en Periodos.jsx para una celda con dos controles ("Ver expensas"
// + "✉ Enviar PDFs", más texto combinado que "Editar" + "Desactivar" acá),
// así que entra sin necesidad de envolver en el caso común. Si algún día
// hiciera falta más precisión, `.tabla-datos tbody td:has(button)` ya tiene
// `white-space: normal` (index.css) — un ajuste corto solo agrega una
// segunda línea, nunca corta ni fuerza scroll horizontal.
const ANCHO_ACCIONES_PROVEEDOR = "11rem";

export default function Proveedores() {
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [modal, setModal] = useState(null);

  async function recargar() {
    setCargando(true);
    const filtro = mostrarInactivos ? { activo: false } : { activo: true };
    const r = await listarProveedores(filtro);
    if (r.status === 200) {
      setProveedores(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los proveedores.");
    }
    setCargando(false);
  }

  useEffect(() => {
    recargar();
  }, [mostrarInactivos]);

  async function toggleActivo(p) {
    const r = p.activo
      ? await eliminarProveedor(p.id)
      : await actualizarProveedor(p.id, { activo: true });
    if (r.status === 200) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al actualizar.");
  }

  if (cargando) return <section><p>Cargando…</p></section>;

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Proveedores</h2>
        <div className="cabecera-acciones">
          <label className="filtro-checkbox">
            <input
              type="checkbox"
              checked={mostrarInactivos}
              onChange={(e) => setMostrarInactivos(e.target.checked)}
            />
            Mostrar inactivos
          </label>
          <button type="button" onClick={() => setModal({ tipo: "crear" })}>
            Nuevo proveedor
          </button>
        </div>
      </header>

      {error && <p role="alert" className="error-banner">{error}</p>}

      <TablaResponsive
        columnas={[
          { clave: "razon", titulo: "Razón social", prioridad: 1, ancho: "auto",
            celda: (p) => p.razon_social },
          { clave: "fantasia", titulo: "Nombre fantasía", prioridad: 3, ancho: "auto",
            celda: (p) => p.nombre_fantasia || "—" },
          { clave: "cuit", titulo: "CUIT", prioridad: 1, ancho: ANCHO_CUIT,
            celda: (p) => p.cuit },
          { clave: "direccion", titulo: "Dirección", prioridad: 3, ancho: "auto",
            celda: (p) => p.direccion || "—" },
          { clave: "estado", titulo: "Estado", prioridad: 2, ancho: ANCHO_ESTADO,
            celda: (p) => (p.activo ? "Activo" : "Inactivo") },
          {
            clave: "acciones", titulo: "", className: "col-acciones", prioridad: 1,
            ancho: ANCHO_ACCIONES_PROVEEDOR,
            celda: (p) => (
              <>
                <button type="button" onClick={() => setModal({ tipo: "editar", proveedor: p })}>
                  Editar
                </button>{" "}
                <button type="button" onClick={() => toggleActivo(p)}>
                  {p.activo ? "Desactivar" : "Activar"}
                </button>
              </>
            ),
          },
        ]}
        filas={proveedores}
        claveFila={(p) => p.id}
        vacio="No hay proveedores con esos filtros."
        renderTarjeta={(p) => (
          <Tarjeta>
            <h3>{p.razon_social}</h3>
            {p.nombre_fantasia && <p className="meta">Nombre fantasía: {p.nombre_fantasia}</p>}
            <p className="meta">CUIT: {p.cuit}</p>
            {p.direccion && <p className="meta">Dirección: {p.direccion}</p>}
            <p className="meta">Estado: {p.activo ? "Activo" : "Inactivo"}</p>
            <div className="tarjeta-acciones">
              <button type="button" onClick={() => setModal({ tipo: "editar", proveedor: p })}>
                Editar
              </button>
              <button type="button" onClick={() => toggleActivo(p)}>
                {p.activo ? "Desactivar" : "Activar"}
              </button>
            </div>
          </Tarjeta>
        )}
      />

      {modal?.tipo === "crear" && (
        <ModalProveedor
          titulo="Nuevo proveedor"
          inicial={{ razon_social: "", nombre_fantasia: "", cuit: "", direccion: "" }}
          permiteEditarCuit
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const payload = {
              ...datos,
              nombre_fantasia: datos.nombre_fantasia || null,
              direccion: datos.direccion || null,
            };
            const r = await crearProveedor(payload);
            if (r.status === 201) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al crear.";
          }}
        />
      )}

      {modal?.tipo === "editar" && (
        <ModalProveedor
          titulo={`Editar ${modal.proveedor.razon_social}`}
          inicial={{
            razon_social: modal.proveedor.razon_social,
            nombre_fantasia: modal.proveedor.nombre_fantasia || "",
            cuit: modal.proveedor.cuit,
            direccion: modal.proveedor.direccion || "",
          }}
          permiteEditarCuit={false}
          onCerrar={() => setModal(null)}
          onGuardar={async ({ razon_social, nombre_fantasia, direccion }) => {
            const r = await actualizarProveedor(modal.proveedor.id, {
              razon_social,
              nombre_fantasia: nombre_fantasia || null,
              direccion: direccion || null,
            });
            if (r.status === 200) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al editar.";
          }}
        />
      )}
    </section>
  );
}

function ModalProveedor({ titulo, inicial, permiteEditarCuit, onCerrar, onGuardar }) {
  const [form, setForm] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const err = await onGuardar(form);
    if (err) {
      setError(err);
      setGuardando(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{titulo}</h3>
        <form onSubmit={onSubmit}>
          <label>Razón social
            <input
              value={form.razon_social}
              onChange={(e) => setForm({ ...form, razon_social: e.target.value })}
              maxLength={255}
              required
            />
          </label>
          <label>Nombre fantasía
            <input
              value={form.nombre_fantasia}
              onChange={(e) => setForm({ ...form, nombre_fantasia: e.target.value })}
              maxLength={255}
            />
          </label>
          <label>CUIT
            <input
              value={form.cuit}
              onChange={(e) => setForm({ ...form, cuit: e.target.value })}
              disabled={!permiteEditarCuit}
              placeholder="30-12345678-9"
              pattern="\d{2}-\d{8}-\d{1}"
              required
            />
          </label>
          <label>Dirección
            <input
              value={form.direccion}
              onChange={(e) => setForm({ ...form, direccion: e.target.value })}
              maxLength={500}
            />
          </label>
          {error && <p className="error">{error}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

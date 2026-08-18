import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { crearConsorcio, listarConsorcios } from "../api/consorcios";

const DEFAULTS = {
  nombre: "",
  consorcio_domicilio: "",
  consorcio_cuit: "",
  consorcio_convenio_suterh: "",
  usa_personal_propio: true,
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
  reportes_visibles_a_depto: false,
  peticiones_visibles_a_depto: true,
};

const CAMPOS_ADMIN = [
  "admin_nombre",
  "admin_domicilio",
  "admin_email",
  "admin_telefono",
  "admin_cuit",
  "admin_rpa",
  "admin_situacion_fiscal",
];
const CAMPOS_BANCO = [
  "banco_titular",
  "banco_nombre",
  "banco_sucursal",
  "banco_numero_cuenta",
  "banco_cbu",
  "banco_alias",
];

function ProgressBar({ paso, total }) {
  return (
    <div
      role="progressbar"
      aria-valuemin={1}
      aria-valuemax={total}
      aria-valuenow={paso}
      style={{
        display: "flex",
        gap: "0.5rem",
        margin: "0 0 1.5rem",
      }}
    >
      {Array.from({ length: total }, (_, i) => i + 1).map((n) => (
        <div
          key={n}
          style={{
            flex: 1,
            height: 6,
            borderRadius: 3,
            background:
              n <= paso
                ? "var(--color-primary)"
                : "var(--color-border, #ddd)",
          }}
        />
      ))}
    </div>
  );
}

function Campo({ label, required, children }) {
  return (
    <label style={{ display: "block", marginBottom: "0.75rem" }}>
      <span style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.25rem" }}>
        {label} {required && <span style={{ color: "var(--color-danger)" }}>*</span>}
      </span>
      {children}
    </label>
  );
}

export default function WizardNuevoConsorcio() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [paso, setPaso] = useState(1);
  const [f, setF] = useState(DEFAULTS);
  const [otros, setOtros] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await listarConsorcios();
      if (r.status === 200) setOtros(r.data);
    })();
  }, []);

  if (!user) return null;
  if (user.rol !== "administracion") return <Navigate to="/" replace />;

  function set(k, v) {
    setF((prev) => ({ ...prev, [k]: v }));
  }

  function copiarDelUltimo(campos) {
    if (otros.length === 0) return;
    const ultimo = otros[otros.length - 1];
    setF((prev) => {
      const nuevo = { ...prev };
      for (const c of campos) {
        if (ultimo[c] !== undefined && ultimo[c] !== null) nuevo[c] = ultimo[c];
      }
      return nuevo;
    });
  }

  function validarPaso() {
    setError(null);
    if (paso === 1) {
      if (!f.nombre || !f.consorcio_domicilio || !f.consorcio_cuit) {
        setError("Completá nombre, domicilio y CUIT del consorcio.");
        return false;
      }
    } else if (paso === 2) {
      for (const c of CAMPOS_ADMIN) {
        if (!f[c]) {
          setError("Completá todos los datos de la administración.");
          return false;
        }
      }
    } else if (paso === 3) {
      const requeridos = ["banco_titular", "banco_nombre", "banco_numero_cuenta", "banco_cbu"];
      for (const c of requeridos) {
        if (!f[c]) {
          setError("Completá titular, banco, número de cuenta y CBU.");
          return false;
        }
      }
    }
    return true;
  }

  function avanzar(e) {
    e.preventDefault();
    if (!validarPaso()) return;
    setPaso((p) => Math.min(4, p + 1));
  }

  function volver() {
    setError(null);
    setPaso((p) => Math.max(1, p - 1));
  }

  async function crear(e) {
    e.preventDefault();
    if (!validarPaso()) return;
    setLoading(true);
    setError(null);
    // Sanear campos opcionales vacíos → null.
    const body = { ...f };
    for (const k of [
      "consorcio_convenio_suterh",
      "banco_sucursal",
      "banco_alias",
    ]) {
      if (body[k] === "") body[k] = null;
    }
    const r = await crearConsorcio(body);
    setLoading(false);
    if (r.status === 201) {
      navigate("/administracion/consorcios", { replace: true });
      return;
    }
    setError(r.data?.detail || "No se pudo crear el consorcio.");
  }

  const puedePrefill = otros.length > 0;

  return (
    <section style={{ maxWidth: 720, margin: "0 auto" }}>
      <h2>Nuevo consorcio</h2>
      <ProgressBar paso={paso} total={4} />

      <form onSubmit={paso === 4 ? crear : avanzar}>
        {paso === 1 && (
          <>
            <h3>1. Datos del consorcio</h3>
            <Campo label="Nombre" required>
              <input
                value={f.nombre}
                onChange={(e) => set("nombre", e.target.value)}
                required
                maxLength={255}
              />
            </Campo>
            <Campo label="Domicilio" required>
              <input
                value={f.consorcio_domicilio}
                onChange={(e) => set("consorcio_domicilio", e.target.value)}
                required
                maxLength={500}
              />
            </Campo>
            <Campo label="CUIT" required>
              <input
                value={f.consorcio_cuit}
                onChange={(e) => set("consorcio_cuit", e.target.value)}
                required
                maxLength={13}
                placeholder="30-XXXXXXXX-X"
              />
            </Campo>
            <Campo label="Convenio SUTERH (opcional)">
              <input
                value={f.consorcio_convenio_suterh}
                onChange={(e) => set("consorcio_convenio_suterh", e.target.value)}
                maxLength={50}
              />
            </Campo>
            <Campo label="">
              <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={f.usa_personal_propio}
                  onChange={(e) => set("usa_personal_propio", e.target.checked)}
                />
                El consorcio administra personal propio (encargados, ayudantes).
              </label>
            </Campo>
          </>
        )}

        {paso === 2 && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3>2. Datos de la administración</h3>
              {puedePrefill && (
                <button
                  type="button"
                  onClick={() => copiarDelUltimo(CAMPOS_ADMIN)}
                  style={{ fontSize: "0.85rem" }}
                >
                  Usar los datos del último consorcio
                </button>
              )}
            </div>
            {[
              ["admin_nombre", "Razón social / nombre", 255],
              ["admin_domicilio", "Domicilio", 500],
              ["admin_email", "Email", 255, "email"],
              ["admin_telefono", "Teléfono", 50],
              ["admin_cuit", "CUIT", 13],
              ["admin_rpa", "RPA (Registro Público de Administradores)", 50],
              ["admin_situacion_fiscal", "Situación fiscal", 100],
            ].map(([k, label, max, type]) => (
              <Campo key={k} label={label} required>
                <input
                  type={type || "text"}
                  value={f[k]}
                  onChange={(e) => set(k, e.target.value)}
                  required
                  maxLength={max}
                />
              </Campo>
            ))}
          </>
        )}

        {paso === 3 && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3>3. Datos bancarios</h3>
              {puedePrefill && (
                <button
                  type="button"
                  onClick={() => copiarDelUltimo(CAMPOS_BANCO)}
                  style={{ fontSize: "0.85rem" }}
                >
                  Usar los datos del último consorcio
                </button>
              )}
            </div>
            <Campo label="Titular" required>
              <input
                value={f.banco_titular}
                onChange={(e) => set("banco_titular", e.target.value)}
                required
                maxLength={255}
              />
            </Campo>
            <Campo label="Banco" required>
              <input
                value={f.banco_nombre}
                onChange={(e) => set("banco_nombre", e.target.value)}
                required
                maxLength={100}
              />
            </Campo>
            <Campo label="Sucursal">
              <input
                value={f.banco_sucursal}
                onChange={(e) => set("banco_sucursal", e.target.value)}
                maxLength={50}
              />
            </Campo>
            <Campo label="Número de cuenta" required>
              <input
                value={f.banco_numero_cuenta}
                onChange={(e) => set("banco_numero_cuenta", e.target.value)}
                required
                maxLength={50}
              />
            </Campo>
            <Campo label="CBU (22 dígitos)" required>
              <input
                value={f.banco_cbu}
                onChange={(e) => set("banco_cbu", e.target.value)}
                required
                maxLength={22}
                minLength={22}
              />
            </Campo>
            <Campo label="Alias">
              <input
                value={f.banco_alias}
                onChange={(e) => set("banco_alias", e.target.value)}
                maxLength={50}
              />
            </Campo>
          </>
        )}

        {paso === 4 && (
          <>
            <h3>4. Vencimientos e intereses</h3>
            <Campo label="Día del primer vencimiento (1-28)">
              <input
                type="number"
                min={1}
                max={28}
                value={f.dia_primer_vencimiento}
                onChange={(e) => set("dia_primer_vencimiento", Number(e.target.value))}
                required
              />
            </Campo>
            <Campo label="Días entre vencimientos (1-30)">
              <input
                type="number"
                min={1}
                max={30}
                value={f.dias_entre_vencimientos}
                onChange={(e) => set("dias_entre_vencimientos", Number(e.target.value))}
                required
              />
            </Campo>
            <Campo label="Recargo 2º vencimiento (%)">
              <input
                type="number"
                min={0}
                max={100}
                step="0.1"
                value={f.recargo_segundo_vencimiento_pct}
                onChange={(e) => set("recargo_segundo_vencimiento_pct", Number(e.target.value))}
                required
              />
            </Campo>
            <Campo label="Tasa interés mensual (%)">
              <input
                type="number"
                min={0}
                max={100}
                step="0.1"
                value={f.tasa_interes_mensual_pct}
                onChange={(e) => set("tasa_interes_mensual_pct", Number(e.target.value))}
                required
              />
            </Campo>
            <Campo label="">
              <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={f.reportes_visibles_a_depto}
                  onChange={(e) => set("reportes_visibles_a_depto", e.target.checked)}
                />
                Los departamentos pueden ver los reportes del consorcio.
              </label>
            </Campo>
            <Campo label="">
              <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={f.peticiones_visibles_a_depto}
                  onChange={(e) => set("peticiones_visibles_a_depto", e.target.checked)}
                />
                Cada departamento ve también las peticiones de los demás.
              </label>
            </Campo>
          </>
        )}

        {error && (
          <p role="alert" className="login-error" style={{ marginTop: "0.5rem" }}>
            {error}
          </p>
        )}

        <div style={{ display: "flex", justifyContent: "space-between", marginTop: "1.5rem" }}>
          <button
            type="button"
            onClick={paso === 1 ? () => navigate("/administracion/consorcios") : volver}
          >
            {paso === 1 ? "Cancelar" : "← Volver"}
          </button>
          <button type="submit" disabled={loading}>
            {paso === 4 ? (loading ? "Creando…" : "Crear consorcio") : "Siguiente →"}
          </button>
        </div>
      </form>
    </section>
  );
}

# Hubs financieros — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidar el flujo financiero del depto en un hub `/mi-cuenta` con 4 tabs y flujo de pago único; consolidar Expensas y Comprobantes del admin en un hub `/cobranzas` con 2 tabs. Los links viejos redirigen al hub según el rol.

**Architecture:** Cambio 100% frontend. Se introduce un componente `Tabs` liviano compartido y un `TarjetaExpensa` extraído. `MiCuenta.jsx` pasa a ser el hub del depto; `Cobranzas.jsx` es una pantalla nueva que embebe `Expensas.jsx` y `Comprobantes.jsx` como secciones. `App.jsx` centraliza los redirects por rol de `/expensas` y `/comprobantes`. Sin backend, sin cambios en `openapi.yaml`, sin tests de pytest afectados.

**Tech Stack:** React 18 + Vite, react-router-dom v6 (`useSearchParams`, `<Navigate>`), CSS con variables ya definidas en `frontend/src/index.css`. Sin librerías nuevas.

**Verificación:** el proyecto no tiene tests de frontend; cada task cierra con `npm run build` para catch de errores + verificación manual en browser. Roles a testear: `administracion`, `representante`, `departamento`.

**Referencia:** `docs/superpowers/specs/2026-07-04-hub-mi-cuenta-design.md`.

---

## File Structure

**Crear:**
- `frontend/src/components/Tabs.jsx` — componente compartido de tabs (botones + `aria-selected`).
- `frontend/src/components/TarjetaExpensa.jsx` — extracción de la función local de `Expensas.jsx`.
- `frontend/src/screens/Cobranzas.jsx` — hub admin con tabs Expensas | Comprobantes.

**Modificar:**
- `frontend/src/screens/MiCuenta.jsx` — reorganizar en 4 tabs, pago único, borrar helpers duplicados.
- `frontend/src/screens/Expensas.jsx` — raíz `<main>`→`<section>`; sacar la definición local de `TarjetaExpensa`; sacar el aviso a depto (ahora inalcanzable).
- `frontend/src/screens/Comprobantes.jsx` — sacar el aviso a depto (ahora inalcanzable). Root ya es `<section>`.
- `frontend/src/components/Sidebar.jsx` — quitar `/expensas` y `/comprobantes` del menú; agregar `/cobranzas` (admin-only).
- `frontend/src/App.jsx` — nueva ruta `/cobranzas`; wrappers `ExpensasRoute` y `ComprobantesRoute` que redirigen por rol.
- `frontend/src/index.css` — estilos del componente `Tabs` (tokens existentes, mobile-first).

**Eliminar:**
- `frontend/src/components/ModalPresentarPago.jsx` — modal de pago asociado a expensa (solo lo usa `MiCuenta.jsx`).

**No tocar:** backend completo, `openapi.yaml`, tests de pytest, `.claude/rules/*`.

---

## Task 1: Extraer `TarjetaExpensa` a su propio componente

Cero cambio de comportamiento. Solo movemos la función `TarjetaExpensa` (definida en `Expensas.jsx` líneas 23-88) a su propio archivo y actualizamos el import.

**Files:**
- Create: `frontend/src/components/TarjetaExpensa.jsx`
- Modify: `frontend/src/screens/Expensas.jsx`

- [ ] **Step 1: Crear `frontend/src/components/TarjetaExpensa.jsx`**

Contenido completo (copiar tal cual desde `Expensas.jsx` + arreglar imports):

```jsx
import { abrirPdfExpensa } from "../api/pdf";
import BadgeEstado from "./BadgeEstado";
import Tarjeta from "./Tarjeta";

function formatearMonto(v) {
  return Number(v).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  });
}

export default function TarjetaExpensa({
  expensa,
  esAdmin,
  depto,
  token,
  onEliminar,
  onVerComprobantes,
}) {
  async function handleAbrirPdf() {
    try {
      await abrirPdfExpensa(expensa.id, token);
    } catch (e) {
      alert(`No se pudo abrir el PDF: ${e.message}`);
    }
  }

  return (
    <Tarjeta>
      <h3>
        {expensa.periodo} — {formatearMonto(expensa.monto_primer_vencimiento)}
      </h3>
      {esAdmin && (
        <p className="meta">
          {depto ? `${depto.codigo} — ${depto.descripcion}` : `Depto #${expensa.departamento_id}`}
        </p>
      )}
      <p className="meta">
        1° venc {expensa.fecha_primer_vencimiento}: {formatearMonto(expensa.monto_primer_vencimiento)}
      </p>
      <p className="meta">
        2° venc {expensa.fecha_segundo_vencimiento}: {formatearMonto(expensa.monto_segundo_vencimiento)} (+recargo)
      </p>
      {expensa.saldo_anterior > 0 && (
        <p className="meta">Saldo anterior: {formatearMonto(expensa.saldo_anterior)}</p>
      )}
      <p>
        <BadgeEstado estado={expensa.estado_calculado} />
        {expensa.monto_pendiente > 0 && (
          <span className="meta" style={{ marginLeft: "0.5rem" }}>
            Pendiente {formatearMonto(expensa.monto_pendiente)}
          </span>
        )}
      </p>
      {(expensa.detalle?.length > 0 || esAdmin) && (
        <div className="tarjeta-acciones">
          <button
            type="button"
            className="boton-secundario"
            onClick={() => onVerComprobantes(expensa)}
          >
            Ver comprobantes
          </button>
          <button
            type="button"
            className="boton-secundario"
            onClick={handleAbrirPdf}
          >
            📄 Ver PDF
          </button>
          {esAdmin && (
            <button
              type="button"
              className="boton-peligro"
              onClick={() => onEliminar(expensa)}
            >
              Eliminar
            </button>
          )}
        </div>
      )}
    </Tarjeta>
  );
}
```

- [ ] **Step 2: Sacar la definición local de `TarjetaExpensa` de `Expensas.jsx`**

En `frontend/src/screens/Expensas.jsx`:
- Borrar la función `formatearMonto` local (líneas 15-21) y la función `TarjetaExpensa` (líneas 23-88).
- Actualizar el import block añadiendo:
```jsx
import TarjetaExpensa from "../components/TarjetaExpensa";
```
- Eliminar imports que ya no se usan en Expensas.jsx después del recorte: `abrirPdfExpensa` NO se elimina — lo mantiene en el módulo por si algún otro handler lo usa. Confirmar con grep si sigue apareciendo; si no aparece más, quitarlo también. Igual con `BadgeEstado` y `Tarjeta`: verificar y quitar solo si dejan de usarse.

Después del recorte, verificar con Grep en `Expensas.jsx`:
- Si `formatearMonto` no aparece más, ya está borrada.
- Si `abrirPdfExpensa`, `BadgeEstado`, `Tarjeta` no aparecen más, quitar sus imports.

- [ ] **Step 3: Verificar el build**

```bash
cd frontend && npm run build
```
Esperado: pasa sin errores.

- [ ] **Step 4: Verificar en browser**

Vite hot-reloads. Como admin, entrar a `/expensas` y comprobar que las tarjetas se ven idénticas a antes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TarjetaExpensa.jsx frontend/src/screens/Expensas.jsx
git commit -m "refactor(frontend): extraer TarjetaExpensa a su propio componente"
```

---

## Task 2: Componente `Tabs` compartido + estilos

Componente liviano reutilizable: renderiza los botones de tabs con `aria-selected`. El parent maneja qué panel mostrar. Sin dependencia de router.

**Files:**
- Create: `frontend/src/components/Tabs.jsx`
- Modify: `frontend/src/index.css` (agregar bloque de estilos al final del archivo)

- [ ] **Step 1: Crear `frontend/src/components/Tabs.jsx`**

```jsx
export default function Tabs({ items, activo, onCambio, ariaLabel }) {
  return (
    <div className="tabs" role="tablist" aria-label={ariaLabel}>
      {items.map((item) => {
        const seleccionado = item.valor === activo;
        return (
          <button
            key={item.valor}
            type="button"
            role="tab"
            aria-selected={seleccionado}
            className={seleccionado ? "tab activo" : "tab"}
            onClick={() => onCambio(item.valor)}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
```

Contrato:
- `items`: array de `{ valor: string, label: string }`.
- `activo`: string, valor del tab activo.
- `onCambio(valor)`: callback al click de un tab.
- `ariaLabel`: string, descripción del grupo (accesibilidad).

- [ ] **Step 2: Agregar estilos en `frontend/src/index.css`**

Agregar al final del archivo (después del último bloque):

```css
/* ---------- Tabs ---------- */

.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin: 0 0 1.25rem;
  padding: 0.25rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  width: fit-content;
  max-width: 100%;
}

.tab {
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  padding: 0.5em 1em;
  min-height: 44px;
  font-family: inherit;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--color-text-muted);
  cursor: pointer;
}

.tab:hover:not(:disabled) {
  background: color-mix(in srgb, var(--color-primary-soft) 55%, transparent);
  color: var(--color-text);
}

.tab:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.tab.activo {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 600;
}
```

- [ ] **Step 3: Verificar el build**

```bash
cd frontend && npm run build
```
Esperado: pasa. (El componente no se usa aún; solo verifico que compile.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Tabs.jsx frontend/src/index.css
git commit -m "feat(frontend): componente Tabs compartido con estilos"
```

---

## Task 3: `MiCuenta.jsx` como hub del depto (4 tabs + pago único)

Reorganiza la pantalla en 4 tabs, un solo botón "Presentar pago" en el header, monto pre-cargado con el saldo pendiente. Se borra `components/ModalPresentarPago.jsx` y su import. Se agrega la carga de comprobantes.

**Files:**
- Modify: `frontend/src/screens/MiCuenta.jsx`
- Delete: `frontend/src/components/ModalPresentarPago.jsx`

- [ ] **Step 1: Verificar que `ModalPresentarPago.jsx` no tiene otros consumidores**

```bash
grep -rn "ModalPresentarPago" frontend/src
```
Esperado: solo aparece en `MiCuenta.jsx` y en su propio archivo. Si aparece en algún otro consumidor, ABORTAR y pedir contexto.

- [ ] **Step 2: Reescribir `frontend/src/screens/MiCuenta.jsx` completo**

Reemplazar todo el archivo con:

```jsx
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { listarMisMovimientos } from "../api/movimientos";
import { listarExpensas } from "../api/expensas";
import { listarComprobantes, presentarComprobante } from "../api/comprobantes";
import { abrirPdfExpensa } from "../api/pdf";
import { API_BASE } from "../api/client";
import Modal from "../components/Modal";
import Tabs from "../components/Tabs";
import Tarjeta from "../components/Tarjeta";
import TarjetaExpensa from "../components/TarjetaExpensa";
import BadgeEstado from "../components/BadgeEstado";

const TIPO_LABEL = {
  expensa_emitida: "Expensa emitida",
  pago_recibido: "Pago",
  interes_punitorio: "Interés",
  nota_debito: "Nota de débito",
  nota_credito: "Nota de crédito",
};

const TIPO_SIGNO = {
  expensa_emitida: "+",
  pago_recibido: "-",
  interes_punitorio: "+",
  nota_debito: "+",
  nota_credito: "-",
};

const TABS = [
  { valor: "resumen", label: "Resumen" },
  { valor: "expensas", label: "Expensas" },
  { valor: "comprobantes", label: "Comprobantes" },
  { valor: "movimientos", label: "Movimientos" },
];

const TABS_VALIDOS = new Set(TABS.map((t) => t.valor));

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
  });
}

function sumarDias(yyyymmdd, n) {
  const d = new Date(yyyymmdd);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

export default function MiCuenta() {
  const { token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tabActivo = TABS_VALIDOS.has(tabParam) ? tabParam : "resumen";

  const [data, setData] = useState(null);
  const [expensas, setExpensas] = useState([]);
  const [comprobantes, setComprobantes] = useState([]);
  const [error, setError] = useState(null);
  const [modalPagoAbierto, setModalPagoAbierto] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);

  function cambiarTab(valor) {
    const params = new URLSearchParams(searchParams);
    if (valor === "resumen") params.delete("tab");
    else params.set("tab", valor);
    setSearchParams(params, { replace: true });
  }

  async function cargar() {
    setError(null);
    const res = await listarMisMovimientos();
    if (!res.ok) {
      setError(res.data?.detail || "Error cargando la cuenta corriente.");
      return;
    }
    setData(res.data);
  }

  async function cargarExpensas() {
    const res = await listarExpensas();
    if (res.status === 200) {
      setExpensas(res.data);
    }
  }

  async function cargarComprobantes() {
    const res = await listarComprobantes();
    if (res.status === 200) {
      setComprobantes(res.data);
    }
  }

  useEffect(() => {
    cargar();
    cargarExpensas();
    cargarComprobantes();
  }, []);

  if (error) {
    return (
      <main className="pantalla">
        <p role="alert">{error}</p>
      </main>
    );
  }
  if (!data) {
    return (
      <main className="pantalla">
        <p>Cargando cuenta corriente…</p>
      </main>
    );
  }

  const saldo = data.saldo_total;
  const saldoColor =
    saldo > 0
      ? "var(--color-danger)"
      : saldo < 0
        ? "var(--color-success)"
        : "var(--color-text)";
  const saldoTexto =
    saldo > 0
      ? "Saldo pendiente."
      : saldo < 0
        ? "Tenés saldo a favor."
        : "Estás al día.";

  const montoInicialPago = saldo > 0 ? saldo : "";

  return (
    <main className="pantalla">
      <header className="cabecera-pantalla">
        <h2>Mi cuenta</h2>
        <button type="button" onClick={() => setModalPagoAbierto(true)}>
          + Presentar pago
        </button>
      </header>

      {successMsg && (
        <p role="status" className="banner-exito">
          ✓ {successMsg}
        </p>
      )}

      <Tabs
        items={TABS}
        activo={tabActivo}
        onCambio={cambiarTab}
        ariaLabel="Secciones de mi cuenta"
      />

      {tabActivo === "resumen" && (
        <SeccionResumen
          saldo={saldo}
          saldoColor={saldoColor}
          saldoTexto={saldoTexto}
          expensas={expensas}
          token={token}
        />
      )}

      {tabActivo === "expensas" && (
        <SeccionExpensas expensas={expensas} token={token} />
      )}

      {tabActivo === "comprobantes" && (
        <SeccionComprobantes comprobantes={comprobantes} />
      )}

      {tabActivo === "movimientos" && (
        <SeccionMovimientos movimientos={data.movimientos} />
      )}

      {modalPagoAbierto && (
        <ModalPresentarPago
          montoInicial={montoInicialPago}
          onClose={() => setModalPagoAbierto(false)}
          onDone={() => {
            setModalPagoAbierto(false);
            setSuccessMsg(
              "Comprobante enviado. Va a quedar pendiente hasta que administración lo apruebe.",
            );
            cargar();
            cargarExpensas();
            cargarComprobantes();
          }}
        />
      )}
    </main>
  );
}

function SeccionResumen({ saldo, saldoColor, saldoTexto, expensas, token }) {
  const hoy = new Date().toISOString().slice(0, 10);
  const proximaExpensa = expensas
    .filter((e) => e.fecha_primer_vencimiento >= hoy)
    .sort((a, b) =>
      a.fecha_primer_vencimiento.localeCompare(b.fecha_primer_vencimiento),
    )[0];

  async function handleAbrirPdf() {
    if (!proximaExpensa) return;
    try {
      await abrirPdfExpensa(proximaExpensa.id, token);
    } catch (e) {
      alert(`No se pudo abrir el PDF: ${e.message}`);
    }
  }

  return (
    <>
      <Tarjeta>
        <p style={{ fontSize: "1.4rem", margin: 0, color: saldoColor }}>
          <strong>Saldo: {formatMoney(saldo)}</strong>
        </p>
        <p style={{ margin: "0.4rem 0 0", color: "var(--color-text-muted)" }}>
          {saldoTexto}
        </p>
      </Tarjeta>

      {proximaExpensa && (
        <Tarjeta>
          <h3>Próximo vencimiento</h3>
          <p>
            Si pagás hasta el {proximaExpensa.fecha_primer_vencimiento}:{" "}
            <strong>{formatMoney(proximaExpensa.monto_primer_vencimiento)}</strong>
          </p>
          <p>
            Del {sumarDias(proximaExpensa.fecha_primer_vencimiento, 1)} al{" "}
            {proximaExpensa.fecha_segundo_vencimiento}:{" "}
            <strong>{formatMoney(proximaExpensa.monto_segundo_vencimiento)}</strong>{" "}
            (+recargo)
          </p>
          <p className="meta">
            Después del {proximaExpensa.fecha_segundo_vencimiento}: se acumulan
            intereses mensuales.
          </p>
          <div className="tarjeta-acciones">
            <button
              type="button"
              className="boton-secundario"
              onClick={handleAbrirPdf}
            >
              📄 Ver PDF
            </button>
          </div>
        </Tarjeta>
      )}
    </>
  );
}

function SeccionExpensas({ expensas, token }) {
  if (expensas.length === 0) {
    return <p>No hay expensas.</p>;
  }
  return (
    <ul className="lista-expensas">
      {expensas.map((e) => (
        <li key={e.id}>
          <TarjetaExpensa
            expensa={e}
            esAdmin={false}
            depto={null}
            token={token}
            onEliminar={() => {}}
            onVerComprobantes={() => {}}
          />
        </li>
      ))}
    </ul>
  );
}

function SeccionComprobantes({ comprobantes }) {
  if (comprobantes.length === 0) {
    return <p>No hay comprobantes.</p>;
  }
  return (
    <ul className="lista-comprobantes">
      {comprobantes.map((c) => (
        <li key={c.id}>
          <Tarjeta>
            <h3>{formatMoney(c.monto)}</h3>
            <p className="meta">Pagado {c.fecha_pago}</p>
            <p><BadgeEstado estado={c.estado} /></p>
            {c.archivo_path && (
              <a
                href={`${API_BASE}${c.archivo_path}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <img
                  src={`${API_BASE}${c.archivo_path}`}
                  alt="Comprobante"
                  className="comprobante-img"
                />
              </a>
            )}
          </Tarjeta>
        </li>
      ))}
    </ul>
  );
}

function SeccionMovimientos({ movimientos }) {
  if (movimientos.length === 0) {
    return <p>No hay movimientos.</p>;
  }
  return (
    <table className="tabla-movimientos">
      <thead>
        <tr>
          <th>Fecha</th>
          <th>Tipo</th>
          <th>Descripción</th>
          <th>Monto</th>
        </tr>
      </thead>
      <tbody>
        {movimientos.map((m) => (
          <tr key={m.id}>
            <td>{m.fecha}</td>
            <td>{TIPO_LABEL[m.tipo] || m.tipo}</td>
            <td>{m.descripcion}</td>
            <td>
              {TIPO_SIGNO[m.tipo] || ""}
              {formatMoney(m.monto)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ModalPresentarPago({ montoInicial, onClose, onDone }) {
  const [fechaPago, setFechaPago] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [monto, setMonto] = useState(
    montoInicial ? String(montoInicial) : "",
  );
  const [archivo, setArchivo] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const res = await presentarComprobante({
      fecha_pago: fechaPago,
      monto: parseFloat(monto),
      archivo,
    });
    setSubmitting(false);
    if (!res.ok) {
      setError(res.data?.detail || "No se pudo registrar el comprobante.");
      return;
    }
    onDone();
  }

  return (
    <Modal titulo="Presentar pago" onClose={onClose}>
      <form onSubmit={submit} noValidate>
        <label>
          Fecha del pago
          <input
            type="date"
            value={fechaPago}
            onChange={(e) => setFechaPago(e.target.value)}
            required
          />
        </label>
        <label>
          Monto
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
            required
          />
        </label>
        <label>
          Comprobante (imagen JPG/PNG/WebP o PDF)
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
            required
          />
        </label>
        {error && <p role="alert">{error}</p>}
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.9rem" }}>
          Tu pago será visible cuando administración lo apruebe.
        </p>
        <div className="modal-acciones">
          <button type="button" onClick={onClose} disabled={submitting}>
            Cancelar
          </button>
          <button type="submit" disabled={submitting}>
            {submitting ? "Enviando…" : "Presentar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
```

Nota clave: `SeccionExpensas` pasa `onEliminar={() => {}}` y `onVerComprobantes={() => {}}` porque en la vista depto esos botones no se renderizan (`TarjetaExpensa` los condiciona a `esAdmin` o a `detalle?.length > 0`; si aparece "Ver comprobantes" para el depto, es no-op — aceptable como quick fix; si aparece por `detalle`, es del deep-link admin y tampoco es problema).

- [ ] **Step 3: Eliminar `frontend/src/components/ModalPresentarPago.jsx`**

```bash
git rm frontend/src/components/ModalPresentarPago.jsx
```

- [ ] **Step 4: Verificar el build**

```bash
cd frontend && npm run build
```
Esperado: pasa. Si falla por algún import no capturado, arreglarlo y reintentar.

- [ ] **Step 5: Verificar en browser (rol depto)**

Como depto:
- `/mi-cuenta` → tab Resumen con saldo y tarjeta "Próximo vencimiento" (sin botón de pago en la tarjeta).
- Header con un solo botón "+ Presentar pago" que abre el modal con monto pre-cargado si saldo > 0.
- Cambiar de tab a "Expensas" — la URL cambia a `?tab=expensas`.
- Tab "Comprobantes" — la URL cambia a `?tab=comprobantes` y aparecen los comprobantes con estado.
- Tab "Movimientos" — tabla de la cuenta corriente.
- Refresh en cualquier tab: mantiene el tab activo por el URL.
- Presentar un pago → aparece banner de éxito y el comprobante aparece en el tab Comprobantes.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/screens/MiCuenta.jsx
git commit -m "feat(frontend): Mi cuenta como hub con tabs y pago unificado"
```

(La eliminación de `ModalPresentarPago.jsx` ya está staged por el `git rm` del Step 3.)

---

## Task 4: Preparar `Expensas.jsx` para embed y crear `Cobranzas.jsx`

Se embeben `Expensas.jsx` y `Comprobantes.jsx` como secciones dentro de `Cobranzas.jsx`. Para eso, `Expensas.jsx` cambia su raíz de `<main className="pantalla">` a `<section className="pantalla">` (Comprobantes ya es `<section>`). Se quita el aviso a depto que dejó de aplicar (redirect llegará en Task 5). Se agrega la ruta `/cobranzas`.

**Files:**
- Modify: `frontend/src/screens/Expensas.jsx`
- Modify: `frontend/src/screens/Comprobantes.jsx`
- Create: `frontend/src/screens/Cobranzas.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Cambiar la raíz de `Expensas.jsx`**

Buscar en `frontend/src/screens/Expensas.jsx` la línea `<main className="pantalla">` (al inicio del JSX de `Expensas`) y su cierre `</main>` (al final). Reemplazar por `<section className="pantalla">` y `</section>` respectivamente.

También borrar el bloque de aviso al depto (ya no aplica porque el depto se redirige en Task 5):

```jsx
{esDepto && (
  <p className="meta">
    Para presentar un pago, andá a <Link to="/mi-cuenta">Mi cuenta</Link>.
  </p>
)}
```

Y la variable `esDepto = user.rol === "departamento";` si queda sin uso después de sacar el aviso.

Verificar con Grep si `Link` sigue usándose en el archivo; si no, quitar `Link` del import de `react-router-dom`.

- [ ] **Step 2: Sacar el aviso a depto de `Comprobantes.jsx`**

En `frontend/src/screens/Comprobantes.jsx`, encontrar el bloque:

```jsx
<p>
  No hay comprobantes con esos filtros.
  {!esAdmin && (
    <>{" "}Para presentar un pago, andá a <Link to="/mi-cuenta">Mi cuenta</Link>.</>
  )}
</p>
```

Reemplazar por:

```jsx
<p>No hay comprobantes con esos filtros.</p>
```

Verificar si `Link` sigue usándose; si no, quitarlo del import.

- [ ] **Step 3: Crear `frontend/src/screens/Cobranzas.jsx`**

```jsx
import { useSearchParams } from "react-router-dom";
import Tabs from "../components/Tabs";
import Expensas from "./Expensas";
import Comprobantes from "./Comprobantes";

const TABS = [
  { valor: "expensas", label: "Expensas" },
  { valor: "comprobantes", label: "Comprobantes" },
];

const TABS_VALIDOS = new Set(TABS.map((t) => t.valor));

export default function Cobranzas() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tabActivo = TABS_VALIDOS.has(tabParam) ? tabParam : "expensas";

  function cambiarTab(valor) {
    const params = new URLSearchParams(searchParams);
    params.set("tab", valor);
    setSearchParams(params, { replace: true });
  }

  return (
    <main className="pantalla">
      <header className="cabecera-pantalla">
        <h2>Cobranzas</h2>
      </header>

      <Tabs
        items={TABS}
        activo={tabActivo}
        onCambio={cambiarTab}
        ariaLabel="Secciones de cobranzas"
      />

      {tabActivo === "expensas" && <Expensas />}
      {tabActivo === "comprobantes" && <Comprobantes />}
    </main>
  );
}
```

- [ ] **Step 4: Agregar la ruta `/cobranzas` en `App.jsx`**

En `frontend/src/App.jsx`:

Agregar el import junto a los demás screens (después de la línea de `import Reglamento from "./screens/Reglamento";`):

```jsx
import Cobranzas from "./screens/Cobranzas";
```

Dentro del `<Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>`, agregar después de `<Route path="reglamento" element={<Reglamento />} />` y antes de `<Route path="*" element={<NotFound />} />`:

```jsx
<Route path="cobranzas" element={<Cobranzas />} />
```

- [ ] **Step 5: Verificar el build**

```bash
cd frontend && npm run build
```

- [ ] **Step 6: Verificar en browser (rol admin)**

Como admin:
- Navegar a `/cobranzas` → aparecen los tabs Expensas | Comprobantes y por defecto abre Expensas.
- El contenido embebido de Expensas funciona idéntico a `/expensas`: filtros, crear expensa, envío de PDFs.
- Cambiar al tab Comprobantes → aparece el listado con acciones admin (aprobar con caja, rechazar, eliminar).
- La URL sincroniza: `?tab=comprobantes`.
- `/expensas` y `/comprobantes` siguen accesibles (aún sin redirect).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/screens/Expensas.jsx frontend/src/screens/Comprobantes.jsx frontend/src/screens/Cobranzas.jsx frontend/src/App.jsx
git commit -m "feat(frontend): hub Cobranzas para admin con tabs Expensas/Comprobantes"
```

---

## Task 5: Redirects por rol en `App.jsx` + Sidebar

Cierra el loop: los links viejos redirigen al hub correcto según el rol; el aside deja de mostrar Expensas/Comprobantes como módulos separados y agrega Cobranzas para admin.

**Files:**
- Modify: `frontend/src/App.jsx` (wrappers de rutas viejas)
- Modify: `frontend/src/components/Sidebar.jsx` (constante SECCIONES, grupo Finanzas)

- [ ] **Step 1: Agregar wrappers `ExpensasRoute` y `ComprobantesRoute` en `App.jsx`**

En `frontend/src/App.jsx`, agregar los imports necesarios en el bloque de imports de react-router-dom:

```jsx
import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from "react-router-dom";
```

Agregar el import de `useAuth`:

```jsx
import { useAuth } from "./auth/AuthContext";
```

Justo antes de `export default function App()`, definir los wrappers:

```jsx
function ExpensasRoute() {
  const { user } = useAuth();
  if (user.rol === "departamento") {
    return <Navigate to="/mi-cuenta?tab=expensas" replace />;
  }
  if (user.rol === "administracion") {
    return <Navigate to="/cobranzas?tab=expensas" replace />;
  }
  return <Expensas />;
}

function ComprobantesRoute() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  if (user.rol === "departamento") {
    return <Navigate to="/mi-cuenta?tab=comprobantes" replace />;
  }
  if (user.rol === "administracion") {
    const params = new URLSearchParams(searchParams);
    params.set("tab", "comprobantes");
    return <Navigate to={`/cobranzas?${params.toString()}`} replace />;
  }
  return <Comprobantes />;
}
```

Cambiar las dos rutas existentes:

```jsx
<Route path="expensas" element={<Expensas />} />
```
a:
```jsx
<Route path="expensas" element={<ExpensasRoute />} />
```

Y:
```jsx
<Route path="comprobantes" element={<Comprobantes />} />
```
a:
```jsx
<Route path="comprobantes" element={<ComprobantesRoute />} />
```

- [ ] **Step 2: Actualizar `Sidebar.jsx` — quitar Expensas y Comprobantes, agregar Cobranzas**

En `frontend/src/components/Sidebar.jsx`, dentro del grupo `Finanzas` de `SECCIONES`:

Reemplazar los dos entries de expensas/comprobantes que están así:

```jsx
      {
        ruta: "/expensas",
        nombre: "Expensas",
        rolesPermitidos: ["administracion", "departamento"],
      },
      {
        ruta: "/comprobantes",
        nombre: "Comprobantes",
        rolesPermitidos: ["administracion", "departamento"],
      },
```

por un solo entry:

```jsx
      {
        ruta: "/cobranzas",
        nombre: "Cobranzas",
        rolesPermitidos: ["administracion"],
      },
```

El resto del grupo Finanzas queda intacto. `Mi cuenta` sigue existiendo con `rolesPermitidos: ["departamento"]`.

Grupo Finanzas resultante (orden final de módulos):
- Mi cuenta (depto)
- Cobranzas (admin)
- Historial de cierres (admin)
- Gastos (admin)
- Estado financiero (admin)
- Cajas (admin)
- Transferencias (admin)

- [ ] **Step 3: Verificar el build**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Verificar en browser — los 3 roles**

**Admin:**
- Aside → grupo Finanzas muestra: Cobranzas, Historial de cierres, Gastos, Estado financiero, Cajas, Transferencias. Sin "Expensas" ni "Comprobantes" sueltos.
- Ir a `/cobranzas` → hub con tabs, todo funciona.
- Escribir `/expensas` en la URL → redirige a `/cobranzas?tab=expensas`.
- Escribir `/comprobantes?departamento_id=3` → redirige a `/cobranzas?departamento_id=3&tab=comprobantes` (o `?tab=comprobantes&departamento_id=3`, el orden no importa; el hub y el tab Comprobantes leen el param).
- El link "Ver comprobantes" que hoy va de una expensa a `/comprobantes?departamento_id=X` sigue funcionando (llega a Cobranzas con el filtro puesto).

**Depto:**
- Aside → grupo Finanzas muestra solo: Mi cuenta.
- Ir a `/expensas` → redirige a `/mi-cuenta?tab=expensas` y abre el tab correcto.
- Ir a `/comprobantes` → redirige a `/mi-cuenta?tab=comprobantes`.

**Representante:**
- Aside → grupo Finanzas no aparece (no tiene módulos permitidos).
- Escribir `/expensas` en la URL → renderiza `<Expensas />` standalone (edge case aceptado; el backend le da 403 en las llamadas y el usuario ve la pantalla vacía).

**Mobile 375px:** tabs se ven bien en Mi cuenta y en Cobranzas, sin overflow horizontal.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/Sidebar.jsx
git commit -m "feat(frontend): redirects por rol de /expensas y /comprobantes + sidebar Cobranzas"
```

---

## Self-review checklist (para quien ejecute)

Cerrar cada task requiere verificar:

- [ ] Backend intocado — `git diff master..HEAD -- backend/ openapi.yaml tests/` muestra vacío.
- [ ] `pytest -q` (con el venv del proyecto: `.venv/Scripts/python.exe -m pytest -q`) → 632 passed.
- [ ] Depto: aside con solo "Mi cuenta" en Finanzas; hub con 4 tabs; un solo botón de pago; monto pre-cargado con saldo; `/expensas` y `/comprobantes` redirigen.
- [ ] Admin: aside con "Cobranzas"; hub con 2 tabs; contenido idéntico a las pantallas viejas; `/expensas` y `/comprobantes` redirigen (con `?departamento_id=` preservado en Comprobantes).
- [ ] Representante: cero cambios.
- [ ] Mobile 375px: los dos hubs son usables, sin overflow.
- [ ] Sin duplicación del botón "Presentar pago" en ninguna pantalla.
- [ ] `frontend/src/components/ModalPresentarPago.jsx` no existe más.
- [ ] `git log --oneline` muestra 5 commits (uno por Task).

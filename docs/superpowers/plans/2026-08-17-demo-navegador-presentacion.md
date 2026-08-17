# Demo en el navegador, parte 3: presentación y publicación — Plan B3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la demo se pueda mostrar y publicar: cambiar de rol sin perder lo hecho, entender qué es y qué no, y quedar servida en internet sin depender de ningún servidor.

**Architecture:** A diferencia de B1 y B2, este plan **sí toca pantallas**. Cada cambio va detrás de la bandera de demo salvo uno, que es una mejora del producto real y está marcado como tal.

**Tech Stack:** React 18 · Vite · vitest.

**Spec:** `docs/superpowers/specs/2026-08-16-demo-sin-backend-design.md` (§2.2, §2.4, §3.2.4, §7, §8)

**Depende de:** Planes B1 y B2, ya ejecutados.

## Global Constraints

- **Este plan sí modifica pantallas.** Todo cambio visible tiene que estar guardado tras `ES_DEMO` (`frontend/src/api/demo.js`), **salvo la Task 5**, que es una mejora del producto real y se aplica siempre.
- **En la aplicación de un cliente nada de esto puede aparecer:** el cambiador de rol sin credenciales sería un agujero de seguridad, no una comodidad.
- **No se toca el backend** ni el generador.
- **Sin dependencias nuevas.**
- Comando de tests: `npm test` desde `frontend/` (hoy 209 pasando).
- Para probar a mano: `cd frontend && VITE_DEMO_MODE=true npm run dev`, **con el backend apagado**.

## Por qué el cambiador de rol va primero

No es comodidad: hoy **el circuito de cobranza no se puede completar en la demo**. Verificado en el navegador — se presenta un pago como propietario, se va a cambiar a administración para aprobarlo, y como el cambio pasa por la pantalla de entrada la página se recarga, el estado en memoria se pierde y el comprobante desaparece.

El estado vive en memoria a propósito (§2.3: cada visita arranca limpia). Lo que hay que evitar no es eso, sino **la recarga al cambiar de perfil**.

---

### Task 1: Cambiar de perfil sin recargar

Un control siempre visible que cambia quién sos, sin pasar por la pantalla de entrada y sin perder lo que hiciste.

**Files:**
- Create: `frontend/src/components/CambiadorDeRol.jsx`
- Modify: `frontend/src/components/AppLayout.jsx`
- Modify: `frontend/src/auth/AuthContext.jsx`
- Test: `frontend/src/components/CambiadorDeRol.test.jsx`

**Interfaces:**
- Consumes: `login(token, user)` del contexto de autenticación, que ya existe y ya persiste el usuario.
- Consumes: `demoLogin(rol)` de `frontend/src/api/demo.js`.

- [ ] **Step 1: Write the failing test**

```jsx
// frontend/src/components/CambiadorDeRol.test.jsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CambiadorDeRol from "./CambiadorDeRol";

const login = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { rol: "departamento", departamento_id: 1 }, login }),
}));

const demoLogin = vi.fn(async (rol) => ({
  ok: true,
  status: 200,
  data: { access_token: `demo-${rol}`, user: { rol, departamento_id: 9 } },
}));
vi.mock("../api/demo", () => ({
  ES_DEMO: true,
  demoLogin: (rol) => demoLogin(rol),
}));

beforeEach(() => {
  login.mockClear();
  demoLogin.mockClear();
});

describe("CambiadorDeRol", () => {
  it("ofrece los tres perfiles", () => {
    render(<CambiadorDeRol />);
    expect(screen.getByRole("button", { name: /administración/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /al día/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /moroso/i })).toBeInTheDocument();
  });

  it("al elegir un perfil entra con ese perfil, sin recargar", async () => {
    const user = userEvent.setup();
    render(<CambiadorDeRol />);

    await user.click(screen.getByRole("button", { name: /administración/i }));

    expect(demoLogin).toHaveBeenCalledWith("administracion");
    expect(login).toHaveBeenCalled();
  });

  it("marca cuál es el perfil activo", () => {
    render(<CambiadorDeRol />);
    const activo = screen.getByRole("button", { name: /al día/i });
    expect(activo).toHaveAttribute("aria-current", "true");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/CambiadorDeRol.test.jsx`
Expected: FAIL — el componente no existe.

- [ ] **Step 3: Write minimal implementation**

```jsx
// frontend/src/components/CambiadorDeRol.jsx
import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { demoLogin } from "../api/demo";

/**
 * Cambia de perfil sin pasar por la pantalla de entrada.
 *
 * No es una comodidad: el estado de la demo vive en memoria, y volver al
 * selector recarga la página y lo borra. Sin esto no se puede mostrar el
 * circuito completo — presentar un pago como propietario y aprobarlo como
 * administración —, que es lo que la demo existe para mostrar.
 *
 * Sólo se renderiza en modo demo (ver `AppLayout`): en la aplicación de un
 * cliente la identidad la da el token, y cambiar de rol sin credenciales
 * sería un agujero de seguridad.
 */
const PERFILES = [
  { rol: "administracion", etiqueta: "Administración" },
  { rol: "propietario_al_dia", etiqueta: "Propietario al día" },
  { rol: "propietario_moroso", etiqueta: "Propietario moroso" },
];

export default function CambiadorDeRol() {
  const { user, login } = useAuth();
  const [cambiando, setCambiando] = useState(null);

  const esActivo = (rol) => {
    if (rol === "administracion") return user?.rol === "administracion";
    if (user?.rol !== "departamento") return false;
    // Entre los dos perfiles de propietario, el activo es el que coincide con
    // el departamento de la sesión; sin más datos, el primero.
    return rol === "propietario_al_dia"
      ? user?.departamento_id === 1
      : user?.departamento_id !== 1;
  };

  async function cambiar(rol) {
    if (esActivo(rol) || cambiando) return;
    setCambiando(rol);
    const r = await demoLogin(rol);
    if (r.ok) await login(r.data.access_token, r.data.user);
    setCambiando(null);
  }

  return (
    <nav className="cambiador-rol" aria-label="Ver la demo como">
      <span className="cambiador-rol-etiqueta">Ver como</span>
      {PERFILES.map(({ rol, etiqueta }) => (
        <button
          key={rol}
          type="button"
          onClick={() => cambiar(rol)}
          aria-current={esActivo(rol) ? "true" : undefined}
          disabled={cambiando !== null}
        >
          {etiqueta}
        </button>
      ))}
    </nav>
  );
}
```

En `AppLayout.jsx`, junto al banner de demo:

```jsx
      {ES_DEMO && <CambiadorDeRol />}
```

Y los estilos en `index.css`, con los tokens existentes: una fila de botones chicos, el activo destacado, que no desborde a 375px.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/CambiadorDeRol.test.jsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Verificar el circuito completo a mano**

Con el backend apagado y la demo levantada:

1. Entrar como Propietario moroso, anotar el saldo.
2. Presentar un pago por el saldo completo, con una imagen.
3. **Con el cambiador**, pasar a Administración — sin recargar.
4. Cobranzas → Comprobantes: el comprobante presentado tiene que estar ahí, pendiente.
5. Aprobarlo.
6. **Con el cambiador**, volver al Propietario moroso: el saldo tiene que estar en cero.

Este recorrido es el que hoy no se puede hacer. Si algún paso falla, esta tarea no está terminada.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/CambiadorDeRol.jsx frontend/src/components/CambiadorDeRol.test.jsx frontend/src/components/AppLayout.jsx frontend/src/index.css
git commit -m "feat(demo): cambiar de perfil sin recargar, para poder mostrar el circuito"
```

---

### Task 2: El aviso de arriba dice la verdad

Hoy dice "los datos se reinician cada 6 horas", que era cierto cuando había un servidor con un cron. En la demo del navegador es falso: los datos viven en la máquina de quien mira y se reinician al recargar.

**Files:**
- Modify: `frontend/src/components/BannerDemo.jsx`
- Test: `frontend/src/components/BannerDemo.test.jsx`

- [ ] **Step 1: Write the failing test**

```jsx
// frontend/src/components/BannerDemo.test.jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BannerDemo from "./BannerDemo";

const reiniciarDemo = vi.fn();
vi.mock("../demo/index.js", () => ({ reiniciarDemo: () => reiniciarDemo() }));

describe("BannerDemo", () => {
  it("no promete un reinicio que ya no ocurre", () => {
    render(<BannerDemo />);
    expect(screen.queryByText(/6 horas/i)).toBeNull();
  });

  it("explica que los datos son de quien mira", () => {
    render(<BannerDemo />);
    expect(screen.getByText(/en tu navegador/i)).toBeInTheDocument();
  });

  it("ofrece reiniciar la demo", async () => {
    const user = userEvent.setup();
    render(<BannerDemo />);
    await user.click(screen.getByRole("button", { name: /reiniciar/i }));
    expect(reiniciarDemo).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/BannerDemo.test.jsx`
Expected: FAIL — el texto viejo sigue ahí y no hay botón.

- [ ] **Step 3: Write minimal implementation**

El texto pasa a algo como: **"Esta demo corre entera en tu navegador. Nada de lo que hagas se guarda ni se comparte."**, con un botón "Reiniciar demo" que llama a `reiniciarDemo()` y recarga la vista.

Además de ser preciso, es argumento de venta: el visitante entiende que puede tocar lo que quiera.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/BannerDemo.test.jsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/BannerDemo.jsx frontend/src/components/BannerDemo.test.jsx
git commit -m "fix(demo): el aviso de arriba describe la demo que hay, no la que habia"
```

---

### Task 3: Las secciones fuera del recorrido, visibles y explicadas

Tesorería, Personal y Configuración siguen en el menú —la amplitud del producto es argumento de venta— pero no están implementadas en la demo. En vez de un error, muestran una pantalla que explica qué hace ese módulo.

**Files:**
- Create: `frontend/src/screens/ModuloNoIncluido.jsx`
- Modify: `frontend/src/App.jsx`
- Test: `frontend/src/screens/ModuloNoIncluido.test.jsx`

**Interfaces:**
- Produces: `<ModuloNoIncluido modulo="tesoreria" />`, con un catálogo de textos por módulo.

- [ ] **Step 1: Write the failing test**

```jsx
// frontend/src/screens/ModuloNoIncluido.test.jsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ModuloNoIncluido, { MODULOS } from "./ModuloNoIncluido";

describe("ModuloNoIncluido", () => {
  it("explica qué hace el módulo, no que está roto", () => {
    render(<ModuloNoIncluido modulo="personal" />);
    expect(screen.getByText(/liquidación|sueldo|encargado/i)).toBeInTheDocument();
    expect(screen.queryByText(/error|no disponible|roto/i)).toBeNull();
  });

  it("aclara que la sección existe en el sistema completo", () => {
    render(<ModuloNoIncluido modulo="tesoreria" />);
    expect(screen.getByText(/versión completa|sistema completo/i)).toBeInTheDocument();
  });

  it("tiene texto para cada módulo del catálogo", () => {
    for (const clave of Object.keys(MODULOS)) {
      const { unmount } = render(<ModuloNoIncluido modulo={clave} />);
      expect(screen.getByRole("heading")).toBeInTheDocument();
      unmount();
    }
  });

  it("con un módulo desconocido no explota", () => {
    render(<ModuloNoIncluido modulo="inventado" />);
    expect(screen.getByRole("heading")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/screens/ModuloNoIncluido.test.jsx`
Expected: FAIL — la pantalla no existe.

- [ ] **Step 3: Write minimal implementation**

Una pantalla con un catálogo `MODULOS` de tres entradas (tesorería, personal, configuración), cada una con título, dos o tres frases sobre qué resuelve, y una línea que aclara que está en el sistema completo. Sin capturas por ahora: agregarlas es un paso posterior y no bloquea.

En `App.jsx`, las rutas de esos módulos renderizan esta pantalla **sólo si `ES_DEMO`**; con la bandera apagada siguen renderizando la pantalla real.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/screens/ModuloNoIncluido.test.jsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Verificar que con la bandera apagada nada cambia**

Run: `cd frontend && VITE_DEMO_MODE=false npx vitest run`
Expected: la aplicación real sigue renderizando Tesorería, Personal y Configuración.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/screens/ModuloNoIncluido.jsx frontend/src/screens/ModuloNoIncluido.test.jsx frontend/src/App.jsx
git commit -m "feat(demo): las secciones fuera del recorrido explican que hacen"
```

---

### Task 4: Los PDF de boleta se abren desde el archivo estático

En la demo no hay servidor que genere el PDF, pero los 18 del último período están exportados. La pantalla del propietario tiene que abrir el suyo.

**Files:**
- Modify: `frontend/src/api/pdf.js`
- Test: `frontend/src/api/pdf.test.js`

**Interfaces:**
- Consumes: el mapa `_pdfs` del dataset.

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/api/pdf.test.js
import { describe, it, expect, vi, beforeEach } from "vitest";

describe("abrirPdfExpensa en modo demo", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("VITE_DEMO_MODE", "true");
    vi.stubGlobal("open", vi.fn());
    vi.stubGlobal("fetch", vi.fn());
  });

  it("abre el archivo estático, sin pedirle nada a ningún servidor", async () => {
    const DATASET = await import("../demo/dataset.json");
    const [id, nombre] = Object.entries(DATASET.default._pdfs)[0];

    const { abrirPdfExpensa } = await import("./pdf");
    await abrirPdfExpensa(Number(id));

    expect(fetch).not.toHaveBeenCalled();
    expect(window.open).toHaveBeenCalledWith(expect.stringContaining(nombre), "_blank");
  });

  it("una expensa sin PDF exportado avisa en vez de abrir una pestaña vacía", async () => {
    const { abrirPdfExpensa } = await import("./pdf");
    await expect(abrirPdfExpensa(999999)).rejects.toThrow(/no está/i);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api/pdf.test.js`
Expected: FAIL — hoy sale a la red.

- [ ] **Step 3: Write minimal implementation**

`abrirPdfExpensa` consulta primero si está en modo demo; si lo está, busca el nombre en el mapa `_pdfs` y abre `/demo-pdfs/<nombre>`. Si no está en el mapa, lanza un error con un mensaje entendible (sólo el último período tiene PDF exportado).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/api/pdf.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/pdf.js frontend/src/api/pdf.test.js
git commit -m "feat(demo): el PDF de la boleta se abre desde el archivo estatico"
```

---

### Task 5: El tablero del mes en curso invita en vez de mostrar ceros

**Esta tarea es del producto real, no de la demo**: se aplica con la bandera encendida o apagada.

La pantalla de inicio calcula el mes actual y, si todavía no se cerró, muestra la recaudación en `$0` con "0% cobrado". Le pasa a cualquier administrador que entre a principio de mes, no sólo al visitante de la demo. Un tablero en cero se lee como "el sistema no tiene datos" cuando en realidad el mes recién empieza.

**Files:**
- Modify: `frontend/src/screens/Inicio.jsx`
- Test: `frontend/src/screens/Inicio.test.jsx`

- [ ] **Step 1: Write the failing test**

```jsx
// frontend/src/screens/Inicio.test.jsx
// Con el mes en curso sin expensas emitidas, el hero no debe mostrar $0:
// tiene que mostrar el último período cerrado, diciendo cuál es.
it("sin expensas del mes en curso, muestra el último período cerrado", async () => {
  // ...montar Inicio con expensas sólo de períodos anteriores
  expect(await screen.findByText(/2026-07/)).toBeInTheDocument();
  expect(screen.queryByText("0% cobrado")).toBeNull();
});

it("y aclara que el mes en curso está abierto", async () => {
  expect(await screen.findByText(/en curso|sin cerrar/i)).toBeInTheDocument();
});
```

(El montaje exacto depende de cómo se mockeen las llamadas; seguir el patrón de los tests de pantalla que ya existan, o crear el primero con el mínimo necesario.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/screens/Inicio.test.jsx`
Expected: FAIL — hoy muestra `$0`.

- [ ] **Step 3: Write minimal implementation**

El hero pasa a mostrar **el último período con expensas emitidas**, con su nombre visible, y una línea que aclara que el mes en curso sigue abierto. La sección "requiere tu atención" ya avisa del cierre pendiente, así que no hace falta repetirlo.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS, sin romper nada.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/Inicio.jsx frontend/src/screens/Inicio.test.jsx
git commit -m "fix: el tablero muestra el ultimo periodo cerrado en vez de ceros"
```

---

### Task 6: Publicar

**Files:**
- Create: `frontend/vercel.json` (revisar el existente)
- Create: `docs/superpowers/2026-08-17-publicar-la-demo.md`

- [ ] **Step 1: Verificar el build de demo**

```bash
cd frontend && rm -rf dist && VITE_DEMO_MODE=true npm run build && npx vite preview --port 4200
```

Abrir `http://localhost:4200`, recorrer los dos circuitos y confirmar que **no sale ningún pedido a la red** en la pestaña correspondiente del navegador.

- [ ] **Step 2: Confirmar que el build de producción sigue limpio**

```bash
cd frontend && rm -rf dist && VITE_DEMO_MODE=false npm run build
grep -l "_generado" dist/assets/*.js && echo "PROBLEMA: el dataset entró" || echo "ok: el sustituto no se emite"
```

- [ ] **Step 3: Escribir las instrucciones de publicación**

Un documento corto con: qué proyecto de Vercel, qué variable de entorno lleva cada uno, que ambos apuntan a la misma rama, que el comando de build de la demo corre las pruebas primero (`npm test && npm run build`), y las dos advertencias del spec §7.3 — no encender la bandera en el proyecto de producción, y que el plan gratuito es para uso no comercial.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/2026-08-17-publicar-la-demo.md frontend/vercel.json
git commit -m "docs: como publicar la demo sin backend"
```

---

## Verificación manual antes de dar el plan por terminado

Con el backend **apagado**, el recorrido completo de venta:

1. Entrar. Leer el aviso de arriba: tiene que decir la verdad.
2. Como Administración: Inicio con el último período cerrado, no ceros.
3. Gastos → cargar uno en el mes abierto.
4. Cierre de período → validaciones → preview → confirmar.
5. Cobranzas: aparecen las expensas nuevas con el gasto repartido.
6. **Con el cambiador**, pasar a Propietario moroso: ver su deuda y su PDF.
7. Presentar un pago.
8. **Con el cambiador**, volver a Administración y aprobarlo.
9. **Con el cambiador**, volver al propietario: la deuda bajó.
10. Entrar a Tesorería: la pantalla explica el módulo, no muestra un error.
11. Apretar "Reiniciar demo": todo vuelve al arranque.

Los pasos 6, 8 y 9 son los que hoy no se pueden hacer. Son la razón de ser de este plan.

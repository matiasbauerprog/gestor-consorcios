export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

let _authToken = null;
let _consorcioActivoId = null;
let _onUnauthorized = null;
let _onCambioPasswordRequerido = null;

export function setAuthToken(token) {
  _authToken = token;
}

export function setConsorcioActivoId(id) {
  _consorcioActivoId = id == null ? null : String(id);
}

export function setUnauthorizedHandler(handler) {
  _onUnauthorized = handler;
}

export function setCambioPasswordRequeridoHandler(handler) {
  _onCambioPasswordRequerido = handler;
}

// Rutas que NO deben llevar X-Consorcio-Id automático.
const _RUTAS_SIN_TENANT = [
  "/auth/",
  "/me/",
  "/super-admin/",
];

function _requiereConsorcio(path) {
  return !_RUTAS_SIN_TENANT.some((p) => path.startsWith(p));
}

export async function apiFetch(path, { token, body, method = "GET", headers = {}, ...rest } = {}) {
  // En modo demo no hay servidor: un sustituto responde desde un dataset
  // estático en memoria. La importación es dinámica para que ni el módulo ni
  // el dataset entren en el paquete que descarga un cliente real.
  if (import.meta.env.VITE_DEMO_MODE === "true") {
    const { responderDemo } = await import("../demo/index.js");
    return responderDemo(method, path, body);
  }

  const tokenToUse = token !== undefined ? token : _authToken;
  const finalHeaders = { ...headers };
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

  if (body !== undefined && !isFormData && !finalHeaders["Content-Type"]) {
    finalHeaders["Content-Type"] = "application/json";
  }

  if (tokenToUse) {
    finalHeaders["Authorization"] = `Bearer ${tokenToUse}`;
  }

  // Inyectar X-Consorcio-Id automático si aplica.
  if (
    !finalHeaders["X-Consorcio-Id"] &&
    _consorcioActivoId &&
    _requiereConsorcio(path)
  ) {
    finalHeaders["X-Consorcio-Id"] = _consorcioActivoId;
  }

  const res = await fetch(API_BASE + path, {
    method,
    headers: finalHeaders,
    body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
    ...rest,
  });

  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  // Auto-logout solo si el request fue autenticado.
  if (res.status === 401 && tokenToUse && _onUnauthorized) {
    _onUnauthorized();
  }

  // 403 cambio_password_requerido: patear a la pantalla de cambio.
  if (
    res.status === 403 &&
    data &&
    typeof data === "object" &&
    data.detail === "cambio_password_requerido" &&
    _onCambioPasswordRequerido
  ) {
    _onCambioPasswordRequerido();
  }

  return { ok: res.ok, status: res.status, data };
}

/**
 * Abre un PDF autenticado en una nueva pestaña. Inyecta Authorization y
 * X-Consorcio-Id igual que apiFetch (los endpoints de PDF están scoped por
 * consorcio, un fetch sin el header devuelve 400).
 */
export async function abrirPdf(path) {
  const headers = {};
  if (_authToken) headers["Authorization"] = `Bearer ${_authToken}`;
  if (_consorcioActivoId && _requiereConsorcio(path)) {
    headers["X-Consorcio-Id"] = _consorcioActivoId;
  }
  const res = await fetch(API_BASE + path, { headers });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

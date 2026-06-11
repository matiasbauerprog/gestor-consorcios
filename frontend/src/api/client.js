const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

let _authToken = null;
let _onUnauthorized = null;

export function setAuthToken(token) {
  _authToken = token;
}

export function setUnauthorizedHandler(handler) {
  _onUnauthorized = handler;
}

export async function apiFetch(path, { token, body, method = "GET", headers = {}, ...rest } = {}) {
  const tokenToUse = token !== undefined ? token : _authToken;
  const finalHeaders = { ...headers };

  if (body !== undefined && !finalHeaders["Content-Type"]) {
    finalHeaders["Content-Type"] = "application/json";
  }

  if (tokenToUse) {
    finalHeaders["Authorization"] = `Bearer ${tokenToUse}`;
  }

  const res = await fetch(API_BASE + path, {
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
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

  // Auto-logout solo si el request fue autenticado: un 401 con token significa
  // token expirado/revocado. Un 401 sin token (ej. credenciales malas en /auth/login)
  // lo maneja el componente.
  if (res.status === 401 && tokenToUse && _onUnauthorized) {
    _onUnauthorized();
  }

  return { ok: res.ok, status: res.status, data };
}

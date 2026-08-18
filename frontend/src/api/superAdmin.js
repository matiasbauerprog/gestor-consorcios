import { apiFetch } from "./client";

export async function listarAdministraciones() {
  return apiFetch("/super-admin/administraciones");
}

export async function obtenerAdministracion(id) {
  return apiFetch(`/super-admin/administraciones/${id}`);
}

export async function crearAdministracion(body) {
  return apiFetch("/super-admin/administraciones", { method: "POST", body });
}

export async function editarAdministracion(id, body) {
  return apiFetch(`/super-admin/administraciones/${id}`, {
    method: "PATCH",
    body,
  });
}

export async function toggleSuspenderAdministracion(id) {
  return apiFetch(`/super-admin/administraciones/${id}/suspender`, {
    method: "POST",
  });
}

export async function listarUsuariosDeAdministracion(administracionId) {
  return apiFetch(`/super-admin/administraciones/${administracionId}/usuarios`);
}

export async function resetPasswordUsuario(administracionId, userId) {
  return apiFetch(
    `/super-admin/administraciones/${administracionId}/reset-password/${userId}`,
    { method: "POST" }
  );
}

export async function impersonateStart(usuarioId, motivo) {
  return apiFetch("/super-admin/impersonate/start", {
    method: "POST",
    body: { usuario_id: usuarioId, motivo },
  });
}

export async function impersonateEnd() {
  return apiFetch("/super-admin/impersonate/end", { method: "POST" });
}

export async function obtenerModulos(administracionId) {
  return apiFetch(`/super-admin/administraciones/${administracionId}/modulos`);
}

export async function guardarModulos(administracionId, habilitados) {
  return apiFetch(`/super-admin/administraciones/${administracionId}/modulos`, {
    method: "PUT",
    body: { habilitados },
  });
}

export async function obtenerMetricas() {
  return apiFetch("/super-admin/metricas");
}

export async function listarErrores({ limit = 50, offset = 0 } = {}) {
  const p = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiFetch(`/super-admin/errores?${p.toString()}`);
}

export async function buscarErrorPorCodigo(codigo) {
  return apiFetch(`/super-admin/errores/${encodeURIComponent(codigo.trim())}`);
}

export async function listarAuditLog({
  accion,
  administracionId,
  limit = 50,
  offset = 0,
} = {}) {
  const p = new URLSearchParams();
  if (accion) p.set("accion", accion);
  if (administracionId) p.set("administracion_id", String(administracionId));
  p.set("limit", String(limit));
  p.set("offset", String(offset));
  return apiFetch(`/super-admin/audit-log?${p.toString()}`);
}

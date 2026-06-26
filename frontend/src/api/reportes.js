import { apiFetch, API_BASE } from "./client";

// JSON endpoints
export function listarMorosos({ soloDeudores = true } = {}) {
  return apiFetch(`/reportes/morosos?solo_deudores=${soloDeudores}`);
}

export function obtenerEstadoFinanciero(fechaCorte) {
  const qs = fechaCorte ? `?fecha_corte=${fechaCorte}` : "";
  return apiFetch(`/reportes/estado-financiero${qs}`);
}

export function obtenerGastosDelPeriodo(periodo, { rubro, proveedorId } = {}) {
  const params = new URLSearchParams();
  if (rubro) params.set("rubro", rubro);
  if (proveedorId != null) params.set("proveedor_id", proveedorId);
  const qs = params.toString() ? `?${params}` : "";
  return apiFetch(`/reportes/gastos/${periodo}${qs}`);
}

export function listarProveedores({ anio, periodo } = {}) {
  const params = new URLSearchParams();
  if (anio) params.set("anio", anio);
  if (periodo) params.set("periodo", periodo);
  const qs = params.toString() ? `?${params}` : "";
  return apiFetch(`/reportes/proveedores${qs}`);
}

// PDFs — abren en nueva pestaña con blob URL (mismo patrón que api/pdf.js)
async function _abrirPdf(path, token) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function abrirPdfMorosos({ soloDeudores = true }, token) {
  return _abrirPdf(`/reportes/morosos/pdf?solo_deudores=${soloDeudores}`, token);
}

export function abrirPdfEstadoFinanciero(fechaCorte, token) {
  const qs = fechaCorte ? `?fecha_corte=${fechaCorte}` : "";
  return _abrirPdf(`/reportes/estado-financiero/pdf${qs}`, token);
}

export function abrirPdfGastosPeriodo(periodo, filtros, token) {
  const params = new URLSearchParams();
  if (filtros?.rubro) params.set("rubro", filtros.rubro);
  if (filtros?.proveedorId != null) params.set("proveedor_id", filtros.proveedorId);
  const qs = params.toString() ? `?${params}` : "";
  return _abrirPdf(`/reportes/gastos/${periodo}/pdf${qs}`, token);
}

export function abrirPdfProveedores({ anio, periodo }, token) {
  const params = new URLSearchParams();
  if (anio) params.set("anio", anio);
  if (periodo) params.set("periodo", periodo);
  const qs = params.toString() ? `?${params}` : "";
  return _abrirPdf(`/reportes/proveedores/pdf${qs}`, token);
}

import { apiFetch, abrirPdf } from "./client";

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

// PDFs — abren en nueva pestaña; token y X-Consorcio-Id los inyecta el client.
export function abrirPdfMorosos({ soloDeudores = true } = {}) {
  return abrirPdf(`/reportes/morosos/pdf?solo_deudores=${soloDeudores}`);
}

export function abrirPdfEstadoFinanciero(fechaCorte) {
  const qs = fechaCorte ? `?fecha_corte=${fechaCorte}` : "";
  return abrirPdf(`/reportes/estado-financiero/pdf${qs}`);
}

export function abrirPdfGastosPeriodo(periodo, filtros) {
  const params = new URLSearchParams();
  if (filtros?.rubro) params.set("rubro", filtros.rubro);
  if (filtros?.proveedorId != null) params.set("proveedor_id", filtros.proveedorId);
  const qs = params.toString() ? `?${params}` : "";
  return abrirPdf(`/reportes/gastos/${periodo}/pdf${qs}`);
}

export function abrirPdfProveedores({ anio, periodo } = {}) {
  const params = new URLSearchParams();
  if (anio) params.set("anio", anio);
  if (periodo) params.set("periodo", periodo);
  const qs = params.toString() ? `?${params}` : "";
  return abrirPdf(`/reportes/proveedores/pdf${qs}`);
}

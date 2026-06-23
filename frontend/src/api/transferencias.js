import { apiFetch } from "./client";

export function listarTransferencias() {
  return apiFetch("/transferencias-caja");
}

export function crearTransferencia(payload) {
  return apiFetch("/transferencias-caja", { method: "POST", body: payload });
}

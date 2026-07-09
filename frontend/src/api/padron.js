import { apiFetch } from "./client";

export function importarPadronCSV(file) {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch("/padron/importar", { method: "POST", body: formData });
}

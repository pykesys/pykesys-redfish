const BASE = "/api";

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const getFleet = () => apiFetch("/fleet/");
export const getHost = (id) => apiFetch(`/hosts/${id}/`);
export const getSnapshots = (id, page = 1) => apiFetch(`/hosts/${id}/snapshots/?page=${page}`);
export const getSensors = (id) => apiFetch(`/hosts/${id}/sensors/`);
export const getLogs = (id, page = 1) => apiFetch(`/hosts/${id}/logs/?page=${page}`);
export const createHost = (data) => apiFetch("/hosts/", { method: "POST", body: JSON.stringify(data) });
export const updateHost = (id, data) => apiFetch(`/hosts/${id}/`, { method: "PATCH", body: JSON.stringify(data) });
export const deleteHost = (id) => apiFetch(`/hosts/${id}/`, { method: "DELETE" });
export const pollHost = (id) => apiFetch(`/hosts/${id}/poll/`, { method: "POST", body: "{}" });
export const powerAction = (id, resetType) =>
  apiFetch(`/hosts/${id}/power/`, { method: "POST", body: JSON.stringify({ reset_type: resetType }) });
export const bootAction = (id, target, enabled = "Once") =>
  apiFetch(`/hosts/${id}/boot/`, { method: "POST", body: JSON.stringify({ target, enabled }) });
export const getRules = () => apiFetch("/alerts/rules/");
export const createRule = (data) => apiFetch("/alerts/rules/", { method: "POST", body: JSON.stringify(data) });
export const deleteRule = (id) => apiFetch(`/alerts/rules/${id}/`, { method: "DELETE" });
export const getEvents = (params = "") => apiFetch(`/alerts/events/${params}`);
export const resolveEvent = (id) => apiFetch(`/alerts/events/${id}/resolve/`, { method: "POST", body: "{}" });

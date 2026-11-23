// API actions — URLs align one-to-one with api-admin.md (GR-05).

import { apiFetch } from "./client";
import type {
  ClientKey,
  ConfigView,
  Dashboard,
  Page,
  RequestLog,
  SetupResult,
  SetupStatus,
  UpstreamKey,
  Usage,
} from "./types";

const BASE = "/api/v1/admin";

// ---- first-run setup + auth (public) ----

export const getSetupStatus = () => apiFetch<SetupStatus>("/api/v1/setup/status");

export const setupInit = (body: {
  nvidia_key: string;
  admin_password: string;
  client_key_name?: string;
}) => apiFetch<SetupResult>("/api/v1/setup/init", { method: "POST", body: JSON.stringify(body) });

export const login = (password: string) =>
  apiFetch<{ token: string }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ password }),
  });

export const getDashboard = () => apiFetch<Dashboard>(`${BASE}/dashboard`);
export const getConfig = () => apiFetch<ConfigView>(`${BASE}/config`);

export const listUpstreamKeys = () => apiFetch<UpstreamKey[]>(`${BASE}/upstream-keys`);
export const createUpstreamKey = (label: string, secret: string) =>
  apiFetch<UpstreamKey>(`${BASE}/upstream-keys`, {
    method: "POST",
    body: JSON.stringify({ label, secret }),
  });
export const deleteUpstreamKey = (id: string) =>
  apiFetch<void>(`${BASE}/upstream-keys/${id}`, { method: "DELETE" });
export const enableUpstreamKey = (id: string) =>
  apiFetch<UpstreamKey>(`${BASE}/upstream-keys/${id}/enable`, { method: "POST" });
export const disableUpstreamKey = (id: string) =>
  apiFetch<UpstreamKey>(`${BASE}/upstream-keys/${id}/disable`, { method: "POST" });

export const listClientKeys = () => apiFetch<ClientKey[]>(`${BASE}/client-keys`);
export const createClientKey = (name: string) =>
  apiFetch<ClientKey>(`${BASE}/client-keys`, { method: "POST", body: JSON.stringify({ name }) });
export const revokeClientKey = (id: string) =>
  apiFetch<void>(`${BASE}/client-keys/${id}`, { method: "DELETE" });
export const enableClientKey = (id: string) =>
  apiFetch<ClientKey>(`${BASE}/client-keys/${id}/enable`, { method: "POST" });
export const disableClientKey = (id: string) =>
  apiFetch<ClientKey>(`${BASE}/client-keys/${id}/disable`, { method: "POST" });

export const getUsage = (params: {
  dimension_type: string;
  bucket_type: string;
  start?: string;
  end?: string;
}) => {
  const q = new URLSearchParams({
    dimension_type: params.dimension_type,
    bucket_type: params.bucket_type,
  });
  if (params.start) q.set("start", params.start);
  if (params.end) q.set("end", params.end);
  return apiFetch<Usage[]>(`${BASE}/usage?${q.toString()}`);
};

export const listRequestLogs = (params: {
  client_key_id?: string;
  model?: string;
  status?: string;
  start?: string;
  end?: string;
  page_num: number;
  page_size: number;
}) => {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") q.set(k, String(v));
  }
  return apiFetch<Page<RequestLog>>(`${BASE}/request-logs?${q.toString()}`);
};

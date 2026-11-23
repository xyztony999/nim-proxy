// Fetch wrapper: bearer token, unified error body, 401 -> login.

const TOKEN_KEY = "nim_admin_token";

export function getToken(): string {
  return sessionStorage.getItem(TOKEN_KEY) ?? "";
}
export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const resp = await fetch(path, { ...init, headers });
  if (resp.status === 401) {
    clearToken();
    if (!location.pathname.endsWith("/login")) {
      location.href = "/admin/login";
    }
  }
  if (resp.status === 204) return undefined as T;
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const err = data?.error ?? {};
    throw new ApiError(resp.status, err.code ?? "http_error", err.message ?? resp.statusText);
  }
  return data as T;
}

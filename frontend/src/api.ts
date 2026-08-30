// Development uses the local launcher. Production serves the frontend and API
// from the same HTTPS origin, so phones never need a private LAN address.
const API_URL = import.meta.env.VITE_API_URL
  ?? (import.meta.env.PROD ? "/api/v1" : "http://127.0.0.1:8001/api/v1");

export type User = { id: number; username: string; role: string; is_active: boolean };

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

function errorMessage(detail: unknown): string {
  if (Array.isArray(detail)) {
    return detail.map(item => {
      const message = item && typeof item === "object" && "msg" in item ? String(item.msg) : "ข้อมูลไม่ถูกต้อง";
      if (message.includes("end_date must not be before start_date")) return "วันสิ้นสุดการลาต้องเป็นวันเดียวกันหรือหลังวันเริ่มลา";
      return message.replace(/^Value error,\s*/i, "");
    }).join(" • ");
  }
  if (typeof detail === "string") return detail;
  return "ข้อมูลที่กรอกไม่ถูกต้อง กรุณาตรวจสอบอีกครั้ง";
}

export function getToken(): string | null { return localStorage.getItem("access_token"); }
export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem("access_token", accessToken);
  localStorage.setItem("refresh_token", refreshToken);
}
export function clearTokens(): void { localStorage.removeItem("access_token"); localStorage.removeItem("refresh_token"); }

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const request = async (token: string | null) => {
    const headers = new Headers(options.headers);
    headers.set("Content-Type", "application/json");
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(`${API_URL}${path}`, { ...options, headers });
  };

  let response = await request(getToken());
  if (response.status === 401 && path !== "/auth/refresh") {
    const refreshToken = localStorage.getItem("refresh_token");
    if (refreshToken) {
      const refreshResponse = await fetch(
        `${API_URL}/auth/refresh`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        },
      );
      if (refreshResponse.ok) {
        const tokens = await refreshResponse.json() as { access_token: string; refresh_token: string };
        setTokens(tokens.access_token, tokens.refresh_token);
        response = await request(tokens.access_token);
      }
    }
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(errorMessage(body.detail), response.status);
  return body as T;
}

export async function login(username: string, password: string): Promise<void> {
  const tokens = await api<{ access_token: string; refresh_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
  setTokens(tokens.access_token, tokens.refresh_token);
}

const API_BASE_URL = window.location.port === "5173"
  ? "http://localhost:8000/api"
  : "/api";

export function getAuthToken(): string | null {
  return localStorage.getItem("telescrape_token");
}

export function getAuthRole(): string | null {
  return localStorage.getItem("telescrape_role");
}

export function getAuthUsername(): string | null {
  return localStorage.getItem("telescrape_username");
}

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const token = getAuthToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errText = await response.text();
    let errMsg = "API error";
    try {
      errMsg = JSON.parse(errText).detail || errMsg;
    } catch {
      errMsg = errText || errMsg;
    }
    throw new Error(errMsg);
  }

  return response.json();
}

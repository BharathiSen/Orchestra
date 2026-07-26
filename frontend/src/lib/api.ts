export type User = {
  id: number;
  email: string;
  full_name: string | null;
  created_at: string;
};

export type Project = {
  id: number;
  name: string;
  description: string | null;
  owner_id: number;
  created_at: string;
  updated_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const data = await response.json();
      detail = data.detail || detail;
      if (Array.isArray(detail)) {
        detail = detail.map((item) => item.msg || JSON.stringify(item)).join(", ");
      }
    } catch {
      // ignore parse errors
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  signup: (body: { email: string; password: string; full_name?: string }) =>
    request<AuthResponse>("/api/v1/auth/signup", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  login: (body: { email: string; password: string }) =>
    request<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  me: (token: string) => request<User>("/api/v1/auth/me", {}, token),
  listProjects: (token: string) =>
    request<Project[]>("/api/v1/projects", {}, token),
  createProject: (
    token: string,
    body: { name: string; description?: string },
  ) =>
    request<Project>(
      "/api/v1/projects",
      { method: "POST", body: JSON.stringify(body) },
      token,
    ),
  updateProject: (
    token: string,
    id: number,
    body: { name?: string; description?: string },
  ) =>
    request<Project>(
      `/api/v1/projects/${id}`,
      { method: "PATCH", body: JSON.stringify(body) },
      token,
    ),
  deleteProject: (token: string, id: number) =>
    request<void>(`/api/v1/projects/${id}`, { method: "DELETE" }, token),
};

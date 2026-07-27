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

export type Agent = {
  id: number;
  name: string;
  description: string | null;
  system_prompt: string;
  model_name: string;
  project_id: number;
  created_at: string;
  updated_at: string;
};

export type Conversation = {
  id: number;
  project_id: number;
  agent_id: number | null;
  title: string;
  model_name: string;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: number;
  conversation_id: number;
  role: string;
  content: string;
  created_at: string;
};

export type ChatModel = {
  id: string;
  label: string;
  description: string;
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
        detail = detail
          .map((item) => item.msg || JSON.stringify(item))
          .join(", ");
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

export type ToolInfo = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
};

export type ToolEvent = {
  tool_call_id: string;
  tool_name: string;
  arguments?: string;
  status: "running" | "complete" | "error";
  result?: string;
};

export type ChatStreamHandlers = {
  onMeta?: (data: { conversation_id: number; title: string }) => void;
  onUserMessage?: (data: ChatMessage) => void;
  onToken?: (token: string) => void;
  onToolStart?: (data: ToolEvent) => void;
  onToolResult?: (data: ToolEvent) => void;
  onDone?: (data: { message_id: number; conversation_id: number }) => void;
  onError?: (detail: string) => void;
};

export async function streamChat(
  token: string,
  body: {
    project_id: number;
    message: string;
    conversation_id?: number | null;
    agent_id?: number | null;
    model?: string;
    temperature?: number;
    system_prompt?: string;
    enable_tools?: boolean;
  },
  handlers: ChatStreamHandlers,
): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let detail = "Chat request failed";
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  if (!response.body) {
    throw new ApiError(500, "No response body from chat stream");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const line = part
        .split("\n")
        .map((l) => l.trim())
        .find((l) => l.startsWith("data:"));
      if (!line) continue;
      const jsonText = line.replace(/^data:\s*/, "");
      try {
        const event = JSON.parse(jsonText) as {
          type: string;
          conversation_id?: number;
          title?: string;
          id?: number;
          role?: string;
          content?: string;
          message_id?: number;
          detail?: string;
          created_at?: string;
          tool_call_id?: string;
          tool_name?: string;
          arguments?: string;
          status?: "running" | "complete" | "error";
          result?: string;
        };

        if (event.type === "meta" && event.conversation_id != null) {
          handlers.onMeta?.({
            conversation_id: event.conversation_id,
            title: event.title || "New conversation",
          });
        } else if (event.type === "user_message" && event.id != null) {
          handlers.onUserMessage?.({
            id: event.id,
            conversation_id: event.conversation_id || 0,
            role: event.role || "user",
            content: event.content || "",
            created_at: event.created_at || new Date().toISOString(),
          });
        } else if (event.type === "tool_start" && event.tool_name) {
          handlers.onToolStart?.({
            tool_call_id: event.tool_call_id || event.tool_name,
            tool_name: event.tool_name,
            arguments: event.arguments,
            status: "running",
          });
        } else if (event.type === "tool_result" && event.tool_name) {
          handlers.onToolResult?.({
            tool_call_id: event.tool_call_id || event.tool_name,
            tool_name: event.tool_name,
            status: event.status || "complete",
            result: event.result,
          });
        } else if (event.type === "token" && event.content) {
          handlers.onToken?.(event.content);
        } else if (event.type === "done" && event.conversation_id != null) {
          handlers.onDone?.({
            message_id: event.message_id || 0,
            conversation_id: event.conversation_id,
          });
        } else if (event.type === "error") {
          handlers.onError?.(event.detail || "Chat stream error");
        }
      } catch {
        // skip malformed SSE chunks
      }
    }
  }
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
  getProject: (token: string, id: number) =>
    request<Project>(`/api/v1/projects/${id}`, {}, token),
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

  listAgents: (token: string, projectId?: number) => {
    const query =
      projectId !== undefined ? `?project_id=${projectId}` : "";
    return request<Agent[]>(`/api/v1/agents${query}`, {}, token);
  },
  getAgent: (token: string, id: number) =>
    request<Agent>(`/api/v1/agents/${id}`, {}, token),
  createAgent: (
    token: string,
    body: {
      name: string;
      project_id: number;
      description?: string;
      system_prompt?: string;
      model_name?: string;
    },
  ) =>
    request<Agent>(
      "/api/v1/agents",
      { method: "POST", body: JSON.stringify(body) },
      token,
    ),
  updateAgent: (
    token: string,
    id: number,
    body: {
      name?: string;
      description?: string;
      system_prompt?: string;
      model_name?: string;
      project_id?: number;
    },
  ) =>
    request<Agent>(
      `/api/v1/agents/${id}`,
      { method: "PATCH", body: JSON.stringify(body) },
      token,
    ),
  deleteAgent: (token: string, id: number) =>
    request<void>(`/api/v1/agents/${id}`, { method: "DELETE" }, token),

  listModels: (token: string) =>
    request<{
      models: ChatModel[];
      gemini_configured: boolean;
      llm_configured?: boolean;
      provider?: string;
    }>("/api/v1/chat/models", {}, token),
  listTools: (token: string) =>
    request<{ tools: ToolInfo[]; count: number }>("/api/v1/tools", {}, token),
  listConversations: (token: string, projectId: number) =>
    request<Conversation[]>(
      `/api/v1/conversations?project_id=${projectId}`,
      {},
      token,
    ),
  getConversation: (token: string, id: number) =>
    request<Conversation>(`/api/v1/conversations/${id}`, {}, token),
  createConversation: (
    token: string,
    body: {
      project_id: number;
      title?: string;
      agent_id?: number | null;
      model_name?: string;
    },
  ) =>
    request<Conversation>(
      "/api/v1/conversations",
      { method: "POST", body: JSON.stringify(body) },
      token,
    ),
  deleteConversation: (token: string, id: number) =>
    request<void>(`/api/v1/conversations/${id}`, { method: "DELETE" }, token),
  listMessages: (token: string, conversationId: number) =>
    request<ChatMessage[]>(
      `/api/v1/conversations/${conversationId}/messages`,
      {},
      token,
    ),
};

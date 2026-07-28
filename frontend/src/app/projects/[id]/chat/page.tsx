"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  api,
  streamChat,
  type Agent,
  type ChatMessage,
  type ChatModel,
  type Conversation,
  type GraphNodeName,
  type GraphStepEvent,
  type Project,
  type ToolEvent,
  type ToolInfo,
} from "@/lib/api";
import { clearSession, getToken } from "@/lib/auth";

type UiMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools?: ToolEvent[];
  graphSteps?: GraphStepEvent[];
};

function toolLabel(name: string): string {
  if (name === "calculator") return "Calculator";
  if (name === "weather") return "Weather";
  if (name === "search") return "Search";
  return name;
}

function ToolPanel({ tools }: { tools: ToolEvent[] }) {
  if (!tools.length) return null;
  return (
    <div className="mb-2 space-y-1.5">
      {tools.map((t) => (
        <div
          key={t.tool_call_id}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold">
              {toolLabel(t.tool_name)}
            </span>
            <span
              className={
                t.status === "running"
                  ? "text-amber-700"
                  : t.status === "error"
                    ? "text-red-700"
                    : "text-teal-700"
              }
            >
              {t.status === "running"
                ? "Running…"
                : t.status === "error"
                  ? "Error"
                  : "Complete"}
            </span>
          </div>
          {t.result && (
            <p className="mt-1 whitespace-pre-wrap text-[11px] text-slate-600">
              {t.result.length > 280 ? `${t.result.slice(0, 277)}…` : t.result}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

function GraphExecutionPanel({ steps }: { steps: GraphStepEvent[] }) {
  if (!steps.length) return null;
  const nodeLabel: Record<GraphNodeName, string> = {
    planner: "Planner",
    tool: "Tool",
    reviewer: "Reviewer",
    answer: "Final Answer",
  };

  const latestByNode = new Map<GraphNodeName, GraphStepEvent>();
  for (const step of steps) {
    latestByNode.set(step.node, step);
  }

  const orderedNodes: GraphNodeName[] = ["planner", "tool", "reviewer", "answer"];

  return (
    <div className="mb-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
      <p className="mb-1 font-semibold text-slate-800">Execution</p>
      <div className="space-y-1.5">
        {orderedNodes.map((node) => {
          const step = latestByNode.get(node);
          const status = step?.status;
          const statusText =
            status === "running" ? "Running…" : status === "done" ? "✓" : status === "error" ? "Error" : "Pending";
          const statusClass =
            status === "running"
              ? "text-amber-700"
              : status === "done"
                ? "text-teal-700"
                : status === "error"
                  ? "text-red-700"
                  : "text-slate-400";

          return (
            <div key={node}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{nodeLabel[node]}</span>
                <span className={statusClass}>{statusText}</span>
              </div>
              {step?.summary && (
                <p className="mt-0.5 text-[11px] text-slate-500">{step.summary}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function ProjectChatPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  const [token, setToken] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(
    null,
  );
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [models, setModels] = useState<ChatModel[]>([]);
  const [toolsCatalog, setToolsCatalog] = useState<ToolInfo[]>([]);
  const [llmConfigured, setLlmConfigured] = useState(true);
  const [provider, setProvider] = useState("groq");
  const [model, setModel] = useState("llama-3.1-8b-instant");
  const [agentId, setAgentId] = useState<number | "">("");
  const [temperature, setTemperature] = useState(0.2);
  const [enableTools, setEnableTools] = useState(true);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const selectedAgent = agents.find((a) => a.id === agentId);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const refreshConversations = useCallback(
    async (authToken: string) => {
      const list = await api.listConversations(authToken, projectId);
      setConversations(list);
      return list;
    },
    [projectId],
  );

  const loadConversationMessages = useCallback(
    async (authToken: string, conversationId: number) => {
      const rows = await api.listMessages(authToken, conversationId);
      setMessages(
        rows
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map((m: ChatMessage) => ({
            id: String(m.id),
            role: m.role as "user" | "assistant",
            content: m.content,
          })),
      );
    },
    [],
  );

  useEffect(() => {
    if (!Number.isFinite(projectId)) {
      router.replace("/projects");
      return;
    }
    const authToken = getToken();
    if (!authToken) {
      router.replace("/login");
      return;
    }
    setToken(authToken);

    Promise.all([
      api.getProject(authToken, projectId),
      api.listAgents(authToken, projectId),
      api.listConversations(authToken, projectId),
      api.listModels(authToken),
      api.listTools(authToken).catch(() => ({ tools: [], count: 0 })),
    ])
      .then(([projectData, agentList, conversationList, modelData, toolsData]) => {
        setProject(projectData);
        setAgents(agentList);
        setConversations(conversationList);
        setModels(modelData.models);
        setToolsCatalog(toolsData.tools || []);
        setLlmConfigured(
          modelData.llm_configured ?? modelData.gemini_configured,
        );
        setProvider(modelData.provider || "groq");
        if (modelData.models.length > 0) {
          setModel(modelData.models[0].id);
        }
        if (conversationList.length > 0) {
          setActiveConversationId(conversationList[0].id);
        }
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Failed to load chat");
      })
      .finally(() => setLoading(false));
  }, [projectId, router]);

  useEffect(() => {
    if (!token || !activeConversationId) {
      setMessages([]);
      return;
    }
    loadConversationMessages(token, activeConversationId).catch((err) => {
      setError(err instanceof ApiError ? err.message : "Failed to load messages");
    });
  }, [token, activeConversationId, loadConversationMessages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  async function onNewChat() {
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
  }

  async function onSelectConversation(id: number) {
    setActiveConversationId(id);
    setError(null);
  }

  async function onDeleteConversation(id: number) {
    if (!token) return;
    try {
      await api.deleteConversation(token, id);
      const list = await refreshConversations(token);
      if (activeConversationId === id) {
        setActiveConversationId(list[0]?.id ?? null);
        if (!list[0]) setMessages([]);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete conversation");
    }
  }

  async function onSend(event: FormEvent) {
    event.preventDefault();
    if (!token || !input.trim() || sending) return;

    const userText = input.trim();
    setInput("");
    setSending(true);
    setError(null);

    const optimisticUser: UiMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content: userText,
    };
    const assistantId = `local-assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      optimisticUser,
      { id: assistantId, role: "assistant", content: "", tools: [] },
    ]);

    try {
      await streamChat(
        token,
        {
          project_id: projectId,
          message: userText,
          conversation_id: activeConversationId,
          agent_id: agentId === "" ? null : agentId,
          model,
          temperature,
          system_prompt: selectedAgent?.system_prompt || undefined,
          enable_tools: enableTools,
        },
        {
          onMeta: ({ conversation_id }) => {
            setActiveConversationId(conversation_id);
          },
          onToolStart: (tool) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      tools: [
                        ...(m.tools || []).filter(
                          (t) => t.tool_call_id !== tool.tool_call_id,
                        ),
                        tool,
                      ],
                    }
                  : m,
              ),
            );
          },
          onToolResult: (tool) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      tools: (m.tools || []).map((t) =>
                        t.tool_call_id === tool.tool_call_id ? { ...t, ...tool } : t,
                      ),
                    }
                  : m,
              ),
            );
          },
          onGraphStep: (step) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      graphSteps: [
                        ...(m.graphSteps || []).filter(
                          (s) => !(s.node === step.node && s.status === step.status && s.summary === step.summary),
                        ),
                        step,
                      ],
                    }
                  : m,
              ),
            );
          },
          onToken: (tokenText) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + tokenText }
                  : m,
              ),
            );
          },
          onError: (detail) => {
            setError(detail);
          },
          onDone: async () => {
            await refreshConversations(token);
          },
        },
      );

      const list = await refreshConversations(token);
      const currentId =
        activeConversationId ??
        list.find((c) => c.title.includes(userText.slice(0, 20)))?.id ??
        list[0]?.id ??
        null;
      if (currentId) {
        setActiveConversationId(currentId);
        // Keep live tool cards for this turn; reload only if we need canonical ids.
        const rows = await api.listMessages(token, currentId);
        setMessages((prev) => {
          const liveTools =
            prev.find((m) => m.id === assistantId)?.tools || [];
          const liveGraphSteps =
            prev.find((m) => m.id === assistantId)?.graphSteps || [];
          return rows
            .filter((m) => m.role === "user" || m.role === "assistant")
            .map((m: ChatMessage, idx, arr) => {
              const isLastAssistant =
                m.role === "assistant" &&
                idx === arr.map((x) => x.role).lastIndexOf("assistant");
              return {
                id: String(m.id),
                role: m.role as "user" | "assistant",
                content: m.content,
                tools: isLastAssistant ? liveTools : undefined,
                graphSteps: isLastAssistant ? liveGraphSteps : undefined,
              };
            });
        });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Chat failed");
      setMessages((prev) => prev.filter((m) => m.id !== assistantId));
    } finally {
      setSending(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-[1400px] items-center justify-center px-4 md:px-6 lg:px-8">
        <p className="text-slate-500">Loading chat...</p>
      </main>
    );
  }

  if (!project) return null;

  return (
    <main className="mx-auto flex h-screen w-full max-w-[1400px] flex-col overflow-hidden px-4 py-6 md:px-6 lg:px-8">
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
            Orchestra
          </p>
          <h1 className="mt-1 font-display text-2xl font-bold md:text-3xl">
            Chat · {project.name}
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Streaming chat with optional tools: calculator, weather, and search.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/projects/${projectId}`}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
          >
            Agents
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
          >
            Dashboard
          </Link>
        </div>
      </header>

      {!llmConfigured && (
        <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          LLM provider <code>{provider}</code> is not configured. For free
          testing set <code>LLM_PROVIDER=groq</code> and{" "}
          <code>GROQ_API_KEY</code> (or use <code>ollama</code>). For production
          use <code>LLM_PROVIDER=gemini</code> + <code>GEMINI_API_KEY</code>,
          then restart the backend.
        </p>
      )}
      {llmConfigured && (
        <p className="mb-4 text-xs text-slate-500">
          Active provider: <span className="font-medium">{provider}</span>
          {toolsCatalog.length > 0 && (
            <>
              {" "}
              · Tools:{" "}
              <span className="font-medium">
                {toolsCatalog.map((t) => t.name).join(", ")}
              </span>
            </>
          )}
        </p>
      )}

      {error && (
        <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="min-h-0 rounded-2xl border border-slate-200 bg-white/80 p-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-700">Conversations</h2>
            <button
              type="button"
              onClick={onNewChat}
              className="rounded-md bg-ink px-2 py-1 text-xs font-medium text-white"
            >
              New
            </button>
          </div>
          <ul className="max-h-[calc(100vh-240px)] space-y-1 overflow-y-auto">
            {conversations.length === 0 && (
              <li className="px-2 py-3 text-xs text-slate-500">No chats yet.</li>
            )}
            {conversations.map((c) => (
              <li key={c.id}>
                <div
                  className={`flex items-center gap-1 rounded-lg px-2 py-2 text-sm ${
                    activeConversationId === c.id
                      ? "bg-teal-50 text-teal-900"
                      : "hover:bg-slate-50"
                  }`}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 truncate text-left"
                    onClick={() => onSelectConversation(c.id)}
                  >
                    {c.title}
                  </button>
                  <button
                    type="button"
                    className="text-xs text-red-600"
                    onClick={() => onDeleteConversation(c.id)}
                    aria-label="Delete conversation"
                  >
                    ×
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </aside>

        <section className="min-h-0 flex flex-col rounded-2xl border border-slate-200 bg-white/80">
          <div className="flex flex-wrap items-end gap-3 border-b border-slate-200 p-3">
            <label className="text-xs text-slate-600">
              Model
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="mt-1 block rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
              >
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-600">
              Agent (system prompt)
              <select
                value={agentId}
                onChange={(e) =>
                  setAgentId(e.target.value ? Number(e.target.value) : "")
                }
                className="mt-1 block max-w-[220px] rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
              >
                <option value="">Default mentor prompt</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-600">
              Temperature ({temperature.toFixed(1)})
              <input
                type="range"
                min={0}
                max={1.5}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
                className="mt-2 block w-40"
              />
            </label>
            <label className="inline-flex items-center gap-2 rounded-lg border-2 border-teal-500 bg-teal-50 px-3 py-2 text-sm font-semibold text-teal-900">
              <input
                type="checkbox"
                checked={enableTools}
                onChange={(e) => setEnableTools(e.target.checked)}
                className="h-4 w-4"
              />
              Enable tools {enableTools ? "(ON)" : "(OFF)"}
            </label>
          </div>

          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
            {messages.length === 0 && (
              <p className="text-center text-sm text-slate-500">
                Try: &quot;What is 24 * 18?&quot; or &quot;Weather in Chennai&quot; or
                &quot;Search for JWT&quot;
              </p>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
                  m.role === "user"
                    ? "ml-auto bg-ink text-white"
                    : "bg-slate-100 text-slate-800"
                }`}
              >
                <p className="mb-1 text-[10px] font-semibold tracking-wide uppercase opacity-70">
                  {m.role}
                </p>
                {m.role === "assistant" && m.graphSteps && m.graphSteps.length > 0 && (
                  <GraphExecutionPanel steps={m.graphSteps} />
                )}
                {m.role === "assistant" && m.tools && m.tools.length > 0 && (
                  <ToolPanel tools={m.tools} />
                )}
                {m.content || (sending ? "…" : "")}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={onSend} className="border-t border-slate-200 p-3">
            <div className="flex gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={2}
                placeholder="Ask something that needs a tool…"
                className="min-h-[48px] flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none ring-accent focus:ring-2"
                disabled={sending}
              />
              <button
                type="submit"
                disabled={sending || !input.trim()}
                className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
              >
                {sending ? "…" : "Send"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}

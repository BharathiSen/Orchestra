"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
  type MemoryStatus,
  type OrchestraAgentName,
  type OrchestraStepEvent,
  type Project,
  type RetrievedChunk,
  type ToolEvent,
  type ToolInfo,
  type UserMemoryItem,
} from "@/lib/api";
import { clearSession, getToken } from "@/lib/auth";

type UiMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  retrievedChunks?: RetrievedChunk[];
  tools?: ToolEvent[];
  graphSteps?: GraphStepEvent[];
  orchestraSteps?: OrchestraStepEvent[];
};

type StarterPrompt = {
  label: string;
  prompt: string;
  detail: string;
  /** Which pipeline the prompt is designed to exercise. */
  requires: "orchestra" | "tools" | "any";
};

// Each prompt is chosen to land on a specific path: "compare" matches the full
// route in orchestrator/routing.py, and "847 * 23" matches both the simple
// route and the tool gate in graph/nodes.py.
const STARTER_PROMPTS: StarterPrompt[] = [
  {
    label: "Multi-agent research",
    prompt: "Compare Redis and Postgres for session storage.",
    detail: "Runs the full pipeline — Planner, Research, Writer, Reviewer.",
    requires: "orchestra",
  },
  {
    label: "Tool calling",
    prompt: "What is 847 * 23?",
    detail: "Routes to the calculator tool and shows the call in the trace.",
    requires: "tools",
  },
  {
    label: "Long-term memory",
    prompt: "My favorite language is TypeScript.",
    detail: "Stores a durable fact. Ask what you know about me in a new chat.",
    requires: "any",
  },
];

/** Returns the toggle change needed to run a prompt, or null if it is ready. */
function starterBlockedBy(
  requires: StarterPrompt["requires"],
  enableOrchestra: boolean,
  enableTools: boolean,
): string | null {
  if (requires === "orchestra" && !enableOrchestra) {
    return "Turn Orchestra on";
  }
  if (requires === "tools") {
    if (enableOrchestra) return "Turn Orchestra off";
    if (!enableTools) return "Turn tools on";
  }
  return null;
}

/**
 * Assistant output is Markdown — models emit `**bold**`, lists, tables, and
 * fenced code. Rendering it into `whitespace-pre-wrap` showed the raw syntax.
 *
 * User messages are deliberately NOT parsed as Markdown: what someone typed
 * should appear exactly as typed, so they keep plain text with preserved
 * whitespace.
 */
function MessageBody({ role, content }: { role: string; content: string }) {
  if (role !== "assistant") {
    return <span className="whitespace-pre-wrap">{content}</span>;
  }

  return (
    <div className="markdown-body text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-ink">{children}</strong>
          ),
          ul: ({ children }) => (
            <ul className="mb-2 ml-5 list-disc space-y-1 last:mb-0">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-2 ml-5 list-decimal space-y-1 last:mb-0">{children}</ol>
          ),
          h1: ({ children }) => (
            <h1 className="mt-3 mb-2 font-display text-base font-semibold first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-3 mb-2 font-display text-base font-semibold first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-3 mb-1 font-display text-sm font-semibold first:mt-0">
              {children}
            </h3>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="text-accent underline underline-offset-2"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-slate-300 pl-3 text-slate-600">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-3 border-slate-300" />,
          // Wide tables and long code lines scroll inside the bubble rather
          // than stretching it past the column.
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-slate-300 bg-slate-200/60 px-2 py-1 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-slate-300 px-2 py-1 align-top">{children}</td>
          ),
          pre: ({ children }) => (
            <pre className="my-2 overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
              {children}
            </pre>
          ),
          code: ({ className, children, ...props }) => {
            // react-markdown renders inline code without a language class and
            // fenced blocks with one; only the inline case needs a chip style.
            const isBlock = Boolean(className);
            if (isBlock) {
              return (
                <code className={`${className ?? ""} font-mono`} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code className="rounded bg-slate-200 px-1 py-0.5 font-mono text-[0.85em] text-ink">
                {children}
              </code>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function ChatEmptyState({
  enableOrchestra,
  enableTools,
  onSelect,
}: {
  enableOrchestra: boolean;
  enableTools: boolean;
  onSelect: (prompt: string) => void;
}) {
  return (
    <div className="mx-auto max-w-2xl py-10">
      <h2 className="text-center font-display text-lg font-semibold text-slate-800">
        Start a traced conversation
      </h2>
      <p className="mt-1.5 text-center text-sm text-slate-500">
        Every turn records its steps, tokens, cost, and latency. Pick a prompt to
        see a pipeline run end to end.
      </p>
      <ul className="mt-6 space-y-2">
        {STARTER_PROMPTS.map((starter) => {
          const blockedBy = starterBlockedBy(
            starter.requires,
            enableOrchestra,
            enableTools,
          );
          return (
            <li key={starter.label}>
              <button
                type="button"
                onClick={() => onSelect(starter.prompt)}
                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-accent hover:shadow-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-semibold tracking-wide text-accent uppercase">
                    {starter.label}
                  </span>
                  {blockedBy && (
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800">
                      {blockedBy}
                    </span>
                  )}
                </div>
                <p className="mt-1.5 text-sm font-medium text-slate-800">
                  {starter.prompt}
                </p>
                <p className="mt-1 text-xs text-slate-500">{starter.detail}</p>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

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

function OrchestraExecutionPanel({ steps }: { steps: OrchestraStepEvent[] }) {
  if (!steps.length) return null;
  const labels: Record<OrchestraAgentName, string> = {
    planner: "Planner",
    research: "Research",
    writer: "Writer",
    reviewer: "Reviewer",
    fast_answer: "Fast Answer",
  };
  const route = steps.find((s) => s.route)?.route;
  const ordered: OrchestraAgentName[] =
    route === "simple"
      ? ["planner", "research", "fast_answer"]
      : ["planner", "research", "writer", "reviewer"];
  const latest = new Map<OrchestraAgentName, OrchestraStepEvent>();
  for (const step of steps) {
    latest.set(step.agent, step);
  }

  return (
    <div className="mb-2 rounded-lg border border-indigo-200 bg-indigo-50/50 px-3 py-2 text-xs text-slate-700">
      <p className="mb-1.5 font-semibold text-indigo-950">
        Agent Execution{route ? ` · ${route}` : ""}
      </p>
      <div className="space-y-1.5">
        {ordered.map((agent, idx) => {
          const step = latest.get(agent);
          const status = step?.status;
          const statusText =
            status === "running"
              ? "Running…"
              : status === "done"
                ? "✓"
                : status === "error"
                  ? "Error"
                  : "Pending";
          const statusClass =
            status === "running"
              ? "text-amber-700"
              : status === "done"
                ? "text-teal-700"
                : status === "error"
                  ? "text-red-700"
                  : "text-slate-400";
          return (
            <div key={agent}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{labels[agent]}</span>
                <span className={statusClass}>{statusText}</span>
              </div>
              {step?.summary && (
                <p className="mt-0.5 text-[11px] text-slate-500">{step.summary}</p>
              )}
              {idx < ordered.length - 1 && (
                <p className="text-[10px] text-slate-400">↓</p>
              )}
            </div>
          );
        })}
        {(latest.get("reviewer")?.status === "done" ||
          latest.get("fast_answer")?.status === "done") && (
          <p className="pt-1 font-semibold text-teal-800">↓ Done</p>
        )}
      </div>
    </div>
  );
}

function MemoryPanel({
  status,
  preferences,
  onSavePreference,
  prefDraft,
  setPrefDraft,
  savingPref,
}: {
  status: MemoryStatus | null;
  preferences: UserMemoryItem[];
  onSavePreference: () => void;
  prefDraft: { key: string; value: string };
  setPrefDraft: (v: { key: string; value: string }) => void;
  savingPref: boolean;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs text-slate-700">
      <p className="mb-2 font-semibold text-slate-800">Memory Panel</p>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        <span className="text-slate-500">Conversation</span>
        <span className="font-medium">
          Memory Size {status?.memory_size ?? 0} / {status?.buffer_limit ?? 10}
        </span>
        <span className="text-slate-500">Session</span>
        <span className="font-medium">
          {status?.session_active ? "Active" : "Idle"}
        </span>
        <span className="text-slate-500">Redis</span>
        <span
          className={
            status?.redis_connected
              ? "font-medium text-teal-700"
              : "font-medium text-amber-700"
          }
        >
          {status?.redis_connected ? "Connected" : "Offline"}
        </span>
        <span className="text-slate-500">Memory Used</span>
        <span className="font-medium">{status?.memory_used ? "✓ Yes" : "No"}</span>
        <span className="text-slate-500">Summary</span>
        <span className="font-medium">
          {status?.has_summary ? "✓ Compressed" : "—"}
        </span>
        <span className="text-slate-500">Long-term</span>
        <span className="font-medium">{status?.long_term_count ?? 0} facts</span>
      </div>

      {preferences.length > 0 && (
        <ul className="mt-2 space-y-1 border-t border-slate-100 pt-2">
          {preferences.slice(0, 5).map((p) => (
            <li key={p.id} className="truncate text-[11px] text-slate-600">
              <span className="font-medium text-slate-700">{p.key}</span>: {p.value}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-2 space-y-1.5 border-t border-slate-100 pt-2">
        <p className="font-medium text-slate-700">Add preference</p>
        <input
          value={prefDraft.key}
          onChange={(e) => setPrefDraft({ ...prefDraft, key: e.target.value })}
          placeholder="e.g. preferred_language"
          className="w-full rounded-md border border-slate-300 px-2 py-1 text-[11px]"
        />
        <input
          value={prefDraft.value}
          onChange={(e) => setPrefDraft({ ...prefDraft, value: e.target.value })}
          placeholder="e.g. Python"
          className="w-full rounded-md border border-slate-300 px-2 py-1 text-[11px]"
        />
        <button
          type="button"
          disabled={savingPref || !prefDraft.key.trim() || !prefDraft.value.trim()}
          onClick={onSavePreference}
          className="rounded-md bg-ink px-2 py-1 text-[11px] font-medium text-white disabled:opacity-50"
        >
          {savingPref ? "Saving…" : "Save to long-term memory"}
        </button>
      </div>
    </div>
  );
}

function RetrievedContextPanel({ chunks }: { chunks: RetrievedChunk[] }) {
  if (!chunks.length) return null;
  return (
    <div className="mb-2 rounded-lg border border-emerald-200 bg-emerald-50/60 px-3 py-2 text-xs text-slate-700">
      <p className="mb-1.5 font-semibold text-emerald-900">
        Retrieved Sources ({chunks.length})
      </p>
      <div className="space-y-1.5">
        {chunks.map((chunk) => (
          <div key={chunk.chunk_id} className="rounded-md border border-emerald-100 bg-white px-2 py-1.5">
            <p className="font-medium text-slate-800">
              ✓ Chunk {chunk.chunk_index} · {chunk.document_name}
              {typeof chunk.score === "number" && (
                <span className="ml-1.5 font-normal text-slate-500">
                  ({chunk.score.toFixed(3)})
                </span>
              )}
            </p>
            <p className="mt-0.5 line-clamp-2 text-[11px] text-slate-600">
              {chunk.content}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

type ConversationExtras = {
  retrievedChunks: RetrievedChunk[];
  tools: ToolEvent[];
  graphSteps: GraphStepEvent[];
  orchestraSteps: OrchestraStepEvent[];
};

function attachExtrasToMessages(
  rows: ChatMessage[],
  extras: ConversationExtras | undefined,
): UiMessage[] {
  const filtered = rows.filter((m) => m.role === "user" || m.role === "assistant");
  const lastAssistantIdx = filtered.map((x) => x.role).lastIndexOf("assistant");
  return filtered.map((m, idx) => {
    const isLastAssistant = m.role === "assistant" && idx === lastAssistantIdx;
    const persisted = m.trace || null;
    const retrieved =
      (isLastAssistant && extras?.retrievedChunks?.length
        ? extras.retrievedChunks
        : undefined) ||
      persisted?.retrieved_chunks ||
      undefined;
    const tools =
      (isLastAssistant && extras?.tools?.length ? extras.tools : undefined) ||
      persisted?.tools ||
      undefined;
    const graphSteps =
      (isLastAssistant && extras?.graphSteps?.length
        ? extras.graphSteps
        : undefined) ||
      persisted?.graph_steps ||
      undefined;
    const orchestraSteps =
      (isLastAssistant && extras?.orchestraSteps?.length
        ? extras.orchestraSteps
        : undefined) ||
      persisted?.orchestra_steps ||
      undefined;
    return {
      id: String(m.id),
      role: m.role as "user" | "assistant",
      content: m.content,
      retrievedChunks: retrieved?.length ? retrieved : undefined,
      tools: tools?.length ? tools : undefined,
      graphSteps: graphSteps?.length ? graphSteps : undefined,
      orchestraSteps: orchestraSteps?.length ? orchestraSteps : undefined,
    };
  });
}

export default function ProjectChatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
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
  const [enableTools, setEnableTools] = useState(false);
  const [enableOrchestra, setEnableOrchestra] = useState(true);
  const [memoryStatus, setMemoryStatus] = useState<MemoryStatus | null>(null);
  const [preferences, setPreferences] = useState<UserMemoryItem[]>([]);
  const [prefDraft, setPrefDraft] = useState({ key: "", value: "" });
  const [savingPref, setSavingPref] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replayBanner, setReplayBanner] = useState(false);
  // Conversation list is a slide-over drawer below `lg` so the chat itself is
  // always the primary view on a phone. At `lg` and above the same markup is a
  // static grid column and this flag is ignored.
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const replayAppliedRef = useRef(false);
  // Message history API does not persist RAG/tool/graph UI extras.
  // Keep them in-session so the post-stream reload does not wipe the panel.
  const conversationExtrasRef = useRef<Record<number, ConversationExtras>>({});
  const pendingRetrievedRef = useRef<RetrievedChunk[]>([]);

  const selectedAgent = agents.find((a) => a.id === agentId);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const saveConversationExtras = useCallback(
    (conversationId: number, patch: Partial<ConversationExtras>) => {
      const prev = conversationExtrasRef.current[conversationId] || {
        retrievedChunks: [],
        tools: [],
        graphSteps: [],
        orchestraSteps: [],
      };
      conversationExtrasRef.current[conversationId] = {
        retrievedChunks: patch.retrievedChunks ?? prev.retrievedChunks,
        tools: patch.tools ?? prev.tools,
        graphSteps: patch.graphSteps ?? prev.graphSteps,
        orchestraSteps: patch.orchestraSteps ?? prev.orchestraSteps,
      };
    },
    [],
  );

  const refreshMemory = useCallback(
    async (authToken: string, conversationId?: number | null) => {
      try {
        const [status, prefs] = await Promise.all([
          api.getMemoryStatus(authToken, conversationId),
          api.listPreferences(authToken),
        ]);
        setMemoryStatus(status);
        setPreferences(prefs.items || []);
      } catch {
        // Memory panel is best-effort
      }
    },
    [],
  );

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
        attachExtrasToMessages(rows, conversationExtrasRef.current[conversationId]),
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
    // Don't reload mid-stream: onMeta sets conversation id before tokens arrive,
    // and a reload would wipe the optimistic assistant bubble.
    if (sending) return;
    if (!token || !activeConversationId) {
      setMessages([]);
      if (token) {
        refreshMemory(token, null).catch(() => undefined);
      }
      return;
    }
    loadConversationMessages(token, activeConversationId).catch((err) => {
      setError(err instanceof ApiError ? err.message : "Failed to load messages");
    });
    refreshMemory(token, activeConversationId).catch(() => undefined);
  }, [
    token,
    activeConversationId,
    loadConversationMessages,
    refreshMemory,
    sending,
  ]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  // Apply replay query params exactly once: an execution opened from
  // Observability arrives with its prompt and pipeline flags in the URL.
  useEffect(() => {
    if (loading || replayAppliedRef.current) return;
    if (searchParams.get("replay") !== "1") return;
    replayAppliedRef.current = true;
    const message = searchParams.get("message");
    if (message) setInput(message);
    const replayModel = searchParams.get("model");
    if (replayModel) setModel(replayModel);
    const conv = searchParams.get("conversation_id");
    if (conv && Number.isFinite(Number(conv))) {
      setActiveConversationId(Number(conv));
    }
    const agent = searchParams.get("agent_id");
    if (agent && Number.isFinite(Number(agent))) {
      setAgentId(Number(agent));
    }
    if (searchParams.get("orchestra") === "1") {
      setEnableOrchestra(true);
      setEnableTools(false);
    } else if (searchParams.get("tools") === "1") {
      setEnableOrchestra(false);
      setEnableTools(true);
    }
    setReplayBanner(true);
  }, [loading, searchParams]);

  async function onSavePreference() {
    if (!token || !prefDraft.key.trim() || !prefDraft.value.trim()) return;
    setSavingPref(true);
    try {
      await api.upsertPreference(token, {
        category: "preference",
        key: prefDraft.key.trim(),
        value: prefDraft.value.trim(),
      });
      setPrefDraft({ key: "", value: "" });
      await refreshMemory(token, activeConversationId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save preference");
    } finally {
      setSavingPref(false);
    }
  }
  async function onNewChat() {
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
    pendingRetrievedRef.current = [];
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
    let streamConversationId: number | null = activeConversationId;
    setMessages((prev) => [
      ...prev,
      optimisticUser,
      { id: assistantId, role: "assistant", content: "…", tools: [] },
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
          enable_tools: enableOrchestra ? false : enableTools,
          enable_orchestra: enableOrchestra,
        },
        {
          onMeta: ({ conversation_id }) => {
            streamConversationId = conversation_id;
            setActiveConversationId(conversation_id);
            if (pendingRetrievedRef.current.length) {
              saveConversationExtras(conversation_id, {
                retrievedChunks: pendingRetrievedRef.current,
              });
            }
          },
          onMemoryStatus: (status) => {
            setMemoryStatus(status);
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
          onRetrievedContext: ({ chunks }) => {
            pendingRetrievedRef.current = chunks;
            if (streamConversationId) {
              saveConversationExtras(streamConversationId, {
                retrievedChunks: chunks,
              });
            }
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      retrievedChunks: chunks,
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
                          (s) =>
                            !(
                              s.node === step.node &&
                              s.status === step.status &&
                              s.summary === step.summary
                            ),
                        ),
                        step,
                      ],
                    }
                  : m,
              ),
            );
          },
          onOrchestraStep: (step) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      orchestraSteps: [
                        ...(m.orchestraSteps || []).filter(
                          (s) =>
                            !(
                              s.agent === step.agent &&
                              s.status === step.status &&
                              s.summary === step.summary
                            ),
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
                  ? {
                      ...m,
                      content:
                        m.content === "…" ? tokenText : m.content + tokenText,
                    }
                  : m,
              ),
            );
          },
          onError: (detail) => {
            setError(detail);
          },
          onDone: async () => {
            await refreshConversations(token);
            if (streamConversationId) {
              await refreshMemory(token, streamConversationId);
            }
          },
        },
      );

      const list = await refreshConversations(token);
      const currentId =
        streamConversationId ??
        list.find((c) => c.title.includes(userText.slice(0, 20)))?.id ??
        list[0]?.id ??
        null;
      if (currentId) {
        setActiveConversationId(currentId);
        // Keep live tool/RAG/graph cards for this turn; reload canonical messages after stream.
        const rows = await api.listMessages(token, currentId);
        let extras: ConversationExtras = {
          retrievedChunks: pendingRetrievedRef.current,
          tools: [],
          graphSteps: [],
          orchestraSteps: [],
        };
        setMessages((prev) => {
          const live = prev.find((m) => m.id === assistantId);
          extras = {
            retrievedChunks:
              live?.retrievedChunks?.length
                ? live.retrievedChunks
                : pendingRetrievedRef.current,
            tools: live?.tools || [],
            graphSteps: live?.graphSteps || [],
            orchestraSteps: live?.orchestraSteps || [],
          };
          return attachExtrasToMessages(rows, extras);
        });
        saveConversationExtras(currentId, extras);
        pendingRetrievedRef.current = [];
        await refreshMemory(token, currentId);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Chat failed");
      if (streamConversationId) {
        try {
          const rows = await api.listMessages(token, streamConversationId);
          setMessages(
            rows
              .filter((m) => m.role === "user" || m.role === "assistant")
              .map((m: ChatMessage) => ({
                id: String(m.id),
                role: m.role as "user" | "assistant",
                content: m.content,
              })),
          );
        } catch {
          setMessages((prev) => prev.filter((m) => m.id !== assistantId));
        }
      } else {
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      }
    } finally {
      setSending(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-dvh w-full max-w-[1400px] flex-col gap-4 px-4 py-6 md:px-6 lg:px-8">
        <div className="h-9 w-48 animate-pulse rounded-lg bg-slate-200" />
        <div className="h-4 w-72 animate-pulse rounded bg-slate-200" />
        <div className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
          <div className="hidden animate-pulse rounded-2xl border border-slate-200 bg-slate-100/70 lg:block" />
          <div className="flex min-h-0 flex-col gap-3 rounded-2xl border border-slate-200 bg-white/80 p-4">
            <div className="h-10 w-full animate-pulse rounded-lg bg-slate-200" />
            <div className="h-16 w-3/4 animate-pulse rounded-2xl bg-slate-200" />
            <div className="ml-auto h-12 w-1/2 animate-pulse rounded-2xl bg-slate-200" />
            <div className="h-20 w-2/3 animate-pulse rounded-2xl bg-slate-200" />
          </div>
        </div>
        <span className="sr-only">Loading chat…</span>
      </main>
    );
  }

  if (!project) return null;

  return (
    <main className="mx-auto flex h-dvh w-full max-w-[1400px] flex-col overflow-hidden px-3 py-4 sm:px-4 md:px-6 md:py-6 lg:px-8">
      <header className="mb-3 flex flex-wrap items-start justify-between gap-3 md:mb-4">
        <div className="min-w-0">
          <p className="font-display text-xs font-semibold tracking-[0.2em] text-accent uppercase sm:text-sm">
            Orchestra
          </p>
          <h1 className="mt-1 truncate font-display text-xl font-bold sm:text-2xl md:text-3xl">
            Chat · {project.name}
          </h1>
          <p className="mt-1 hidden text-sm text-slate-600 sm:block">
            Multi-agent Orchestra with Redis conversation memory and long-term
            preferences.
          </p>
        </div>
        <nav className="flex flex-wrap gap-2" aria-label="Project sections">
          <Link
            href={`/projects/${projectId}`}
            className="touch-row inline-flex items-center rounded-lg border border-slate-300 px-3 text-sm font-medium hover:bg-white"
          >
            Agents
          </Link>
          <Link
            href={`/projects/${projectId}/knowledge`}
            className="touch-row inline-flex items-center rounded-lg border border-slate-300 px-3 text-sm font-medium hover:bg-white"
          >
            <span className="sm:hidden">Knowledge</span>
            <span className="hidden sm:inline">Knowledge Base</span>
          </Link>
          <Link
            href={`/projects/${projectId}/observability`}
            className="touch-row inline-flex items-center rounded-lg border border-slate-300 px-3 text-sm font-medium hover:bg-white"
          >
            Observability
          </Link>
          <Link
            href="/dashboard"
            className="touch-row inline-flex items-center rounded-lg border border-slate-300 px-3 text-sm font-medium hover:bg-white"
          >
            Dashboard
          </Link>
        </nav>
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
        {/* Backdrop for the drawer. Only below `lg`, where the aside is fixed. */}
        {sidebarOpen && (
          <button
            type="button"
            aria-label="Close conversations"
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden"
          />
        )}

        <aside
          id="conversation-drawer"
          aria-label="Conversations"
          className={`min-h-0 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-3 transition-transform duration-200 ease-out
            max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:z-40 max-lg:w-[86%] max-lg:max-w-[330px] max-lg:rounded-none max-lg:shadow-xl
            ${sidebarOpen ? "max-lg:translate-x-0" : "max-lg:-translate-x-full"}
            lg:bg-white/80`}
        >
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-700">Conversations</h2>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={onNewChat}
                className="touch-row inline-flex items-center rounded-md bg-ink px-3 text-xs font-medium text-white"
              >
                New
              </button>
              <button
                type="button"
                onClick={() => setSidebarOpen(false)}
                aria-label="Close conversations"
                className="touch-target inline-flex items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 lg:hidden"
              >
                <span aria-hidden className="text-xl leading-none">×</span>
              </button>
            </div>
          </div>
          <ul className="mb-3 space-y-1 lg:max-h-[40vh] lg:overflow-y-auto">
            {conversations.length === 0 && (
              <li className="rounded-lg border border-dashed border-slate-300 px-3 py-6 text-center text-xs text-slate-500">
                No conversations yet.
                <br />
                Send a message to start one.
              </li>
            )}
            {conversations.map((c) => (
              <li key={c.id}>
                <div
                  className={`flex items-center gap-1 rounded-lg px-2 text-sm ${
                    activeConversationId === c.id
                      ? "bg-teal-50 text-teal-900"
                      : "hover:bg-slate-50"
                  }`}
                >
                  <button
                    type="button"
                    className="touch-row min-w-0 flex-1 truncate text-left"
                    onClick={() => {
                      onSelectConversation(c.id);
                      setSidebarOpen(false);
                    }}
                  >
                    {c.title}
                  </button>
                  <button
                    type="button"
                    className="touch-target inline-flex shrink-0 items-center justify-center rounded-md text-red-600 hover:bg-red-50"
                    onClick={() => onDeleteConversation(c.id)}
                    aria-label={`Delete conversation ${c.title}`}
                  >
                    <span aria-hidden className="text-lg leading-none">×</span>
                  </button>
                </div>
              </li>
            ))}
          </ul>

          <MemoryPanel
            status={memoryStatus}
            preferences={preferences}
            onSavePreference={onSavePreference}
            prefDraft={prefDraft}
            setPrefDraft={setPrefDraft}
            savingPref={savingPref}
          />
        </aside>

        <section className="flex min-h-0 flex-col rounded-2xl border border-slate-200 bg-white/80">
          <div className="flex flex-wrap items-end gap-2 border-b border-slate-200 p-3 sm:gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              aria-expanded={sidebarOpen}
              aria-controls="conversation-drawer"
              className="touch-row inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm font-medium hover:bg-white lg:hidden"
            >
              <span aria-hidden className="text-base leading-none">☰</span>
              Chats
            </button>
            <label className="text-xs text-slate-600">
              Model
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="touch-row mt-1 block rounded-lg border border-slate-300 px-2 text-sm"
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
                className="touch-row mt-1 block max-w-[220px] rounded-lg border border-slate-300 px-2 text-sm"
              >
                <option value="">Default mentor prompt</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                    {a.knowledge_base_ids && a.knowledge_base_ids.length > 0
                      ? " · KB"
                      : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="touch-row flex flex-col justify-center text-xs text-slate-600">
              Temperature ({temperature.toFixed(1)})
              <input
                type="range"
                min={0}
                max={1.5}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
                aria-label={`Temperature ${temperature.toFixed(1)}`}
                className="mt-2 block h-6 w-40 cursor-pointer"
              />
            </label>
            <label className="touch-row inline-flex items-center gap-2 rounded-lg border-2 border-indigo-500 bg-indigo-50 px-3 text-sm font-semibold text-indigo-950">
              <input
                type="checkbox"
                checked={enableOrchestra}
                onChange={(e) => {
                  const on = e.target.checked;
                  setEnableOrchestra(on);
                  if (on) setEnableTools(false);
                }}
                className="h-5 w-5"
              />
              Orchestra {enableOrchestra ? "(ON)" : "(OFF)"}
            </label>
            <label
              className={`touch-row inline-flex items-center gap-2 rounded-lg border-2 px-3 text-sm font-semibold ${
                enableOrchestra
                  ? "border-slate-200 bg-slate-50 text-slate-400"
                  : "border-teal-500 bg-teal-50 text-teal-900"
              }`}
            >
              <input
                type="checkbox"
                checked={enableTools}
                disabled={enableOrchestra}
                onChange={(e) => setEnableTools(e.target.checked)}
                className="h-5 w-5"
              />
              Tools {enableTools ? "(ON)" : "(OFF)"}
            </label>
          </div>

          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
            {messages.length === 0 && (
              <ChatEmptyState
                enableOrchestra={enableOrchestra}
                enableTools={enableTools}
                onSelect={setInput}
              />
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                  m.role === "user"
                    ? "ml-auto bg-ink text-white"
                    : "bg-slate-100 text-slate-800"
                }`}
              >
                <p className="mb-1 text-[10px] font-semibold tracking-wide uppercase opacity-70">
                  {m.role}
                </p>
                {m.role === "assistant" &&
                  m.orchestraSteps &&
                  m.orchestraSteps.length > 0 && (
                    <OrchestraExecutionPanel steps={m.orchestraSteps} />
                  )}
                {m.role === "assistant" && m.retrievedChunks && m.retrievedChunks.length > 0 && (
                  <RetrievedContextPanel chunks={m.retrievedChunks} />
                )}
                {m.role === "assistant" && m.graphSteps && m.graphSteps.length > 0 && (
                  <GraphExecutionPanel steps={m.graphSteps} />
                )}
                {m.role === "assistant" && m.tools && m.tools.length > 0 && (
                  <ToolPanel tools={m.tools} />
                )}
                {m.content ? (
                  <MessageBody role={m.role} content={m.content} />
                ) : sending ? (
                  <span className="text-slate-400" aria-label="Assistant is responding">
                    …
                  </span>
                ) : null}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* sticky + pb-safe keeps the composer above the iOS home indicator
              and the Android gesture bar; the parent is h-dvh so it never sits
              under a collapsing browser chrome. */}
          <form
            onSubmit={onSend}
            className="pb-safe sticky bottom-0 z-10 border-t border-slate-200 bg-white/95 px-3 pt-3 backdrop-blur"
          >
            {replayBanner && (
              <p className="mb-2 rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs text-teal-900">
                Replay loaded — same prompt and pipeline flags are ready. Press
                Send to re-run, then compare in Observability.
              </p>
            )}
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={2}
                placeholder={
                  enableOrchestra
                    ? "Ask something that needs multiple agents…"
                    : enableTools
                      ? "Ask something that needs a tool…"
                      : "Ask anything…"
                }
                aria-label="Message"
                className="min-h-[48px] flex-1 rounded-xl border border-slate-300 px-3 py-2 text-base outline-none ring-accent focus:ring-2 sm:text-sm"
                disabled={sending}
              />
              <button
                type="submit"
                disabled={sending || !input.trim()}
                className="touch-target inline-flex items-center justify-center rounded-xl bg-accent px-5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
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

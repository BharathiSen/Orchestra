"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { ChatControls } from "@/components/chat/ChatControls";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { Composer } from "@/components/chat/Composer";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { MemoryPanel, type PreferenceDraft } from "@/components/chat/MemoryPanel";
import { MessageList } from "@/components/chat/MessageList";
import {
  PENDING_CONTENT,
  patchMessage,
  withGraphStep,
  withOrchestraStep,
  withRetrievedChunks,
  withToken,
  withToolResult,
  withToolStarted,
} from "@/components/chat/messageUpdates";
import {
  EMPTY_EXTRAS,
  attachExtrasToMessages,
  type ConversationExtras,
  type UiMessage,
} from "@/components/chat/types";
import {
  ApiError,
  api,
  streamChat,
  type Agent,
  type ChatModel,
  type Conversation,
  type MemoryStatus,
  type Project,
  type RetrievedChunk,
  type ToolInfo,
  type UserMemoryItem,
} from "@/lib/api";
import { clearSession, useSession } from "@/lib/auth";

export default function ProjectChatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  const { ready, token } = useSession();
  const [project, setProject] = useState<Project | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [models, setModels] = useState<ChatModel[]>([]);
  const [toolsCatalog, setToolsCatalog] = useState<ToolInfo[]>([]);
  const [llmConfigured, setLlmConfigured] = useState(true);
  const [provider, setProvider] = useState("groq");
  const [model, setModel] = useState("openai/gpt-oss-20b");
  const [agentId, setAgentId] = useState<number | "">("");
  const [temperature, setTemperature] = useState(0.2);
  const [enableTools, setEnableTools] = useState(false);
  const [enableOrchestra, setEnableOrchestra] = useState(true);
  const [memoryStatus, setMemoryStatus] = useState<MemoryStatus | null>(null);
  const [preferences, setPreferences] = useState<UserMemoryItem[]>([]);
  const [prefDraft, setPrefDraft] = useState<PreferenceDraft>({ key: "", value: "" });
  const [savingPref, setSavingPref] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replayBanner, setReplayBanner] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const replayAppliedRef = useRef(false);
  // Message history API does not persist RAG/tool/graph UI extras.
  // Keep them in-session so the post-stream reload does not wipe the panel.
  const conversationExtrasRef = useRef<Record<number, ConversationExtras>>({});
  const pendingRetrievedRef = useRef<RetrievedChunk[]>([]);

  const selectedAgent = agents.find((a) => a.id === agentId);

  const saveConversationExtras = useCallback(
    (conversationId: number, patch: Partial<ConversationExtras>) => {
      const prev = conversationExtrasRef.current[conversationId] || EMPTY_EXTRAS;
      conversationExtrasRef.current[conversationId] = {
        retrievedChunks: patch.retrievedChunks ?? prev.retrievedChunks,
        tools: patch.tools ?? prev.tools,
        graphSteps: patch.graphSteps ?? prev.graphSteps,
        orchestraSteps: patch.orchestraSteps ?? prev.orchestraSteps,
      };
    },
    [],
  );

  const fetchMemory = (authToken: string, conversationId?: number | null) =>
    Promise.all([
      api.getMemoryStatus(authToken, conversationId),
      api.listPreferences(authToken),
    ]);

  // For event handlers. Effects use fetchMemory so they can drop late replies.
  const refreshMemory = useCallback(
    async (authToken: string, conversationId?: number | null) => {
      try {
        const [status, prefs] = await fetchMemory(authToken, conversationId);
        setMemoryStatus(status);
        setPreferences(prefs.items || []);
      } catch {
        // Memory panel is best-effort
      }
    },
    [],
  );

  // An agent's configured model is its default: picking the agent moves the
  // model picker to it, and the picker stays free to override for this chat.
  // An ID the provider no longer lists (a retired model) is left alone, since
  // the select cannot show it and would display a model that is not sent.
  function changeAgent(nextAgentId: number | "") {
    setAgentId(nextAgentId);
    const agentModel = agents.find((a) => a.id === nextAgentId)?.model_name;
    if (agentModel && models.some((m) => m.id === agentModel)) {
      setModel(agentModel);
    }
  }

  function applyReplayParams(searchParams: URLSearchParams) {
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
  }

  const refreshConversations = useCallback(
    async (authToken: string) => {
      const list = await api.listConversations(authToken, projectId);
      setConversations(list);
      return list;
    },
    [projectId],
  );

  useEffect(() => {
    if (!Number.isFinite(projectId)) {
      router.replace("/projects");
      return;
    }
    if (!ready) return;
    if (!token) {
      router.replace("/login");
      return;
    }

    let cancelled = false;
    Promise.all([
      api.getProject(token, projectId),
      api.listAgents(token, projectId),
      api.listConversations(token, projectId),
      api.listModels(token),
      api.listTools(token).catch(() => ({ tools: [], count: 0 })),
    ])
      .then(([projectData, agentList, conversationList, modelData, toolsData]) => {
        if (cancelled) return;
        setProject(projectData);
        setAgents(agentList);
        setConversations(conversationList);
        setModels(modelData.models);
        setToolsCatalog(toolsData.tools || []);
        setLlmConfigured(modelData.llm_configured ?? modelData.gemini_configured);
        setProvider(modelData.provider || "groq");
        if (modelData.models.length > 0) {
          setModel(modelData.models[0].id);
        }
        if (conversationList.length > 0) {
          setActiveConversationId(conversationList[0].id);
        }
        // An execution opened from Observability arrives with its prompt and
        // pipeline flags in the URL. Applied once, after the defaults above.
        if (!replayAppliedRef.current && searchParams.get("replay") === "1") {
          replayAppliedRef.current = true;
          applyReplayParams(searchParams);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Failed to load chat");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ready, token, projectId, router, searchParams]);

  useEffect(() => {
    // Don't reload mid-stream: onMeta sets conversation id before tokens arrive,
    // and a reload would wipe the optimistic assistant bubble.
    // (Clearing for "no conversation" happens where that state is entered:
    // New chat, deleting the last conversation, a failed first message.)
    if (sending || !token) return;
    // Ignore replies for a conversation the user has already left, so a slow
    // request cannot overwrite the one now on screen.
    let cancelled = false;
    const conversationId = activeConversationId;
    fetchMemory(token, conversationId)
      .then(([status, prefs]) => {
        if (cancelled) return;
        setMemoryStatus(status);
        setPreferences(prefs.items || []);
      })
      .catch(() => undefined); // Memory panel is best-effort
    if (!conversationId) {
      return () => {
        cancelled = true;
      };
    }
    api
      .listMessages(token, conversationId)
      .then((rows) => {
        if (cancelled) return;
        setMessages(
          attachExtrasToMessages(rows, conversationExtrasRef.current[conversationId]),
        );
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load messages");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, activeConversationId, sending]);

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

  function onNewChat() {
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
    pendingRetrievedRef.current = [];
  }

  function onSelectConversation(id: number) {
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

  function onOrchestraChange(on: boolean) {
    setEnableOrchestra(on);
    if (on) setEnableTools(false);
  }

  async function onSend(event: FormEvent) {
    event.preventDefault();
    if (!token || !input.trim() || sending) return;

    const userText = input.trim();
    setInput("");
    setSending(true);
    setError(null);

    const assistantId = `local-assistant-${Date.now()}`;
    let streamConversationId: number | null = activeConversationId;
    setMessages((prev) => [
      ...prev,
      { id: `local-user-${Date.now()}`, role: "user", content: userText },
      { id: assistantId, role: "assistant", content: PENDING_CONTENT, tools: [] },
    ]);
    const patchAssistant = (patch: Parameters<typeof patchMessage>[2]) =>
      setMessages((prev) => patchMessage(prev, assistantId, patch));

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
          onMemoryStatus: setMemoryStatus,
          onToolStart: (tool) => patchAssistant(withToolStarted(tool)),
          onToolResult: (tool) => patchAssistant(withToolResult(tool)),
          onRetrievedContext: ({ chunks }) => {
            pendingRetrievedRef.current = chunks;
            if (streamConversationId) {
              saveConversationExtras(streamConversationId, { retrievedChunks: chunks });
            }
            patchAssistant(withRetrievedChunks(chunks));
          },
          onGraphStep: (step) => patchAssistant(withGraphStep(step)),
          onOrchestraStep: (step) => patchAssistant(withOrchestraStep(step)),
          onToken: (text) => patchAssistant(withToken(text)),
          onError: setError,
          // Nothing to refresh on `done`: the block below reloads conversations
          // and messages as soon as the stream closes, and the memory panel
          // reloads when `sending` clears. Refreshing here as well made every
          // turn fetch conversations twice and memory three times.
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
          ...EMPTY_EXTRAS,
          retrievedChunks: pendingRetrievedRef.current,
        };
        setMessages((prev) => {
          const live = prev.find((m) => m.id === assistantId);
          extras = {
            retrievedChunks: live?.retrievedChunks?.length
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
        // The memory panel reloads from the effect once `sending` clears.
      }
    } catch (err) {
      // A session that expired while the visitor was typing: send them to sign
      // in, as every other page does, rather than leave "Not authenticated" in
      // a chat that will refuse every further message.
      if (err instanceof ApiError && err.status === 401) {
        clearSession();
        router.replace("/login");
        return;
      }
      setError(err instanceof ApiError ? err.message : "Chat failed");
      const dropBubble = () => setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      if (streamConversationId) {
        try {
          const rows = await api.listMessages(token, streamConversationId);
          setMessages(
            rows
              .filter((m) => m.role === "user" || m.role === "assistant")
              .map((m) => ({
                id: String(m.id),
                role: m.role as "user" | "assistant",
                content: m.content,
              })),
          );
        } catch {
          dropBubble();
        }
      } else {
        // No conversation was created, so nothing was saved: return to the
        // empty new-chat state rather than leave an unsent message on screen.
        setMessages([]);
      }
    } finally {
      setSending(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-dvh w-full max-w-[1400px] flex-col gap-4 px-4 py-6 md:px-6 lg:px-8">
        <div className="h-9 w-48 animate-pulse rounded-lg bg-line" />
        <div className="h-4 w-72 animate-pulse rounded bg-line" />
        <div className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
          <div className="hidden animate-pulse rounded-2xl border border-line bg-raised/70 lg:block" />
          <div className="flex min-h-0 flex-col gap-3 rounded-2xl border border-line bg-surface/80 p-4">
            <div className="h-10 w-full animate-pulse rounded-lg bg-line" />
            <div className="h-16 w-3/4 animate-pulse rounded-2xl bg-line" />
            <div className="ml-auto h-12 w-1/2 animate-pulse rounded-2xl bg-line" />
            <div className="h-20 w-2/3 animate-pulse rounded-2xl bg-line" />
          </div>
        </div>
        <span className="sr-only">Loading chat…</span>
      </main>
    );
  }

  if (!project) return null;

  return (
    <main className="mx-auto flex h-dvh w-full max-w-[1400px] flex-col overflow-hidden px-3 py-4 sm:px-4 md:px-6 md:py-6 lg:px-8">
      <ChatHeader
        projectId={projectId}
        projectName={project.name}
        llmConfigured={llmConfigured}
        provider={provider}
        tools={toolsCatalog}
      />

      {error && (
        <p className="mb-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>
      )}

      <div className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <ConversationSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onNewChat={onNewChat}
          onSelect={onSelectConversation}
          onDelete={onDeleteConversation}
        >
          <MemoryPanel
            status={memoryStatus}
            preferences={preferences}
            onSavePreference={onSavePreference}
            prefDraft={prefDraft}
            setPrefDraft={setPrefDraft}
            savingPref={savingPref}
          />
        </ConversationSidebar>

        <section className="flex min-h-0 flex-col rounded-2xl border border-line bg-surface/80">
          <ChatControls
            models={models}
            model={model}
            onModelChange={setModel}
            agents={agents}
            agentId={agentId}
            onAgentChange={changeAgent}
            temperature={temperature}
            onTemperatureChange={setTemperature}
            enableOrchestra={enableOrchestra}
            onOrchestraChange={onOrchestraChange}
            enableTools={enableTools}
            onToolsChange={setEnableTools}
            sidebarOpen={sidebarOpen}
            onOpenSidebar={() => setSidebarOpen(true)}
          />
          <MessageList
            messages={messages}
            sending={sending}
            enableOrchestra={enableOrchestra}
            enableTools={enableTools}
            onSelectStarter={setInput}
          />
          <Composer
            value={input}
            onChange={setInput}
            onSubmit={onSend}
            sending={sending}
            enableOrchestra={enableOrchestra}
            enableTools={enableTools}
            showReplayBanner={replayBanner}
          />
        </section>
      </div>
    </main>
  );
}

"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { ApiError, api, type Agent, type KnowledgeBase, type Project } from "@/lib/api";
import { clearSession, useSession } from "@/lib/auth";

type DialogMode = "create" | "edit" | "delete" | null;

const emptyForm = {
  name: "",
  description: "",
  system_prompt: "",
  model_name: "openai/gpt-oss-20b",
  knowledge_base_ids: [] as number[],
};

/**
 * What this agent can actually do, at a glance.
 *
 * Knowledge Base is per-agent configuration, so it reflects real state and is
 * muted when nothing is attached. Tools, Memory, and Multi-Agent are platform
 * capabilities every agent can use — Memory is always on, and the other two are
 * switched per conversation from the chat header. They are shown as available
 * rather than claimed as configured, so the badges stay truthful.
 */
function AgentCapabilities({ hasKnowledgeBase }: { hasKnowledgeBase: boolean }) {
  const capabilities = [
    {
      label: "Knowledge Base",
      active: hasKnowledgeBase,
      title: hasKnowledgeBase
        ? "Retrieves from attached documents on every turn"
        : "No knowledge base attached — answers are ungrounded",
    },
    {
      label: "Memory",
      active: true,
      title: "Redis conversation buffer plus durable facts across sessions",
    },
    {
      label: "Tools",
      active: true,
      title: "Calculator, weather, and reference search — enable in chat",
    },
    {
      label: "Multi-Agent",
      active: true,
      title: "Planner, Research, Writer, Reviewer — enable Orchestra in chat",
    },
  ];

  return (
    <ul className="mt-3 flex flex-wrap gap-1.5">
      {capabilities.map((c) => (
        <li
          key={c.label}
          title={c.title}
          className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium ${
            c.active
              ? "border-accent/30 bg-accent/10 text-accent"
              : "border-line bg-raised text-fg-faint"
          }`}
        >
          <span aria-hidden>{c.active ? "✓" : "○"}</span>
          {c.label}
        </li>
      ))}
    </ul>
  );
}

export default function ProjectDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  const { ready, token } = useSession();
  const [project, setProject] = useState<Project | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<DialogMode>(null);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deletingAgent, setDeletingAgent] = useState<Agent | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const fetchProjectData = useCallback(
    (authToken: string) =>
      Promise.all([
        api.getProject(authToken, projectId),
        api.listAgents(authToken, projectId),
        api.listKnowledgeBases(authToken, projectId),
      ]),
    [projectId],
  );

  function applyProjectData([projectData, agentList, kbList]: Awaited<
    ReturnType<typeof fetchProjectData>
  >) {
    setProject(projectData);
    setAgents(agentList);
    setKnowledgeBases(kbList);
  }

  async function load(authToken: string) {
    applyProjectData(await fetchProjectData(authToken));
  }

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
    fetchProjectData(token)
      .then(([projectData, agentList, kbList]) => {
        if (cancelled) return;
        setProject(projectData);
        setAgents(agentList);
        setKnowledgeBases(kbList);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        router.replace("/projects");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ready, token, fetchProjectData, projectId, router]);

  function openCreate() {
    setEditingAgent(null);
    setForm(emptyForm);
    setError(null);
    setDialog("create");
  }

  function openEdit(agent: Agent) {
    setEditingAgent(agent);
    setForm({
      name: agent.name,
      description: agent.description || "",
      system_prompt: agent.system_prompt,
      model_name: agent.model_name,
      knowledge_base_ids: agent.knowledge_base_ids || [],
    });
    setError(null);
    setDialog("edit");
  }

  function closeDialog() {
    setDialog(null);
    setEditingAgent(null);
    setForm(emptyForm);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      if (dialog === "create") {
        await api.createAgent(token, {
          name: form.name,
          project_id: projectId,
          description: form.description || undefined,
          system_prompt: form.system_prompt,
          model_name: form.model_name,
          knowledge_base_ids: form.knowledge_base_ids,
        });
      } else if (dialog === "edit" && editingAgent) {
        await api.updateAgent(token, editingAgent.id, {
          name: form.name,
          description: form.description || undefined,
          system_prompt: form.system_prompt,
          model_name: form.model_name,
          knowledge_base_ids: form.knowledge_base_ids,
        });
      }
      closeDialog();
      await load(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save agent");
    } finally {
      setSaving(false);
    }
  }

  function confirmDeleteAgent(agent: Agent) {
    setDeletingAgent(agent);
    setDialog("delete");
    setError(null);
  }

  async function onDelete() {
    if (!token || !deletingAgent) return;
    setDeleteBusy(true);
    setError(null);
    try {
      await api.deleteAgent(token, deletingAgent.id);
      setDialog(null);
      setDeletingAgent(null);
      await load(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete agent");
    } finally {
      setDeleteBusy(false);
    }
  }

  if (loading) {
    return (
      <main
        className="mx-auto min-h-dvh max-w-5xl px-4 py-8 sm:px-6 sm:py-10"
        aria-busy="true"
      >
        <div className="mb-8 space-y-2">
          <div className="h-4 w-24 animate-pulse rounded bg-line" />
          <div className="h-9 w-64 animate-pulse rounded-lg bg-line" />
        </div>
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-40 animate-pulse rounded-2xl border border-line bg-surface/60"
            />
          ))}
        </div>
        <span className="sr-only">Loading agents…</span>
      </main>
    );
  }

  if (!project) {
    return null;
  }

  return (
    <main className="mx-auto min-h-dvh max-w-5xl px-6 py-10">
      <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
            Orchestra
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold">{project.name}</h1>
          <p className="mt-1 text-fg-muted">
            {project.description || "Manage agents in this project."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/projects/${projectId}/chat`}
            className="rounded-lg bg-fg px-4 py-2 text-sm font-semibold text-ground hover:bg-fg-muted"
          >
            Open Chat
          </Link>
          <Link
            href={`/projects/${projectId}/knowledge`}
            className="rounded-lg border border-line-strong px-3 py-2 text-sm font-medium hover:bg-raised"
          >
            Knowledge Base
          </Link>
          <Link
            href={`/projects/${projectId}/observability`}
            className="rounded-lg border border-line-strong px-3 py-2 text-sm font-medium hover:bg-raised"
          >
            Observability
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg border border-line-strong px-3 py-2 text-sm font-medium hover:bg-raised"
          >
            Dashboard
          </Link>
          <button
            onClick={openCreate}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-ground hover:brightness-110"
          >
            Create Agent
          </button>
        </div>
      </header>

      <nav className="mb-6 flex flex-wrap gap-2 border-b border-line pb-3">
        <Link
          href="/dashboard"
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-fg-muted hover:bg-raised"
        >
          Dashboard
        </Link>
        <Link
          href={`/projects/${projectId}`}
          className="rounded-lg bg-accent/10 px-3 py-1.5 text-sm font-semibold text-accent"
        >
          Agents
        </Link>
        <Link
          href={`/projects/${projectId}/knowledge`}
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-fg-muted hover:bg-raised"
        >
          Knowledge Base
        </Link>
        <Link
          href={`/projects/${projectId}/chat`}
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-fg-muted hover:bg-raised"
        >
          Chat
        </Link>
        <Link
          href={`/projects/${projectId}/observability`}
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-fg-muted hover:bg-raised"
        >
          Observability
        </Link>
      </nav>

      {error && !dialog && (
        <p className="mb-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}

      <section className="space-y-3">
        {agents.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-line-strong bg-surface/50 px-6 py-12 text-center">
            <p className="font-display text-lg font-semibold text-fg">
              No agents yet
            </p>
            <p className="mx-auto mt-2 max-w-md text-sm text-fg-muted">
              An agent is a prompt, a model, and optionally a knowledge base.
              Create one and you can chat with it, ground it in your documents,
              and trace every run it produces.
            </p>
            <button
              type="button"
              onClick={openCreate}
              className="touch-row mt-5 inline-flex items-center rounded-lg bg-accent px-5 text-sm font-semibold text-ground hover:brightness-110"
            >
              Create your first agent
            </button>
          </div>
        ) : (
          agents.map((agent) => (
            <article
              key={agent.id}
              className="rounded-2xl border border-line bg-surface/80 p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h3 className="font-display text-lg font-semibold">{agent.name}</h3>
                  <p className="mt-1 text-sm text-fg-muted">
                    {agent.description || "No description"}
                  </p>
                  <p className="mt-2 text-xs text-fg-faint">
                    Model: {agent.model_name} · Updated{" "}
                    {new Date(agent.updated_at).toLocaleString()}
                  </p>
                  <p className="mt-1 text-xs text-fg-subtle">
                    Knowledge bases:{" "}
                    {agent.knowledge_base_ids?.length
                      ? agent.knowledge_base_ids
                          .map((id) => knowledgeBases.find((kb) => kb.id === id)?.name || `KB ${id}`)
                          .join(", ")
                      : "None"}
                  </p>
                  <AgentCapabilities
                    hasKnowledgeBase={Boolean(agent.knowledge_base_ids?.length)}
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => openEdit(agent)}
                    className="rounded-lg border border-line-strong px-3 py-2 text-sm font-medium hover:bg-raised"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => confirmDeleteAgent(agent)}
                    className="rounded-lg border border-red-500/30 px-3 py-2 text-sm font-medium text-red-300 hover:bg-red-500/10"
                  >
                    Delete
                  </button>
                </div>
              </div>
              {agent.system_prompt && (
                <pre className="mt-4 overflow-x-auto rounded-lg bg-raised p-3 text-xs text-fg-muted">
                  {agent.system_prompt}
                </pre>
              )}
            </article>
          ))
        )}
      </section>

      {dialog === "delete" && deletingAgent && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-agent-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
        >
          <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-lg">
            <h2 id="delete-agent-title" className="font-display text-xl font-semibold">
              Delete “{deletingAgent.name}”?
            </h2>
            <p className="mt-2 text-sm text-fg-muted">
              The agent and its prompt configuration are removed permanently.
              Conversations and execution traces it produced are kept, but will
              no longer be linked to an agent.
            </p>

            {error && (
              <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">
                {error}
              </p>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setDialog(null);
                  setDeletingAgent(null);
                }}
                disabled={deleteBusy}
                className="rounded-lg border border-line-strong px-3 py-2 text-sm font-medium hover:bg-raised disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onDelete}
                disabled={deleteBusy}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
              >
                {deleteBusy ? "Deleting…" : "Delete agent"}
              </button>
            </div>
          </div>
        </div>
      )}

      {(dialog === "create" || dialog === "edit") && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <form
            onSubmit={onSubmit}
            className="w-full max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-lg"
          >
            <h2 className="font-display text-xl font-semibold">
              {dialog === "create" ? "Create Agent" : "Edit Agent"}
            </h2>
            <p className="mt-1 text-sm text-fg-muted">
              Configure name, system prompt, and default model for this agent.
            </p>

            <label className="mt-4 block text-sm">
              <span className="mb-1 block text-fg-muted">Name</span>
              <input
                required
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="w-full rounded-lg border border-line-strong px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="Research assistant"
              />
            </label>

            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-fg-muted">Description</span>
              <input
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
                className="w-full rounded-lg border border-line-strong px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="Optional"
              />
            </label>

            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-fg-muted">Model</span>
              <input
                required
                value={form.model_name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, model_name: e.target.value }))
                }
                className="w-full rounded-lg border border-line-strong px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="openai/gpt-oss-20b"
              />
            </label>

            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-fg-muted">System prompt</span>
              <textarea
                rows={5}
                value={form.system_prompt}
                onChange={(e) =>
                  setForm((f) => ({ ...f, system_prompt: e.target.value }))
                }
                className="w-full rounded-lg border border-line-strong px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="You are a helpful research assistant..."
              />
            </label>

            <fieldset className="mt-3 rounded-lg border border-line p-3">
              <legend className="px-1 text-sm font-medium text-fg">Knowledge Bases</legend>
              <p className="mb-2 text-xs text-fg-subtle">
                Attach knowledge bases for retrieval-augmented responses in chat.
              </p>
              {knowledgeBases.length === 0 ? (
                <p className="text-xs text-fg-subtle">No knowledge bases in this project.</p>
              ) : (
                <div className="space-y-1.5">
                  {knowledgeBases.map((kb) => {
                    const checked = form.knowledge_base_ids.includes(kb.id);
                    return (
                      <label key={kb.id} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) =>
                            setForm((f) => ({
                              ...f,
                              knowledge_base_ids: e.target.checked
                                ? [...f.knowledge_base_ids, kb.id]
                                : f.knowledge_base_ids.filter((id) => id !== kb.id),
                            }))
                          }
                        />
                        <span>{kb.name}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </fieldset>

            {error && (
              <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">
                {error}
              </p>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={closeDialog}
                className="rounded-lg border border-line-strong px-3 py-2 text-sm font-medium hover:bg-raised"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-ground hover:brightness-110 disabled:opacity-60"
              >
                {saving ? "Saving..." : dialog === "create" ? "Create" : "Save"}
              </button>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}

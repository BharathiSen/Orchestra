"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { ApiError, api, type Agent, type Project } from "@/lib/api";
import { clearSession, getToken } from "@/lib/auth";

type DialogMode = "create" | "edit" | null;

const emptyForm = {
  name: "",
  description: "",
  system_prompt: "",
  model_name: "gemini-2.0-flash",
};

export default function ProjectDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  const [token, setToken] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<DialogMode>(null);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const load = useCallback(
    async (authToken: string) => {
      const [projectData, agentList] = await Promise.all([
        api.getProject(authToken, projectId),
        api.listAgents(authToken, projectId),
      ]);
      setProject(projectData);
      setAgents(agentList);
    },
    [projectId],
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
    load(authToken)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        router.replace("/projects");
      })
      .finally(() => setLoading(false));
  }, [load, projectId, router]);

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
        });
      } else if (dialog === "edit" && editingAgent) {
        await api.updateAgent(token, editingAgent.id, {
          name: form.name,
          description: form.description || undefined,
          system_prompt: form.system_prompt,
          model_name: form.model_name,
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

  async function onDelete(id: number) {
    if (!token) return;
    setError(null);
    try {
      await api.deleteAgent(token, id);
      await load(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete agent");
    }
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-6">
        <p className="text-slate-500">Loading agents...</p>
      </main>
    );
  }

  if (!project) {
    return null;
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
            Orchestra
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold">{project.name}</h1>
          <p className="mt-1 text-slate-600">
            {project.description || "Manage agents in this project."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/projects/${projectId}/chat`}
            className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
          >
            Open Chat
          </Link>
          <Link
            href={`/projects/${projectId}/knowledge`}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
          >
            Knowledge Base
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
          >
            Dashboard
          </Link>
          <button
            onClick={openCreate}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
          >
            Create Agent
          </button>
        </div>
      </header>

      <nav className="mb-6 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        <Link
          href="/dashboard"
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
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
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
        >
          Knowledge Base
        </Link>
        <Link
          href={`/projects/${projectId}/chat`}
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
        >
          Chat
        </Link>
      </nav>

      {error && !dialog && (
        <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <section className="space-y-3">
        {agents.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-slate-300 bg-white/50 px-4 py-10 text-center text-slate-500">
            No agents yet. Create your first agent for this project.
          </p>
        ) : (
          agents.map((agent) => (
            <article
              key={agent.id}
              className="rounded-2xl border border-slate-200 bg-white/80 p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h3 className="font-display text-lg font-semibold">{agent.name}</h3>
                  <p className="mt-1 text-sm text-slate-600">
                    {agent.description || "No description"}
                  </p>
                  <p className="mt-2 text-xs text-slate-400">
                    Model: {agent.model_name} · Updated{" "}
                    {new Date(agent.updated_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => openEdit(agent)}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => onDelete(agent.id)}
                    className="rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
              {agent.system_prompt && (
                <pre className="mt-4 overflow-x-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                  {agent.system_prompt}
                </pre>
              )}
            </article>
          ))
        )}
      </section>

      {dialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
          <form
            onSubmit={onSubmit}
            className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-lg"
          >
            <h2 className="font-display text-xl font-semibold">
              {dialog === "create" ? "Create Agent" : "Edit Agent"}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Configure name, system prompt, and default model for this agent.
            </p>

            <label className="mt-4 block text-sm">
              <span className="mb-1 block text-slate-600">Name</span>
              <input
                required
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="Research assistant"
              />
            </label>

            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-slate-600">Description</span>
              <input
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="Optional"
              />
            </label>

            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-slate-600">Model</span>
              <input
                required
                value={form.model_name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, model_name: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="gemini-2.0-flash"
              />
            </label>

            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-slate-600">System prompt</span>
              <textarea
                rows={5}
                value={form.system_prompt}
                onChange={(e) =>
                  setForm((f) => ({ ...f, system_prompt: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="You are a helpful research assistant..."
              />
            </label>

            {error && (
              <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={closeDialog}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
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

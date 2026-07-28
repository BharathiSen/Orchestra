"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { ApiError, api, type Project } from "@/lib/api";
import { clearSession, getToken } from "@/lib/auth";

type DialogMode = "edit" | null;

export default function ProjectsPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dialog, setDialog] = useState<DialogMode>(null);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [updatingProject, setUpdatingProject] = useState(false);

  async function loadProjects(authToken: string) {
    const data = await api.listProjects(authToken);
    setProjects(data);
  }

  useEffect(() => {
    const authToken = getToken();
    if (!authToken) {
      router.replace("/login");
      return;
    }
    setToken(authToken);
    loadProjects(authToken)
      .catch(() => {
        clearSession();
        router.replace("/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      const project = await api.createProject(token, {
        name,
        description: description || undefined,
      });
      setName("");
      setDescription("");
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create project");
      setSaving(false);
    }
  }

  async function onDelete(id: number) {
    if (!token) return;
    setError(null);
    try {
      await api.deleteProject(token, id);
      await loadProjects(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete project");
    }
  }

  function openEdit(project: Project) {
    setEditingProject(project);
    setEditName(project.name);
    setEditDescription(project.description || "");
    setDialog("edit");
    setError(null);
  }

  function closeDialog() {
    setDialog(null);
    setEditingProject(null);
    setEditName("");
    setEditDescription("");
  }

  async function onUpdateProject(event: FormEvent) {
    event.preventDefault();
    if (!token || !editingProject) return;
    setUpdatingProject(true);
    setError(null);
    try {
      await api.updateProject(token, editingProject.id, {
        name: editName,
        description: editDescription || undefined,
      });
      closeDialog();
      await loadProjects(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update project");
    } finally {
      setUpdatingProject(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-6">
        <p className="text-slate-500">Loading projects...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
            Orchestra
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold">Projects</h1>
          <p className="mt-1 text-slate-600">
            Workspaces that hold your agents.
          </p>
        </div>
        <Link
          href="/dashboard"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
        >
          Back to dashboard
        </Link>
      </header>

      <form
        onSubmit={onCreate}
        className="mb-8 rounded-2xl border border-slate-200 bg-white/80 p-6"
      >
        <h2 className="font-display text-lg font-semibold">Create project</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
              placeholder="Customer support agents"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Description</span>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
              placeholder="Optional"
            />
          </label>
        </div>
        {error && (
          <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={saving}
          className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
        >
          {saving ? "Creating..." : "Create project"}
        </button>
      </form>

      <section className="grid gap-3 sm:grid-cols-2">
        {projects.length === 0 ? (
          <p className="col-span-full rounded-2xl border border-dashed border-slate-300 bg-white/50 px-4 py-8 text-center text-slate-500">
            No projects yet. Create your first workspace above.
          </p>
        ) : (
          projects.map((project) => (
            <article
              key={project.id}
              className="rounded-2xl border border-slate-200 bg-white/80 p-5"
            >
              <Link href={`/projects/${project.id}`} className="block">
                <h3 className="font-display text-lg font-semibold text-ink hover:text-accent">
                  {project.name}
                </h3>
                <p className="mt-1 text-sm text-slate-600">
                  {project.description || "No description"}
                </p>
              </Link>
              <div className="mt-4 flex items-center justify-between gap-3">
                <Link href={`/projects/${project.id}`} className="text-sm font-medium text-accent hover:underline">
                  Open agents →
                </Link>
                <div className="flex gap-2">
                  <button
                    onClick={() => openEdit(project)}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => onDelete(project.id)}
                    className="rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </article>
          ))
        )}
      </section>

      {dialog === "edit" && editingProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
          <form
            onSubmit={onUpdateProject}
            className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-lg"
          >
            <h2 className="font-display text-xl font-semibold">Edit Project</h2>
            <p className="mt-1 text-sm text-slate-600">Update the project name and description.</p>

            <label className="mt-4 block text-sm">
              <span className="mb-1 block text-slate-600">Name</span>
              <input
                required
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
              />
            </label>

            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-slate-600">Description</span>
              <input
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
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
                disabled={updatingProject}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
              >
                {updatingProject ? "Saving..." : "Save"}
              </button>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}

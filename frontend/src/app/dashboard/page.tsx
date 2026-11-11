"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, api, type Agent, type Project, type User } from "@/lib/api";
import { clearSession, useSession } from "@/lib/auth";

export default function DashboardPage() {
  const router = useRouter();
  const { ready, token, user: storedUser } = useSession();
  // The stored user renders immediately; the fresh one replaces it once loaded.
  const [freshUser, setFreshUser] = useState<User | null>(null);
  const user = freshUser ?? storedUser;
  const [projects, setProjects] = useState<Project[]>([]);
  const [agentCounts, setAgentCounts] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    if (!token) {
      router.replace("/login");
      return;
    }

    let cancelled = false;
    Promise.all([api.me(token), api.listProjects(token), api.listAgents(token)])
      .then(([me, projectList, agents]) => {
        if (cancelled) return;
        setFreshUser(me);
        setProjects(projectList);
        const counts: Record<number, number> = {};
        for (const agent of agents as Agent[]) {
          counts[agent.project_id] = (counts[agent.project_id] || 0) + 1;
        }
        setAgentCounts(counts);
      })
      .catch((err) => {
        if (cancelled) return;
        // Only an expired or invalid token means "signed out". A network blip,
        // a 5xx, or a request aborted by navigating away must not wipe the
        // session — that used to log people out for clicking quickly.
        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load the workspace.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ready, token, router]);

  function logout() {
    clearSession();
    router.replace("/login");
  }

  if (loading) {
    // Skeletons mirror the real layout so nothing jumps when data lands.
    return (
      <main
        className="mx-auto min-h-dvh max-w-5xl px-4 py-8 sm:px-6 sm:py-10"
        aria-busy="true"
      >
        <div className="mb-10 space-y-2">
          <div className="h-4 w-24 animate-pulse rounded bg-line" />
          <div className="h-9 w-56 animate-pulse rounded-lg bg-line" />
          <div className="h-4 w-72 animate-pulse rounded bg-line" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-2xl border border-line bg-surface/60"
            />
          ))}
        </div>
        <span className="sr-only">Loading workspace…</span>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-dvh max-w-5xl px-6 py-10">
      <header className="mb-10 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
            Orchestra
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold">Dashboard</h1>
          <p className="mt-1 text-fg-muted">
            Welcome{user?.full_name ? `, ${user.full_name}` : ""} — projects and
            agents.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/evals"
            className="touch-row inline-flex items-center rounded-lg border border-line-strong px-3 text-sm font-medium hover:bg-raised"
          >
            Evaluations
          </Link>
          <Link
            href="/projects"
            className="touch-row inline-flex items-center rounded-lg border border-line-strong px-3 text-sm font-medium hover:bg-raised"
          >
            Manage projects
          </Link>
          <button
            onClick={logout}
            className="touch-row inline-flex items-center rounded-lg border border-line-strong px-3 text-sm font-medium hover:bg-raised"
          >
            Log out
          </button>
        </div>
      </header>

      {error && (
        <p role="alert" className="mb-6 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}

      <section className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h2 className="font-display text-xl font-semibold">Your projects</h2>
          <p className="mt-1 text-sm text-fg-muted">
            Open a project to create and manage agents.
          </p>
        </div>
        <Link
          href="/projects"
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-ground hover:brightness-110"
        >
          New project
        </Link>
      </section>

      {projects.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-line-strong bg-surface/50 px-4 py-10 text-center text-fg-subtle">
          No projects yet.{" "}
          <Link href="/projects" className="text-accent underline">
            Create your first project
          </Link>
          .
        </p>
      ) : (
        <section className="grid gap-4 sm:grid-cols-2">
          {projects.map((project) => (
            <Link
              key={project.id}
              href={`/projects/${project.id}`}
              className="rounded-2xl border border-line bg-surface/80 p-6 transition hover:border-accent hover:shadow-sm"
            >
              <h3 className="font-display text-lg font-semibold">{project.name}</h3>
              <p className="mt-2 line-clamp-2 text-sm text-fg-muted">
                {project.description || "No description"}
              </p>
              <p className="mt-4 text-xs font-medium text-fg-subtle">
                {agentCounts[project.id] || 0} agent
                {(agentCounts[project.id] || 0) === 1 ? "" : "s"}
              </p>
            </Link>
          ))}
        </section>
      )}

      <article className="mt-8 rounded-2xl border border-line bg-surface/80 p-6">
        <h2 className="font-display text-lg font-semibold">Account</h2>
        <dl className="mt-3 space-y-2 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-fg-subtle">Email</dt>
            <dd className="font-medium">{user?.email}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-fg-subtle">User ID</dt>
            <dd className="font-medium">{user?.id}</dd>
          </div>
        </dl>
      </article>
    </main>
  );
}

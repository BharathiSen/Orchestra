"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, type Agent, type Project, type User } from "@/lib/api";
import { clearSession, getStoredUser, getToken } from "@/lib/auth";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [agentCounts, setAgentCounts] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    const cached = getStoredUser();
    if (cached) setUser(cached);

    Promise.all([api.me(token), api.listProjects(token), api.listAgents(token)])
      .then(([me, projectList, agents]) => {
        setUser(me);
        setProjects(projectList);
        const counts: Record<number, number> = {};
        for (const agent of agents as Agent[]) {
          counts[agent.project_id] = (counts[agent.project_id] || 0) + 1;
        }
        setAgentCounts(counts);
      })
      .catch(() => {
        clearSession();
        router.replace("/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

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
          <div className="h-4 w-24 animate-pulse rounded bg-slate-200" />
          <div className="h-9 w-56 animate-pulse rounded-lg bg-slate-200" />
          <div className="h-4 w-72 animate-pulse rounded bg-slate-200" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-2xl border border-slate-200 bg-white/60"
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
          <p className="mt-1 text-slate-600">
            Welcome{user?.full_name ? `, ${user.full_name}` : ""} — projects and
            agents.
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/projects"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
          >
            Manage projects
          </Link>
          <button
            onClick={logout}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
          >
            Log out
          </button>
        </div>
      </header>

      <section className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h2 className="font-display text-xl font-semibold">Your projects</h2>
          <p className="mt-1 text-sm text-slate-600">
            Open a project to create and manage agents.
          </p>
        </div>
        <Link
          href="/projects"
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
        >
          New project
        </Link>
      </section>

      {projects.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white/50 px-4 py-10 text-center text-slate-500">
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
              className="rounded-2xl border border-slate-200 bg-white/80 p-6 transition hover:border-accent hover:shadow-sm"
            >
              <h3 className="font-display text-lg font-semibold">{project.name}</h3>
              <p className="mt-2 line-clamp-2 text-sm text-slate-600">
                {project.description || "No description"}
              </p>
              <p className="mt-4 text-xs font-medium text-slate-500">
                {agentCounts[project.id] || 0} agent
                {(agentCounts[project.id] || 0) === 1 ? "" : "s"}
              </p>
            </Link>
          ))}
        </section>
      )}

      <article className="mt-8 rounded-2xl border border-slate-200 bg-white/80 p-6">
        <h2 className="font-display text-lg font-semibold">Account</h2>
        <dl className="mt-3 space-y-2 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-slate-500">Email</dt>
            <dd className="font-medium">{user?.email}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-slate-500">User ID</dt>
            <dd className="font-medium">{user?.id}</dd>
          </div>
        </dl>
      </article>
    </main>
  );
}

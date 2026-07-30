"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  api,
  type DashboardSummary,
  type ExecutionSummary,
  type MetricsBreakdown,
  type Project,
} from "@/lib/api";
import { clearSession, getToken } from "@/lib/auth";

function formatMs(ms: number) {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} sec`;
  return `${ms} ms`;
}

function formatUsd(n: number) {
  if (n < 0.01 && n > 0) return `$${n.toFixed(6)}`;
  return `$${n.toFixed(4)}`;
}

export default function ObservabilityPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  const [project, setProject] = useState<Project | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [metrics, setMetrics] = useState<MetricsBreakdown | null>(null);
  const [executions, setExecutions] = useState<ExecutionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (token: string) => {
      const [projectData, sum, mets, rows] = await Promise.all([
        api.getProject(token, projectId),
        api.dashboardSummary(token, projectId),
        api.dashboardMetrics(token, projectId),
        api.listExecutions(token, projectId, 50),
      ]);
      setProject(projectData);
      setSummary(sum);
      setMetrics(mets);
      setExecutions(rows);
    },
    [projectId],
  );

  useEffect(() => {
    if (!Number.isFinite(projectId)) {
      router.replace("/projects");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    load(token)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load");
      })
      .finally(() => setLoading(false));
  }, [load, projectId, router]);

  if (loading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-6">
        <p className="text-slate-500">Loading observability…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
            Orchestra
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold">
            Execution Dashboard
          </h1>
          <p className="mt-1 text-slate-600">
            {project?.name || "Project"} — tokens, cost, latency, and traces.
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
            href={`/projects/${projectId}`}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
          >
            Agents
          </Link>
        </div>
      </header>

      <nav className="mb-6 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        <Link
          href={`/projects/${projectId}`}
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
        >
          Agents
        </Link>
        <Link
          href={`/projects/${projectId}/chat`}
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
        >
          Chat
        </Link>
        <Link
          href={`/projects/${projectId}/observability`}
          className="rounded-lg bg-accent/10 px-3 py-1.5 text-sm font-semibold text-accent"
        >
          Observability
        </Link>
      </nav>

      {error && (
        <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {summary && (
        <section className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Stat label="Today's Executions" value={String(summary.executions_today)} />
          <Stat label="Success Rate" value={`${summary.success_rate}%`} />
          <Stat
            label="Average Latency"
            value={formatMs(summary.average_latency_ms)}
          />
          <Stat
            label="Total Tokens"
            value={summary.total_tokens.toLocaleString()}
          />
          <Stat label="Total Cost" value={formatUsd(summary.total_cost_usd)} />
        </section>
      )}

      {metrics && Object.keys(metrics.step_avg_latency_ms).length > 0 && (
        <section className="mb-8 rounded-2xl border border-slate-200 bg-white/80 p-5">
          <h2 className="font-display text-lg font-semibold">Step latency (24h)</h2>
          <p className="mt-1 text-sm text-slate-600">
            Average time per pipeline stage — find bottlenecks fast.
          </p>
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {Object.entries(metrics.step_avg_latency_ms).map(([name, ms]) => (
              <li
                key={name}
                className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
              >
                <span className="font-medium capitalize">{name.replace(/_/g, " ")}</span>
                <span className="text-slate-600">{formatMs(ms)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <div className="mb-3 flex items-end justify-between gap-4">
          <div>
            <h2 className="font-display text-xl font-semibold">Recent Executions</h2>
            <p className="mt-1 text-sm text-slate-600">
              Click any row for steps, prompt snapshot, and replay.
            </p>
          </div>
        </div>

        {executions.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-slate-300 bg-white/50 px-4 py-10 text-center text-slate-500">
            No executions yet. Send a chat message to start tracing.
          </p>
        ) : (
          <ul className="space-y-2">
            {executions.map((ex) => (
              <li key={ex.id}>
                <Link
                  href={`/projects/${projectId}/executions/${ex.id}`}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white/80 px-4 py-3 transition hover:border-accent"
                >
                  <div>
                    <p className="font-medium">
                      Execution #{ex.id}{" "}
                      <span
                        className={
                          ex.success
                            ? "text-teal-700"
                            : ex.status === "error"
                              ? "text-red-600"
                              : "text-slate-500"
                        }
                      >
                        · {ex.status}
                      </span>
                    </p>
                    <p className="mt-0.5 line-clamp-1 text-sm text-slate-600">
                      {ex.prompt || "(empty prompt)"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-3 text-xs font-medium text-slate-500">
                    <span>{ex.pipeline}</span>
                    <span>{formatMs(ex.latency_ms)}</span>
                    <span>{ex.total_tokens.toLocaleString()} tokens</span>
                    <span>{formatUsd(ex.total_cost_usd)}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white/80 px-4 py-4">
      <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">
        {label}
      </p>
      <p className="mt-2 font-display text-2xl font-bold">{value}</p>
    </div>
  );
}

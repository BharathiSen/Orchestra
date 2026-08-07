"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

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

const STATUS_OPTIONS = ["", "running", "completed", "error", "success"] as const;
const PIPELINE_OPTIONS = [
  "",
  "direct",
  "tools",
  "orchestra",
  "orchestra_simple",
  "orchestra_full",
] as const;

export default function ObservabilityPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  const [project, setProject] = useState<Project | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [metrics, setMetrics] = useState<MetricsBreakdown | null>(null);
  const [executions, setExecutions] = useState<ExecutionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [pipeline, setPipeline] = useState("");

  const loadDashboard = useCallback(
    async (token: string) => {
      const [projectData, sum, mets] = await Promise.all([
        api.getProject(token, projectId),
        api.dashboardSummary(token, projectId),
        api.dashboardMetrics(token, projectId),
      ]);
      setProject(projectData);
      setSummary(sum);
      setMetrics(mets);
    },
    [projectId],
  );

  const loadExecutions = useCallback(
    async (
      token: string,
      filters: { q?: string; status?: string; pipeline?: string } = {},
    ) => {
      const rows = await api.listExecutions(token, projectId, {
        limit: 50,
        q: filters.q || undefined,
        status: filters.status || undefined,
        pipeline: filters.pipeline || undefined,
      });
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
    Promise.all([loadDashboard(token), loadExecutions(token)])
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load");
      })
      .finally(() => setLoading(false));
  }, [loadDashboard, loadExecutions, projectId, router]);

  async function onSearch(event: FormEvent) {
    event.preventDefault();
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setSearching(true);
    setError(null);
    try {
      await loadExecutions(token, { q, status, pipeline });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearSession();
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  function onClearFilters() {
    setQ("");
    setStatus("");
    setPipeline("");
    const token = getToken();
    if (!token) return;
    setSearching(true);
    loadExecutions(token)
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to reload");
      })
      .finally(() => setSearching(false));
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-5xl flex-col items-center justify-center px-6">
        <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
          Orchestra
        </p>
        <p className="mt-4 text-slate-500">Loading execution history…</p>
        <div className="mt-6 h-1 w-40 overflow-hidden rounded bg-slate-200">
          <div className="h-full w-1/2 animate-pulse bg-accent/60" />
        </div>
      </main>
    );
  }

  const hasFilters = Boolean(q.trim() || status || pipeline);

  return (
    <main className="mx-auto min-h-dvh max-w-5xl px-6 py-10">
      <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
            Orchestra
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold">
            Execution History
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
        <div className="mb-4">
          <h2 className="font-display text-xl font-semibold">Executions</h2>
          <p className="mt-1 text-sm text-slate-600">
            Search by prompt text, filter by status or pipeline, then open a row
            for steps, snapshot, and replay.
          </p>
        </div>

        <form
          onSubmit={onSearch}
          className="mb-6 flex flex-wrap items-end gap-3 border-b border-slate-200 pb-5"
        >
          <label className="min-w-[12rem] flex-1 text-sm">
            <span className="mb-1 block text-slate-600">Search</span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Prompt, response, model…"
              className="w-full rounded-lg border border-slate-300 bg-white/80 px-3 py-2 outline-none ring-accent focus:ring-2"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-slate-600">Status</span>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white/80 px-3 py-2 outline-none ring-accent focus:ring-2"
            >
              <option value="">All</option>
              {STATUS_OPTIONS.filter(Boolean).map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-slate-600">Pipeline</span>
            <select
              value={pipeline}
              onChange={(e) => setPipeline(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white/80 px-3 py-2 outline-none ring-accent focus:ring-2"
            >
              <option value="">All</option>
              {PIPELINE_OPTIONS.filter(Boolean).map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={searching}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
          >
            {searching ? "Searching…" : "Search"}
          </button>
          {hasFilters && (
            <button
              type="button"
              onClick={onClearFilters}
              disabled={searching}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white disabled:opacity-60"
            >
              Clear
            </button>
          )}
        </form>

        {searching ? (
          <p className="rounded-lg border border-dashed border-slate-300 bg-white/50 px-4 py-10 text-center text-slate-500">
            Searching executions…
          </p>
        ) : executions.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white/50 px-4 py-12 text-center">
            <p className="font-display text-lg font-semibold text-ink">
              {hasFilters ? "No matching executions" : "No executions yet"}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              {hasFilters
                ? "Try a broader search or clear filters."
                : "Send a chat message to start tracing tokens, cost, and latency."}
            </p>
            {!hasFilters && (
              <Link
                href={`/projects/${projectId}/chat`}
                className="mt-4 inline-block text-sm font-medium text-accent hover:underline"
              >
                Open Chat →
              </Link>
            )}
          </div>
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

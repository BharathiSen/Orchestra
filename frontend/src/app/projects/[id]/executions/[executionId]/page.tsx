"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  api,
  type ExecutionDetail,
  type ReplayPayload,
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

export default function ExecutionDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string; executionId: string }>();
  const projectId = Number(params.id);
  const executionId = Number(params.executionId);

  const [token, setToken] = useState<string | null>(null);
  const [execution, setExecution] = useState<ExecutionDetail | null>(null);
  const [replay, setReplay] = useState<ReplayPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ratingBusy, setRatingBusy] = useState(false);

  const load = useCallback(
    async (authToken: string) => {
      const data = await api.getExecution(authToken, executionId);
      if (data.project_id !== projectId) {
        throw new Error("Execution does not belong to this project");
      }
      setExecution(data);
    },
    [executionId, projectId],
  );

  useEffect(() => {
    if (!Number.isFinite(projectId) || !Number.isFinite(executionId)) {
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
        setError(err instanceof Error ? err.message : "Failed to load");
      })
      .finally(() => setLoading(false));
  }, [executionId, load, projectId, router]);

  async function onRate(rating: number) {
    if (!token || !execution) return;
    setRatingBusy(true);
    try {
      const updated = await api.rateExecution(token, execution.id, rating);
      setExecution({ ...execution, user_rating: updated.user_rating });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rating failed");
    } finally {
      setRatingBusy(false);
    }
  }

  async function onReplay() {
    if (!token || !execution) return;
    try {
      const payload = await api.replayExecution(token, execution.id);
      setReplay(payload);
      const qs = new URLSearchParams({
        replay: "1",
        message: payload.prompt,
        model: payload.model_name,
      });
      if (payload.conversation_id != null) {
        qs.set("conversation_id", String(payload.conversation_id));
      }
      if (payload.agent_id != null) qs.set("agent_id", String(payload.agent_id));
      if (payload.enable_orchestra) qs.set("orchestra", "1");
      if (payload.enable_tools) qs.set("tools", "1");
      router.push(`/projects/${projectId}/chat?${qs.toString()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Replay failed");
    }
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-6">
        <p className="text-slate-500">Loading execution…</p>
      </main>
    );
  }

  if (!execution) {
    return (
      <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
        <p className="text-red-600">{error || "Execution not found"}</p>
        <Link
          href={`/projects/${projectId}/observability`}
          className="mt-4 inline-block text-accent underline"
        >
          Back to observability
        </Link>
      </main>
    );
  }

  const snapshot = execution.snapshot || {};
  const retrieved = (snapshot.retrieved_chunks as unknown[]) || [];
  const tools = (snapshot.tool_calls as unknown[]) || [];

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
            Orchestra
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold">
            Execution #{execution.id}
          </h1>
          <p className="mt-1 text-slate-600">
            {execution.pipeline} · {execution.model_name} · {execution.status}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onReplay}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
          >
            Replay
          </button>
          <Link
            href={`/projects/${projectId}/observability`}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
          >
            All executions
          </Link>
        </div>
      </header>

      {error && (
        <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <section className="mb-6 grid gap-3 sm:grid-cols-4">
        <Metric label="Latency" value={formatMs(execution.latency_ms)} />
        <Metric
          label="Tokens"
          value={`${execution.total_tokens.toLocaleString()} (in ${execution.input_tokens} / out ${execution.output_tokens})`}
        />
        <Metric label="Cost" value={formatUsd(execution.total_cost_usd)} />
        <Metric label="API calls" value={String(execution.api_calls)} />
      </section>

      <section className="mb-6 rounded-2xl border border-slate-200 bg-white/80 p-5">
        <h2 className="font-display text-lg font-semibold">Pipeline steps</h2>
        {execution.steps.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">No step records.</p>
        ) : (
          <ol className="mt-4 space-y-2">
            {execution.steps.map((step) => (
              <li
                key={step.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={
                      step.status === "done"
                        ? "text-teal-700"
                        : step.status === "error"
                          ? "text-red-600"
                          : "text-slate-500"
                    }
                  >
                    {step.status === "done" ? "✓" : step.status === "error" ? "✗" : "…"}
                  </span>
                  <span className="font-medium capitalize">
                    {step.step_name.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="flex flex-wrap gap-3 text-xs text-slate-600">
                  <span>{formatMs(step.latency_ms)}</span>
                  <span>{step.tokens} tokens</span>
                  <span>{formatUsd(step.cost_usd)}</span>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      {execution.scores && (
        <section className="mb-6 rounded-2xl border border-slate-200 bg-white/80 p-5">
          <h2 className="font-display text-lg font-semibold">Heuristic scores</h2>
          <p className="mt-1 text-sm text-slate-600">
            Lightweight metrics — not LLM-as-a-judge.
          </p>
          <dl className="mt-3 grid gap-2 sm:grid-cols-2 text-sm">
            {Object.entries(execution.scores).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 rounded-lg bg-slate-50 px-3 py-2">
                <dt className="text-slate-500 capitalize">{k.replace(/_/g, " ")}</dt>
                <dd className="font-medium">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <section className="mb-6 rounded-2xl border border-slate-200 bg-white/80 p-5">
        <h2 className="font-display text-lg font-semibold">Prompt</h2>
        <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm">
          {execution.prompt}
        </pre>
      </section>

      <section className="mb-6 rounded-2xl border border-slate-200 bg-white/80 p-5">
        <h2 className="font-display text-lg font-semibold">Final response</h2>
        <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm">
          {execution.final_response || execution.error_detail || "(none)"}
        </pre>
      </section>

      {retrieved.length > 0 && (
        <section className="mb-6 rounded-2xl border border-slate-200 bg-white/80 p-5">
          <h2 className="font-display text-lg font-semibold">
            Retrieved context ({retrieved.length})
          </h2>
          <ul className="mt-3 space-y-2 text-sm">
            {retrieved.slice(0, 8).map((chunk, idx) => {
              const c = chunk as { document_name?: string; content?: string; score?: number };
              return (
                <li key={idx} className="rounded-lg bg-slate-50 p-3">
                  <p className="text-xs font-medium text-slate-500">
                    {c.document_name || "chunk"}{" "}
                    {c.score != null ? `· score ${Number(c.score).toFixed(3)}` : ""}
                  </p>
                  <p className="mt-1 line-clamp-4 text-slate-700">{c.content}</p>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {tools.length > 0 && (
        <section className="mb-6 rounded-2xl border border-slate-200 bg-white/80 p-5">
          <h2 className="font-display text-lg font-semibold">Tool calls</h2>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-50 p-3 text-xs">
            {JSON.stringify(tools, null, 2)}
          </pre>
        </section>
      )}

      <section className="mb-6 rounded-2xl border border-slate-200 bg-white/80 p-5">
        <h2 className="font-display text-lg font-semibold">Your rating</h2>
        <div className="mt-3 flex gap-2">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              disabled={ratingBusy}
              onClick={() => onRate(n)}
              className={`rounded-lg border px-3 py-1.5 text-sm font-medium ${
                execution.user_rating === n
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-slate-300 hover:bg-white"
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </section>

      {replay && (
        <p className="text-sm text-slate-500">
          Replay payload ready for execution #{replay.execution_id}.
        </p>
      )}
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white/80 px-4 py-3">
      <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  );
}

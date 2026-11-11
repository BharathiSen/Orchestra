"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ScoreTrend, type ScoreKey } from "@/components/evals/ScoreTrend";
import { ApiError, api, type EvalRunDetail, type EvalRunSummary } from "@/lib/api";
import { clearSession, useSession } from "@/lib/auth";

const CRITERIA: { key: ScoreKey; label: string; field: keyof EvalRunDetail["results"][number] }[] = [
  { key: "avg_correctness", label: "Correctness", field: "correctness" },
  { key: "avg_completeness", label: "Completeness", field: "completeness" },
  { key: "avg_relevance", label: "Relevance", field: "relevance" },
  { key: "avg_clarity", label: "Clarity", field: "clarity" },
];

function fmt(value: number | null | undefined, digits = 2): string {
  return value == null ? "—" : value.toFixed(digits);
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export default function EvalsPage() {
  const router = useRouter();
  const { ready, token } = useSession();
  const [runs, setRuns] = useState<EvalRunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  // Stored with the run it belongs to, so switching runs never shows the
  // previous run's questions while the next ones load.
  const [loaded, setLoaded] = useState<EvalRunDetail | null>(null);

  useEffect(() => {
    if (!ready) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    api
      .listEvalRuns(token)
      .then((list) => {
        if (!cancelled) setRuns(list);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load evaluations.");
      });
    return () => {
      cancelled = true;
    };
  }, [ready, token, router]);

  const latest = runs && runs.length ? runs[runs.length - 1] : null;
  const previous = runs && runs.length > 1 ? runs[runs.length - 2] : null;
  const activeId = selectedId ?? latest?.id ?? null;
  const detail = loaded && loaded.id === activeId ? loaded : null;

  useEffect(() => {
    if (!token || activeId == null) return;
    let cancelled = false;
    api
      .getEvalRun(token, activeId)
      .then((run) => {
        if (!cancelled) setLoaded(run);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load the run.");
      });
    return () => {
      cancelled = true;
    };
  }, [token, activeId]);

  const delta =
    latest?.avg_overall != null && previous?.avg_overall != null
      ? latest.avg_overall - previous.avg_overall
      : null;

  return (
    <main className="mx-auto min-h-dvh max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
            Orchestra
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold">Evaluations</h1>
          <p className="mt-2 text-sm text-fg-muted">
            A fixed set of {latest?.question_count ?? 12} questions, answered by the full
            multi-agent pipeline and graded by an LLM judge against the key points each
            answer must cover. Every run is tagged with a hash of the prompts it ran with,
            so a prompt change shows up here as a new point — better or worse.
          </p>
        </div>
        <Link
          href="/dashboard"
          className="rounded-lg border border-line-strong px-3 py-2 text-sm font-medium hover:bg-raised"
        >
          Dashboard
        </Link>
      </header>

      {error && (
        <p role="alert" className="mb-6 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}

      {runs === null && !error && (
        <div aria-busy="true" className="space-y-4">
          <div className="h-28 animate-pulse rounded-2xl border border-line bg-surface" />
          <div className="h-64 animate-pulse rounded-2xl border border-line bg-surface" />
          <span className="sr-only">Loading evaluations…</span>
        </div>
      )}

      {runs && runs.length === 0 && (
        <section className="rounded-2xl border border-dashed border-line-strong bg-surface p-8 text-center">
          <h2 className="font-display text-lg font-semibold">No evaluation runs yet</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm text-fg-muted">
            Runs are produced offline with a live model, never from the browser, so this
            page cannot trigger paid calls. From <code>backend/</code>:
          </p>
          <pre className="mx-auto mt-4 w-fit rounded-lg bg-ground px-4 py-2 text-left text-xs text-fg">
            python scripts/run_eval.py --label baseline
          </pre>
        </section>
      )}

      {runs && latest && (
        <>
          <section className="mb-6 grid gap-4 md:grid-cols-[minmax(0,260px)_minmax(0,1fr)]">
            <div className="rounded-2xl border border-line bg-surface p-5">
              <p className="text-xs font-medium tracking-wide text-fg-subtle uppercase">
                Latest overall
              </p>
              <p className="mt-2 font-display text-5xl font-bold text-fg">
                {fmt(latest.avg_overall)}
                <span className="ml-1 text-base font-medium text-fg-subtle">/ 5</span>
              </p>
              {delta != null && (
                <p className="mt-1 text-sm text-fg-muted">
                  {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(2)} vs “{previous?.label}”
                </p>
              )}
              <dl className="mt-4 grid grid-cols-2 gap-y-1 text-xs">
                <dt className="text-fg-subtle">Run</dt>
                <dd className="truncate text-right text-fg">{latest.label}</dd>
                <dt className="text-fg-subtle">Prompts</dt>
                <dd className="text-right font-mono text-fg">{latest.prompt_version}</dd>
                <dt className="text-fg-subtle">Judged</dt>
                <dd className="text-right text-fg">
                  {latest.judged_count}/{latest.question_count}
                </dd>
                <dt className="text-fg-subtle">Run cost</dt>
                <dd className="text-right text-fg">${Number(latest.total_cost_usd).toFixed(4)}</dd>
              </dl>
            </div>
            <ScoreTrend runs={runs} metric="avg_overall" title="Overall score by run" height={240} />
          </section>

          <section aria-label="Scores by criterion" className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {CRITERIA.map((c) => (
              <ScoreTrend
                key={c.key}
                runs={runs}
                metric={c.key}
                title={c.label}
                height={150}
                showRunLabels={false}
              />
            ))}
          </section>

          <section className="mb-8">
            <h2 className="mb-3 font-display text-lg font-semibold">Runs</h2>
            <div className="overflow-x-auto rounded-2xl border border-line bg-surface">
              <table className="w-full min-w-[760px] text-left text-sm">
                <caption className="sr-only">
                  Every evaluation run with its average judge scores. Select a run to see
                  each question.
                </caption>
                <thead className="border-b border-line text-xs text-fg-subtle">
                  <tr>
                    <th className="px-4 py-2 font-medium">Run</th>
                    <th className="px-4 py-2 font-medium">Prompts</th>
                    <th className="px-4 py-2 font-medium">Model</th>
                    <th className="px-4 py-2 text-right font-medium">Overall</th>
                    {CRITERIA.map((c) => (
                      <th key={c.key} className="px-4 py-2 text-right font-medium">
                        {c.label}
                      </th>
                    ))}
                    <th className="px-4 py-2 text-right font-medium">p50</th>
                    <th className="px-4 py-2 text-right font-medium">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {[...runs].reverse().map((run) => (
                    <tr
                      key={run.id}
                      className={`border-b border-line last:border-0 ${
                        run.id === activeId ? "bg-accent/10" : "hover:bg-raised"
                      }`}
                    >
                      <td className="px-4 py-2">
                        <button
                          type="button"
                          onClick={() => setSelectedId(run.id)}
                          aria-pressed={run.id === activeId}
                          className="text-left font-medium text-fg hover:text-accent"
                        >
                          {run.label}
                        </button>
                        <span className="block text-[11px] text-fg-subtle">
                          {fmtDate(run.created_at)}
                        </span>
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-fg-muted">{run.prompt_version}</td>
                      <td className="px-4 py-2 text-xs text-fg-muted">
                        {run.model.replace("openai/", "")}
                        <span className="block text-[11px] text-fg-subtle">
                          judge {run.judge_model.replace("openai/", "")}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right font-semibold text-fg">{fmt(run.avg_overall)}</td>
                      {CRITERIA.map((c) => (
                        <td key={c.key} className="px-4 py-2 text-right text-fg-muted">
                          {fmt(run[c.key])}
                        </td>
                      ))}
                      <td className="px-4 py-2 text-right text-fg-muted">
                        {run.p50_latency_ms == null ? "—" : `${(run.p50_latency_ms / 1000).toFixed(1)}s`}
                      </td>
                      <td className="px-4 py-2 text-right text-fg-muted">
                        ${Number(run.total_cost_usd).toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section aria-busy={!detail}>
            <h2 className="mb-1 font-display text-lg font-semibold">
              Questions{detail ? ` · ${detail.label}` : ""}
            </h2>
            {detail?.notes && <p className="mb-3 text-sm text-fg-muted">{detail.notes}</p>}
            {!detail && <div className="h-40 animate-pulse rounded-2xl border border-line bg-surface" />}
            {detail && (
              <ul className="space-y-3">
                {detail.results.map((r) => (
                  <li key={r.question_id} className="rounded-2xl border border-line bg-surface p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-[11px] tracking-wide text-fg-subtle uppercase">
                          {r.category} · {r.route ?? "no"} route
                        </p>
                        <p className="mt-0.5 font-medium text-fg">{r.question}</p>
                      </div>
                      <p className="shrink-0 text-right">
                        <span className="font-display text-2xl font-bold text-fg">{fmt(r.overall)}</span>
                        <span className="block text-[11px] text-fg-subtle">overall</span>
                      </p>
                    </div>
                    <dl className="mt-3 flex flex-wrap gap-2 text-xs">
                      {CRITERIA.map((c) => (
                        <div key={c.key} className="rounded-md border border-line px-2 py-1">
                          <dt className="inline text-fg-subtle">{c.label} </dt>
                          <dd className="inline font-semibold text-fg">
                            {(r[c.field] as number | null) ?? "—"}
                          </dd>
                        </div>
                      ))}
                    </dl>
                    {r.rationale && (
                      <p className="mt-3 text-sm text-fg-muted">
                        <span className="text-fg-subtle">Judge: </span>
                        {r.rationale}
                      </p>
                    )}
                    {r.error && (
                      <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-300">
                        {r.error}
                      </p>
                    )}
                    <details className="mt-3 text-sm">
                      <summary className="cursor-pointer text-xs font-medium text-accent">
                        Show answer
                      </summary>
                      <p className="mt-2 whitespace-pre-wrap rounded-lg bg-ground p-3 text-xs text-fg-muted">
                        {r.answer || "(no answer)"}
                      </p>
                    </details>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </main>
  );
}

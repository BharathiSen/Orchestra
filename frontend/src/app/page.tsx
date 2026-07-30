"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getToken } from "@/lib/auth";

const FEATURES = [
  {
    title: "Multi-Agent",
    body: "Planner, Research, Writer, and Reviewer collaborate through LangGraph.",
  },
  {
    title: "Memory",
    body: "Redis short-term buffers plus Postgres long-term preferences.",
  },
  {
    title: "RAG",
    body: "Upload docs, embed with fastembed, retrieve via Postgres + pgvector.",
  },
  {
    title: "Tracing",
    body: "Every chat turn becomes an execution with timed pipeline steps.",
  },
  {
    title: "Replay",
    body: "Re-run stored prompts and snapshots to compare model behavior.",
  },
  {
    title: "Observability",
    body: "Tokens, cost, latency, success rate, and searchable execution history.",
  },
] as const;

const TECH = [
  "FastAPI",
  "Next.js",
  "LangGraph",
  "Redis",
  "Postgres + pgvector",
  "Docker",
] as const;

export default function LandingPage() {
  const [ctaHref, setCtaHref] = useState("/login");

  useEffect(() => {
    setCtaHref(getToken() ? "/dashboard" : "/login");
  }, []);

  return (
    <main className="min-h-screen">
      <section className="relative overflow-hidden px-6 pb-20 pt-16 md:pb-28 md:pt-24">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_20%_0%,rgba(13,148,136,0.18),transparent_50%),radial-gradient(ellipse_at_80%_20%,rgba(15,23,42,0.08),transparent_45%)]"
        />
        <div className="relative mx-auto max-w-5xl">
          <p className="animate-fade-up font-display text-6xl font-bold tracking-tight text-ink sm:text-7xl md:text-8xl">
            Orchestra
          </p>
          <h1 className="animate-fade-up-delay mt-6 max-w-2xl font-display text-2xl font-semibold text-ink sm:text-3xl">
            Production AI agent platform
          </h1>
          <p className="animate-fade-up-delay-2 mt-4 max-w-xl text-base text-slate-600 sm:text-lg">
            Design, run, and debug multi-agent workflows with memory, RAG, and
            full execution traces — all in one workspace.
          </p>
          <div className="animate-fade-up-delay-2 mt-10 flex flex-wrap gap-3">
            <Link
              href={ctaHref}
              className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-700"
            >
              Build
            </Link>
            <Link
              href={ctaHref}
              className="rounded-lg border border-slate-300 bg-white/60 px-5 py-2.5 text-sm font-semibold text-ink transition hover:border-accent hover:text-accent"
            >
              Observe
            </Link>
          </div>
        </div>
      </section>

      <section className="border-t border-slate-200/80 px-6 py-16">
        <div className="mx-auto max-w-5xl">
          <h2 className="font-display text-2xl font-bold">Features</h2>
          <p className="mt-2 max-w-xl text-slate-600">
            Everything you need to ship agents with operational visibility.
          </p>
          <ul className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature) => (
              <li key={feature.title}>
                <h3 className="font-display text-lg font-semibold text-accent">
                  {feature.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">
                  {feature.body}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="border-t border-slate-200/80 px-6 py-16">
        <div className="mx-auto max-w-5xl">
          <h2 className="font-display text-2xl font-bold">Architecture</h2>
          <p className="mt-2 max-w-xl text-slate-600">
            Vectors live in Postgres via pgvector — no separate Qdrant service.
          </p>
          <pre className="mt-8 overflow-x-auto rounded-lg border border-slate-200 bg-white/70 p-5 font-mono text-xs leading-relaxed text-slate-700 sm:text-sm">
{`                Next.js Frontend
                       │
                      REST / SSE
                       │
                FastAPI Backend
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
 PostgreSQL         Redis           LangGraph
 + pgvector      (memory)         Orchestrator
     │                                   │
 embeddings                      Planner → Research
 chunks                          → Writer → Reviewer
                                       │
                                  LLM Providers
                               (Groq / Gemini / Ollama)`}
          </pre>
        </div>
      </section>

      <section className="border-t border-slate-200/80 px-6 py-16">
        <div className="mx-auto max-w-5xl">
          <h2 className="font-display text-2xl font-bold">Tech stack</h2>
          <ul className="mt-8 flex flex-wrap gap-x-8 gap-y-3">
            {TECH.map((item) => (
              <li
                key={item}
                className="font-display text-base font-semibold text-ink"
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <footer className="border-t border-slate-200/80 px-6 py-10">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4">
          <p className="font-display text-sm font-semibold tracking-[0.15em] text-accent uppercase">
            Orchestra
          </p>
          <p className="text-sm text-slate-500">
            Open-source AI engineering platform · MIT
          </p>
          <Link
            href={ctaHref}
            className="text-sm font-medium text-accent hover:underline"
          >
            Get started →
          </Link>
        </div>
      </footer>
    </main>
  );
}

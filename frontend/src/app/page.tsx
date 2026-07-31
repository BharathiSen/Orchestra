"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getToken } from "@/lib/auth";

const PRODUCT_VIEWS = [
  {
    title: "Chat workspace",
    body: "Talk to agents with streaming replies, tool calls, and conversation memory in one place.",
    panel: "chat",
  },
  {
    title: "Multi-agent runs",
    body: "Planner, Research, Writer, and Reviewer hand off work through LangGraph — visible as they go.",
    panel: "agents",
  },
  {
    title: "Observability",
    body: "Every turn becomes an execution: steps, latency, tokens, and replay when something drifts.",
    panel: "observe",
  },
] as const;

const STEPS = [
  {
    n: "01",
    title: "Create a project",
    body: "Spin up a workspace for an agent product, experiment, or evaluation loop.",
  },
  {
    n: "02",
    title: "Configure agents",
    body: "Set prompts, models, knowledge bases, and how agents collaborate.",
  },
  {
    n: "03",
    title: "Run and trace",
    body: "Chat, inspect pipeline steps, then replay to compare behavior over time.",
  },
] as const;

const CAPABILITIES = [
  "Short-term Redis memory and long-term preferences",
  "Document RAG with Postgres + pgvector",
  "LangGraph multi-agent orchestration",
  "Execution traces, cost, and latency",
  "Knowledge upload and retrieval in-project",
  "Replay stored prompts and snapshots",
] as const;

function WorkspaceChrome({ variant }: { variant: "hero" | "chat" | "agents" | "observe" }) {
  const isHero = variant === "hero";
  const active =
    variant === "agents" ? "Agents" : variant === "observe" ? "Trace" : "Chat";

  return (
    <div
      className={`studio-chrome ${isHero ? "studio-chrome-hero" : ""}`}
      aria-hidden={!isHero}
    >
      <div className="studio-chrome-bar">
        <span className="studio-chrome-dot" />
        <span className="studio-chrome-dot" />
        <span className="studio-chrome-dot" />
        <span className="studio-chrome-title">Orchestra · Studio</span>
      </div>
      <div className="studio-chrome-body">
        <aside className="studio-chrome-nav">
          {["Projects", "Chat", "Agents", "Knowledge", "Trace"].map((item) => (
            <span
              key={item}
              className={item === active ? "is-active" : undefined}
            >
              {item}
            </span>
          ))}
        </aside>
        <div className="studio-chrome-main">
          {variant === "observe" ? (
            <>
              <div className="studio-line wide" />
              <div className="studio-trace">
                <div className="studio-trace-row filled" />
                <div className="studio-trace-row" />
                <div className="studio-trace-row filled mid" />
                <div className="studio-trace-row" />
              </div>
            </>
          ) : variant === "agents" ? (
            <>
              <div className="studio-pipeline">
                {["Planner", "Research", "Writer", "Reviewer"].map((agent) => (
                  <span key={agent}>{agent}</span>
                ))}
              </div>
              <div className="studio-line" />
              <div className="studio-line short" />
              <div className="studio-line mid" />
            </>
          ) : (
            <>
              <div className="studio-bubble user">
                <div className="studio-line short" />
              </div>
              <div className="studio-bubble agent">
                <div className="studio-line" />
                <div className="studio-line mid" />
                <div className="studio-line short" />
              </div>
              {isHero ? (
                <div className="studio-bubble agent soft">
                  <div className="studio-line mid" />
                  <div className="studio-line short" />
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const [ctaHref, setCtaHref] = useState("/login");

  useEffect(() => {
    setCtaHref(getToken() ? "/dashboard" : "/login");
  }, []);

  return (
    <main className="studio-landing min-h-screen">
      <section className="studio-hero">
        <div className="studio-hero-copy px-6 pt-16 md:pt-20">
          <div className="mx-auto max-w-5xl">
            <p className="animate-fade-up font-display text-6xl font-bold tracking-tight text-ink sm:text-7xl md:text-8xl">
              Orchestra
            </p>
            <h1 className="animate-fade-up-delay mt-5 max-w-2xl font-display text-2xl font-semibold leading-snug text-ink sm:text-3xl">
              The studio for production AI agents
            </h1>
            <p className="animate-fade-up-delay-2 mt-4 max-w-lg text-base leading-relaxed text-slate-600 sm:text-lg">
              Design agents, run multi-step workflows, and inspect every
              execution — from one calm workspace.
            </p>
            <div className="animate-fade-up-delay-2 mt-9">
              <Link href={ctaHref} className="studio-cta">
                Open workspace
              </Link>
            </div>
          </div>
        </div>
        <div className="studio-hero-visual animate-fade-in-slow mt-12 md:mt-16">
          <WorkspaceChrome variant="hero" />
        </div>
      </section>

      <section className="studio-section px-6 py-20 md:py-24">
        <div className="mx-auto max-w-5xl">
          <h2 className="font-display text-3xl font-bold text-ink">Product</h2>
          <p className="mt-3 max-w-xl text-slate-600">
            Three surfaces you live in while shipping agents.
          </p>
          <div className="mt-12 space-y-16">
            {PRODUCT_VIEWS.map((view, index) => (
              <div
                key={view.title}
                className={`grid items-center gap-8 md:grid-cols-2 md:gap-12 ${
                  index % 2 === 1 ? "md:[&>*:first-child]:order-2" : ""
                }`}
              >
                <div>
                  <h3 className="font-display text-xl font-semibold text-ink">
                    {view.title}
                  </h3>
                  <p className="mt-3 text-base leading-relaxed text-slate-600">
                    {view.body}
                  </p>
                </div>
                <WorkspaceChrome variant={view.panel} />
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="studio-section studio-section-soft px-6 py-20 md:py-24">
        <div className="mx-auto max-w-5xl">
          <h2 className="font-display text-3xl font-bold text-ink">
            How it works
          </h2>
          <p className="mt-3 max-w-xl text-slate-600">
            From empty project to traced run in three steps.
          </p>
          <ol className="mt-12 grid gap-10 md:grid-cols-3">
            {STEPS.map((step) => (
              <li key={step.n}>
                <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent">
                  {step.n}
                </p>
                <h3 className="mt-3 font-display text-xl font-semibold text-ink">
                  {step.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-600">
                  {step.body}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="studio-section px-6 py-20 md:py-24">
        <div className="mx-auto max-w-5xl">
          <h2 className="font-display text-3xl font-bold text-ink">
            Capabilities
          </h2>
          <p className="mt-3 max-w-xl text-slate-600">
            What the platform already carries for serious agent work.
          </p>
          <ul className="mt-10 grid gap-x-12 gap-y-4 sm:grid-cols-2">
            {CAPABILITIES.map((item) => (
              <li
                key={item}
                className="border-t border-slate-300/70 pt-4 text-sm leading-relaxed text-slate-700"
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="studio-section studio-section-soft px-6 py-20 md:py-24">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="font-display text-3xl font-bold text-ink">
            Built for AI engineers
          </h2>
          <p className="mt-4 text-base leading-relaxed text-slate-600">
            If you are wiring agents, memory, retrieval, and evals into a real
            product — Orchestra is the workspace that keeps the loop visible.
          </p>
        </div>
      </section>

      <section className="studio-cta-band px-6 py-16 md:py-20">
        <div className="mx-auto flex max-w-5xl flex-col items-start justify-between gap-6 md:flex-row md:items-center">
          <div>
            <h2 className="font-display text-2xl font-bold text-ink sm:text-3xl">
              Open Orchestra
            </h2>
            <p className="mt-2 text-slate-600">
              Start a project and run your first traced agent conversation.
            </p>
          </div>
          <Link href={ctaHref} className="studio-cta">
            Get started
          </Link>
        </div>
      </section>

      <footer className="border-t border-slate-300/60 px-6 py-10">
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
            Open workspace →
          </Link>
        </div>
      </footer>
    </main>
  );
}

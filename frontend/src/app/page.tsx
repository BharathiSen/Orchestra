"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import CardSwap, { Card } from "@/components/CardSwap";
import { getToken } from "@/lib/auth";

const STEPS = [
  {
    n: "01",
    title: "Create a project",
    body: "Spin up a workspace for an agent product, experiment, or evaluation loop.",
    icon: "project",
  },
  {
    n: "02",
    title: "Configure agents",
    body: "Set prompts, models, knowledge bases, and how agents collaborate.",
    icon: "agents",
  },
  {
    n: "03",
    title: "Run and trace",
    body: "Chat, inspect pipeline steps, then replay to compare behavior over time.",
    icon: "trace",
  },
] as const;

function GitHubIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden
    >
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.087-.731.084-.716.084-.716 1.205.082 1.838 1.215 1.838 1.215 1.07 1.835 2.809 1.305 3.492.998.108-.776.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.046.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
    </svg>
  );
}

function StepIcon({ name }: { name: (typeof STEPS)[number]["icon"] }) {
  if (name === "project") {
    return (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.75">
        <circle cx="12" cy="12" r="7" />
        <circle cx="12" cy="12" r="2.5" />
      </svg>
    );
  }
  if (name === "agents") {
    return (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.75">
        <path d="M13 3L6 14h5l-1 7 8-12h-5l0-6z" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" strokeLinecap="round" />
    </svg>
  );
}

const CAPABILITIES = [
  {
    title: "Memory",
    body: "Short-term Redis buffers plus long-term preferences across sessions.",
    icon: "memory",
  },
  {
    title: "RAG",
    body: "Upload docs and retrieve with Postgres + pgvector embeddings.",
    icon: "rag",
  },
  {
    title: "Multi-agent",
    body: "LangGraph orchestration across Planner, Research, Writer, Reviewer.",
    icon: "agents",
  },
  {
    title: "Tracing",
    body: "Execution steps with tokens, cost, and latency on every chat turn.",
    icon: "trace",
  },
  {
    title: "Knowledge",
    body: "Project knowledge bases for grounded answers inside the workspace.",
    icon: "knowledge",
  },
  {
    title: "Replay",
    body: "Re-run stored prompts and snapshots to compare model behavior.",
    icon: "replay",
  },
] as const;

function CapabilityIcon({
  name,
}: {
  name: (typeof CAPABILITIES)[number]["icon"];
}) {
  const cls = "h-5 w-5";
  if (name === "memory") {
    return (
      <svg viewBox="0 0 24 24" className={cls} fill="none" stroke="currentColor" strokeWidth="1.75">
        <rect x="4" y="5" width="16" height="14" rx="2" />
        <path d="M8 9h8M8 13h5" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "rag") {
    return (
      <svg viewBox="0 0 24 24" className={cls} fill="none" stroke="currentColor" strokeWidth="1.75">
        <path d="M7 4h8l4 4v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z" />
        <path d="M14 4v5h5M9 13h6M9 17h4" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "agents") {
    return (
      <svg viewBox="0 0 24 24" className={cls} fill="none" stroke="currentColor" strokeWidth="1.75">
        <circle cx="8" cy="10" r="2.5" />
        <circle cx="16" cy="10" r="2.5" />
        <path d="M5 18c.8-2.2 2.4-3.5 3-3.5h8c.6 0 2.2 1.3 3 3.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "trace") {
    return (
      <svg viewBox="0 0 24 24" className={cls} fill="none" stroke="currentColor" strokeWidth="1.75">
        <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "knowledge") {
    return (
      <svg viewBox="0 0 24 24" className={cls} fill="none" stroke="currentColor" strokeWidth="1.75">
        <path d="M4 6.5C4 5.7 4.7 5 5.5 5H11v13H5.5A1.5 1.5 0 0 1 4 16.5v-10z" />
        <path d="M20 6.5C20 5.7 19.3 5 18.5 5H13v13h5.5a1.5 1.5 0 0 0 1.5-1.5v-10z" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" className={cls} fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M4 12a8 8 0 0 1 8-8" strokeLinecap="round" />
      <path d="M12 4a8 8 0 1 1-8 8" strokeLinecap="round" />
      <path d="M12 8v4l2.5 2.5" strokeLinecap="round" />
    </svg>
  );
}

export default function LandingPage() {
  const [ctaHref, setCtaHref] = useState("/login");

  useEffect(() => {
    setCtaHref(getToken() ? "/dashboard" : "/login");
  }, []);

  return (
    <main className="studio-landing min-h-screen">
      <section className="studio-hero px-6 pb-20 pt-16 md:pb-28 md:pt-20">
        <div className="mx-auto max-w-5xl">
          <p className="animate-fade-up font-display text-6xl font-bold tracking-tight text-ink sm:text-7xl md:text-8xl">
            Orchestra
          </p>
          <h1 className="animate-fade-up-delay mt-5 max-w-2xl font-display text-2xl font-semibold leading-snug text-ink sm:text-3xl">
            The studio for production AI agents
          </h1>
          <p className="animate-fade-up-delay-2 mt-4 max-w-lg text-base leading-relaxed text-slate-600 sm:text-lg">
            Design agents, run multi-step workflows, and inspect every execution
            — from one calm workspace.
          </p>
          <div className="animate-fade-up-delay-2 mt-9">
            <Link href={ctaHref} className="studio-cta">
              Open workspace
            </Link>
          </div>
        </div>
      </section>

      <section
        id="how-it-works"
        className="studio-section studio-section-soft px-6 py-20 md:py-24"
      >
        <div className="mx-auto max-w-5xl">
          <p className="studio-eyebrow">Workflow</p>
          <h2 className="mt-3 font-display text-3xl font-bold text-ink">
            How it works
          </h2>
          <p className="mt-3 max-w-xl text-slate-600">
            From empty project to traced run — three steps to a visible agent
            loop.
          </p>
          <ol className="mt-12 grid gap-5 md:grid-cols-3">
            {STEPS.map((step) => (
              <li key={step.n} className="studio-shimmer-card">
                <div className="studio-shimmer-inner">
                  <span className="studio-shimmer-num" aria-hidden>
                    {step.n}
                  </span>
                  <div className="studio-shimmer-icon">
                    <StepIcon name={step.icon} />
                  </div>
                  <p className="mt-5 font-display text-xs font-semibold tracking-[0.18em] text-accent uppercase">
                    Step {step.n}
                  </p>
                  <h3 className="mt-2 font-display text-xl font-semibold text-ink">
                    {step.title}
                  </h3>
                  <p className="mt-3 text-sm leading-relaxed text-slate-600">
                    {step.body}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section
        id="capabilities"
        className="capabilities-swap studio-section px-6 py-20 md:py-24"
      >
        <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2 lg:gap-8">
          <div>
            <p className="studio-eyebrow">Capabilities</p>
            <h2 className="mt-4 font-display text-4xl font-bold leading-tight tracking-tight text-white sm:text-5xl">
              Agent stacks have never looked this clear
            </h2>
            <p className="mt-4 max-w-md text-base text-slate-400 sm:text-lg">
              Memory, RAG, multi-agent runs, and traces — watch the stack cycle
              through what Orchestra already ships.
            </p>
          </div>
          <div className="relative h-[520px] w-full sm:h-[560px] lg:h-[600px]">
            <CardSwap
              width={500}
              height={360}
              cardDistance={60}
              verticalDistance={70}
              delay={5000}
              pauseOnHover={false}
              skewAmount={6}
              easing="elastic"
            >
              {CAPABILITIES.slice(0, 3).map((item) => (
                <Card key={item.title}>
                  <div className="card-swap-tab">
                    <CapabilityIcon name={item.icon} />
                    {item.title}
                  </div>
                  <div className="card-swap-panel">
                    <h3 className="card-swap-title">{item.title}</h3>
                    <p className="card-swap-body">{item.body}</p>
                  </div>
                </Card>
              ))}
            </CardSwap>
          </div>
        </div>
      </section>

      <section className="studio-cta-band px-6 py-20 md:py-24">
        <div className="mx-auto flex max-w-5xl flex-col items-start justify-between gap-8 md:flex-row md:items-center">
          <div className="max-w-2xl">
            <h2 className="font-display text-3xl font-bold text-ink">
              Built for AI engineers
            </h2>
            <p className="mt-4 text-base leading-relaxed text-slate-600">
              If you are wiring agents, memory, retrieval, and evals into a real
              product — Orchestra is the workspace that keeps the loop visible.
              Start a project and run your first traced agent conversation.
            </p>
          </div>
          <Link href={ctaHref} className="studio-cta shrink-0">
            Get started
          </Link>
        </div>
      </section>

      <footer className="studio-footer border-t border-slate-300/60 px-6 py-12">
        <div className="mx-auto grid max-w-5xl gap-10 md:grid-cols-[1.4fr_1fr]">
          <div>
            <p className="font-display text-2xl font-bold tracking-tight text-ink">
              Orchestra
            </p>
            <p className="mt-3 max-w-md text-sm leading-relaxed text-slate-600">
              Open-source AI engineering platform for designing, running, and
              tracing production agents.
            </p>
            <a
              href="https://github.com/BharathiSen/Orchestra"
              target="_blank"
              rel="noreferrer"
              className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-slate-600 transition hover:text-accent"
            >
              <GitHubIcon className="h-5 w-5" />
              GitHub
            </a>
          </div>
          <div>
            <p className="font-display text-sm font-semibold tracking-[0.12em] text-ink uppercase">
              Quick links
            </p>
            <ul className="mt-4 space-y-3 text-sm text-slate-600">
              <li>
                <a href="#how-it-works" className="hover:text-accent">
                  How it works
                </a>
              </li>
              <li>
                <a href="#capabilities" className="hover:text-accent">
                  Capabilities
                </a>
              </li>
              <li>
                <Link href={ctaHref} className="hover:text-accent">
                  Open workspace
                </Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="mx-auto mt-10 max-w-5xl border-t border-slate-300/60 pt-6 text-sm text-slate-500">
          © {new Date().getFullYear()} Orchestra · MIT
        </div>
      </footer>
    </main>
  );
}

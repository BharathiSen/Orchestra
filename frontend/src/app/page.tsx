"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { getToken } from "@/lib/auth";

/* Real figures from a full-route run on the deployed instance. They are kept
   here rather than invented so the hero panel matches what the product actually
   produces — and so the numbers in the event stream below reconcile with it. */
const TRACE_TOTAL_MS = 4020;

const TRACE_STEPS = [
  { name: "planner", ms: 380, tokens: "240t", startMs: 0 },
  { name: "research", ms: 1240, tokens: "1.8k", startMs: 380 },
  { name: "writer", ms: 1510, tokens: "1.4k", startMs: 1620 },
  { name: "reviewer", ms: 890, tokens: "620t", startMs: 3130 },
] as const;

const STREAM_EVENTS = [
  { t: "0.00s", name: "meta", value: <>conversation <b>#41</b></> },
  { t: "0.01s", name: "execution_meta", value: <><b>#1284</b> · orchestra_full</> },
  { t: "0.38s", name: "orchestra_step", value: <><b>planner</b> done</> },
  { t: "1.62s", name: "retrieved_context", value: <><b>5 chunks</b> · handbook.pdf</> },
  { t: "1.63s", name: "orchestra_step", value: <><b>research</b> done</> },
  { t: "3.13s", name: "orchestra_step", value: <><b>writer</b> done</> },
  { t: "4.02s", name: "orchestra_step", value: <><b>reviewer</b> done</> },
  { t: "4.03s", name: "token", value: <>&quot;Redis suits ephemeral session…</> },
] as const;

const CAPABILITIES = [
  {
    title: "Execution tracing",
    body: "Every turn writes a durable record: per-step latency, tokens, and cost, searchable and filterable.",
    icon: "trace",
  },
  {
    title: "Multi-agent pipelines",
    body: "LangGraph orchestration across Planner, Research, Writer, and Reviewer, with a fast route for simple questions.",
    icon: "agents",
  },
  {
    title: "RAG on pgvector",
    body: "Upload PDF, DOCX, or TXT — extracted, chunked, embedded, and retrieved inside PostgreSQL.",
    icon: "rag",
  },
  {
    title: "Two-tier memory",
    body: "A Redis conversation buffer that summarises on overflow, plus durable user facts in Postgres.",
    icon: "memory",
  },
  {
    title: "Knowledge bases",
    body: "Attach documents per agent, and see exactly which chunks grounded an answer.",
    icon: "knowledge",
  },
  {
    title: "Replay",
    body: "Reload a stored prompt with its original pipeline flags to compare behaviour after a change.",
    icon: "replay",
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

function CapabilityIcon({ name }: { name: (typeof CAPABILITIES)[number]["icon"] }) {
  const cls = "h-[1.15rem] w-[1.15rem]";
  const common = {
    viewBox: "0 0 24 24",
    className: cls,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.6",
    "aria-hidden": true,
  } as const;

  if (name === "memory") {
    return (
      <svg {...common}>
        <rect x="4" y="5" width="16" height="14" rx="2" />
        <path d="M8 9h8M8 13h5" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "rag") {
    return (
      <svg {...common}>
        <path d="M7 4h8l4 4v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z" />
        <path d="M14 4v5h5M9 13h6M9 17h4" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "agents") {
    return (
      <svg {...common}>
        <circle cx="8" cy="10" r="2.5" />
        <circle cx="16" cy="10" r="2.5" />
        <path d="M5 18c.8-2.2 2.4-3.5 3-3.5h8c.6 0 2.2 1.3 3 3.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "trace") {
    return (
      <svg {...common}>
        <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "knowledge") {
    return (
      <svg {...common}>
        <path d="M4 6.5C4 5.7 4.7 5 5.5 5H11v13H5.5A1.5 1.5 0 0 1 4 16.5v-10z" />
        <path d="M20 6.5C20 5.7 19.3 5 18.5 5H13v13h5.5a1.5 1.5 0 0 0 1.5-1.5v-10z" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M4 12a8 8 0 0 1 8-8" strokeLinecap="round" />
      <path d="M12 4a8 8 0 1 1-8 8" strokeLinecap="round" />
      <path d="M12 8v4l2.5 2.5" strokeLinecap="round" />
    </svg>
  );
}

/** The hero's proof: one execution rendered as a timeline, not a feature list. */
function TraceCard() {
  return (
    <figure className="lp-trace">
      <figcaption className="lp-trace-head">
        <span>execution #1284 · orchestra_full</span>
        <span className="lp-badge">completed</span>
      </figcaption>

      <ol>
        {TRACE_STEPS.map((step) => (
          <li key={step.name} className="lp-trace-row">
            <span className="lp-trace-step">{step.name}</span>
            <span className="lp-lane">
              <i
                style={{
                  left: `${(step.startMs / TRACE_TOTAL_MS) * 100}%`,
                  width: `${(step.ms / TRACE_TOTAL_MS) * 100}%`,
                }}
              />
            </span>
            <span className="lp-trace-num">{step.ms}ms</span>
            <span className="lp-trace-num">{step.tokens}</span>
          </li>
        ))}
      </ol>

      <div className="lp-trace-foot">
        <span>4.02s total · 4,060 tokens</span>
        <span className="lp-cost">$0.00019</span>
      </div>
    </figure>
  );
}

/** Replays the real SSE contract once, when it scrolls into view. */
function EventStream() {
  const ref = useRef<HTMLDivElement>(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || live) return;

    // No IntersectionObserver (or an old browser) should not mean no content —
    // fall back to showing the finished state rather than an empty box.
    if (typeof IntersectionObserver === "undefined") {
      setLive(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setLive(true);
          observer.disconnect();
        }
      },
      { threshold: 0.35 },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [live]);

  return (
    <div ref={ref} className={`lp-term ${live ? "is-live" : ""}`}>
      <div className="lp-term-bar">
        <span>POST /api/v1/chat</span>
        <span>text/event-stream</span>
      </div>
      <div className="lp-term-body">
        {STREAM_EVENTS.map((event, i) => (
          <div
            key={`${event.t}-${event.name}`}
            className="lp-ev"
            style={{ "--i": i } as React.CSSProperties}
          >
            <span className="lp-ev-t">{event.t}</span>
            <span className="lp-ev-n">{event.name}</span>
            <span className="lp-ev-v">
              {event.value}
              {i === STREAM_EVENTS.length - 1 && <span className="lp-caret" />}
            </span>
          </div>
        ))}
        <div
          className="lp-ev"
          style={{ "--i": STREAM_EVENTS.length } as React.CSSProperties}
        >
          <span className="lp-ev-t">4.41s</span>
          <span className="lp-ev-n">done</span>
          <span className="lp-ev-v">
            4,060 tokens · <span className="lp-cost">$0.00019</span>
          </span>
        </div>
      </div>
    </div>
  );
}

// Present only when a demo account has been seeded and wired up. Absent in a
// normal local checkout, in which case the demo call-to-action is not rendered.
const DEMO_ENABLED = Boolean(
  process.env.NEXT_PUBLIC_DEMO_EMAIL && process.env.NEXT_PUBLIC_DEMO_PASSWORD,
);

export default function LandingPage() {
  const [ctaHref, setCtaHref] = useState("/login");
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    const authed = Boolean(getToken());
    setSignedIn(authed);
    setCtaHref(authed ? "/dashboard" : "/login");
  }, []);

  const showDemoCta = DEMO_ENABLED && !signedIn;

  return (
    <main className="lp min-h-dvh">
      {/* —— nav ———————————————————————————————————————————————— */}
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <span className="font-display text-lg font-bold tracking-tight">
          Orchestra<span className="text-lp-beam">.</span>
        </span>
        <div className="flex items-center gap-6 text-sm text-lp-dim">
          <a href="#capabilities" className="lp-link hidden transition sm:inline">
            Capabilities
          </a>
          <a
            href="https://github.com/BharathiSen/Orchestra"
            target="_blank"
            rel="noreferrer"
            className="lp-link inline-flex items-center gap-2 transition"
          >
            <GitHubIcon className="h-[1.05rem] w-[1.05rem]" />
            <span className="hidden sm:inline">GitHub</span>
          </a>
        </div>
      </nav>

      {/* —— hero ——————————————————————————————————————————————— */}
      <section className="px-6 pb-20 pt-10 md:pb-28 md:pt-16">
        <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[0.85fr_1.15fr] lg:gap-14">
          <div>
            <p className="lp-eyebrow animate-fade-up">Agent observability</p>
            <h1 className="animate-fade-up-delay mt-4 font-display text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl">
              Every agent run is a record, not a receipt.
            </h1>
            <p className="animate-fade-up-delay-2 mt-5 max-w-md text-base leading-relaxed text-lp-dim">
              Orchestra runs multi-agent pipelines over LangGraph and writes down
              what each one did — per-step latency, tokens, and cost, stored in
              Postgres and replayable.
            </p>

            <div className="animate-fade-up-delay-2 mt-8 flex flex-wrap items-center gap-3">
              <Link href={ctaHref} className="lp-cta">
                Open workspace
              </Link>
              {showDemoCta && (
                <Link href="/login?demo=1" className="lp-cta-ghost">
                  Try the demo
                </Link>
              )}
            </div>
            {showDemoCta && (
              <p className="animate-fade-up-delay-2 mt-3 text-xs text-lp-dim">
                No signup — opens a shared workspace with traced example runs.
              </p>
            )}

            <div className="animate-fade-up-delay-2 lp-rule mt-10 pt-5">
              <div className="lp-proof">
                <span>
                  <b>4</b> agents
                </span>
                <span>
                  <b>3</b> pipelines
                </span>
                <span>
                  <b>90</b> tests
                </span>
                <span>
                  <b>MIT</b> licensed
                </span>
              </div>
            </div>
          </div>

          <div className="animate-fade-in-slow">
            <TraceCard />
          </div>
        </div>
      </section>

      {/* —— live stream ————————————————————————————————————————— */}
      <section className="lp-rule px-6 py-20 md:py-24">
        <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[0.85fr_1.15fr] lg:gap-14">
          <div>
            <p className="lp-eyebrow">Server-sent events</p>
            <h2 className="mt-4 font-display text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
              Watch the pipeline think.
            </h2>
            <p className="mt-4 max-w-md text-base leading-relaxed text-lp-dim">
              One request opens one stream. Agent progress, retrieved chunks, and
              answer tokens all arrive on it, so the interface can show the work
              instead of a spinner.
            </p>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-lp-dim">
              The direct and multi-agent routes stream tokens straight from the
              model. The tool-calling route sends its answer once complete —
              its final node needs the whole response before it can check it.
            </p>
          </div>

          <EventStream />
        </div>
      </section>

      {/* —— capabilities ———————————————————————————————————————— */}
      <section id="capabilities" className="lp-rule px-6 py-20 md:py-24">
        <div className="mx-auto max-w-6xl">
          <p className="lp-eyebrow">Capabilities</p>
          <h2 className="mt-4 max-w-2xl font-display text-3xl font-bold leading-tight tracking-tight sm:text-4xl">
            The parts that make a run inspectable.
          </h2>

          <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map((item) => (
              <li key={item.title} className="lp-tile">
                <div className="lp-tile-icon">
                  <CapabilityIcon name={item.icon} />
                </div>
                <h3 className="mt-4 font-display text-base font-semibold">
                  {item.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-lp-dim">
                  {item.body}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* —— closing cta ————————————————————————————————————————— */}
      <section className="lp-rule px-6 py-20 md:py-24">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-8 md:flex-row md:items-center">
          <div className="max-w-xl">
            <h2 className="font-display text-3xl font-bold tracking-tight">
              Built to be read, not just run.
            </h2>
            <p className="mt-4 text-base leading-relaxed text-lp-dim">
              Open source, documented down to the trade-offs, and deployed. Start a
              project and trace your first conversation.
            </p>
          </div>
          <Link href={ctaHref} className="lp-cta shrink-0">
            Get started
          </Link>
        </div>
      </section>

      {/* —— footer ————————————————————————————————————————————— */}
      <footer className="lp-rule px-6 py-12">
        <div className="mx-auto grid max-w-6xl gap-10 md:grid-cols-[1.5fr_1fr]">
          <div>
            <p className="font-display text-lg font-bold tracking-tight">
              Orchestra<span className="text-lp-beam">.</span>
            </p>
            <p className="mt-3 max-w-md text-sm leading-relaxed text-lp-dim">
              An AI engineering platform for designing, running, and debugging
              agent pipelines.
            </p>
            <a
              href="https://github.com/BharathiSen/Orchestra"
              target="_blank"
              rel="noreferrer"
              className="lp-link mt-5 inline-flex items-center gap-2 text-sm text-lp-dim transition"
            >
              <GitHubIcon className="h-[1.05rem] w-[1.05rem]" />
              GitHub
            </a>
          </div>
          <div>
            <p className="font-mono text-xs font-medium uppercase tracking-[0.14em] text-lp-dim">
              Links
            </p>
            <ul className="mt-4 space-y-3 text-sm text-lp-dim">
              <li>
                <a href="#capabilities" className="lp-link transition">
                  Capabilities
                </a>
              </li>
              <li>
                <Link href={ctaHref} className="lp-link transition">
                  Open workspace
                </Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="lp-rule mx-auto mt-10 max-w-6xl pt-6 text-sm text-lp-dim">
          © {new Date().getFullYear()} Orchestra · MIT
        </div>
      </footer>
    </main>
  );
}

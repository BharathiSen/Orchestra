type StarterPrompt = {
  label: string;
  prompt: string;
  detail: string;
  /** Which pipeline the prompt is designed to exercise. */
  requires: "orchestra" | "tools" | "any";
};

// Each prompt is chosen to land on a specific path: "compare" matches the full
// route in orchestrator/routing.py, and "847 * 23" matches both the simple
// route and the tool gate in graph/nodes.py.
const STARTER_PROMPTS: StarterPrompt[] = [
  {
    label: "Multi-agent research",
    prompt: "Compare Redis and Postgres for session storage.",
    detail: "Runs the full pipeline — Planner, Research, Writer, Reviewer.",
    requires: "orchestra",
  },
  {
    label: "Tool calling",
    prompt: "What is 847 * 23?",
    detail: "Routes to the calculator tool and shows the call in the trace.",
    requires: "tools",
  },
  {
    label: "Long-term memory",
    prompt: "My favorite language is TypeScript.",
    detail: "Stores a durable fact. Ask what you know about me in a new chat.",
    requires: "any",
  },
];

/** Returns the toggle change needed to run a prompt, or null if it is ready. */
function starterBlockedBy(
  requires: StarterPrompt["requires"],
  enableOrchestra: boolean,
  enableTools: boolean,
): string | null {
  if (requires === "orchestra" && !enableOrchestra) {
    return "Turn Orchestra on";
  }
  if (requires === "tools") {
    if (enableOrchestra) return "Turn Orchestra off";
    if (!enableTools) return "Turn tools on";
  }
  return null;
}

export function ChatEmptyState({
  enableOrchestra,
  enableTools,
  onSelect,
}: {
  enableOrchestra: boolean;
  enableTools: boolean;
  onSelect: (prompt: string) => void;
}) {
  return (
    <div className="mx-auto max-w-2xl py-10">
      <h2 className="text-center font-display text-lg font-semibold text-fg">
        Start a traced conversation
      </h2>
      <p className="mt-1.5 text-center text-sm text-fg-subtle">
        Every turn records its steps, tokens, cost, and latency. Pick a prompt to
        see a pipeline run end to end.
      </p>
      <ul className="mt-6 space-y-2">
        {STARTER_PROMPTS.map((starter) => {
          const blockedBy = starterBlockedBy(
            starter.requires,
            enableOrchestra,
            enableTools,
          );
          return (
            <li key={starter.label}>
              <button
                type="button"
                onClick={() => onSelect(starter.prompt)}
                className="w-full rounded-xl border border-line bg-surface px-4 py-3 text-left transition hover:border-accent hover:shadow-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-semibold tracking-wide text-accent uppercase">
                    {starter.label}
                  </span>
                  {blockedBy && (
                    <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-300">
                      {blockedBy}
                    </span>
                  )}
                </div>
                <p className="mt-1.5 text-sm font-medium text-fg">
                  {starter.prompt}
                </p>
                <p className="mt-1 text-xs text-fg-subtle">{starter.detail}</p>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

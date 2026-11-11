import Link from "next/link";

import type { ToolInfo } from "@/lib/api";

const NAV_LINK =
  "touch-row inline-flex items-center rounded-lg border border-line-strong px-3 text-sm font-medium hover:bg-raised";

export function ChatHeader({
  projectId,
  projectName,
  llmConfigured,
  provider,
  tools,
}: {
  projectId: number;
  projectName: string;
  llmConfigured: boolean;
  provider: string;
  tools: ToolInfo[];
}) {
  return (
    <>
      <header className="mb-3 flex flex-wrap items-start justify-between gap-3 md:mb-4">
        <div className="min-w-0">
          <p className="font-display text-xs font-semibold tracking-[0.2em] text-accent uppercase sm:text-sm">
            Orchestra
          </p>
          <h1 className="mt-1 truncate font-display text-xl font-bold sm:text-2xl md:text-3xl">
            Chat · {projectName}
          </h1>
          <p className="mt-1 hidden text-sm text-fg-muted sm:block">
            Multi-agent Orchestra with Redis conversation memory and long-term
            preferences.
          </p>
        </div>
        <nav className="flex flex-wrap gap-2" aria-label="Project sections">
          <Link href={`/projects/${projectId}`} className={NAV_LINK}>
            Agents
          </Link>
          <Link href={`/projects/${projectId}/knowledge`} className={NAV_LINK}>
            <span className="sm:hidden">Knowledge</span>
            <span className="hidden sm:inline">Knowledge Base</span>
          </Link>
          <Link href={`/projects/${projectId}/observability`} className={NAV_LINK}>
            Observability
          </Link>
          <Link href="/dashboard" className={NAV_LINK}>
            Dashboard
          </Link>
        </nav>
      </header>

      {llmConfigured ? (
        <p className="mb-4 text-xs text-fg-subtle">
          Active provider: <span className="font-medium">{provider}</span>
          {tools.length > 0 && (
            <>
              {" "}
              · Tools:{" "}
              <span className="font-medium">{tools.map((t) => t.name).join(", ")}</span>
            </>
          )}
        </p>
      ) : (
        <p className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
          LLM provider <code>{provider}</code> is not configured. For free testing
          set <code>LLM_PROVIDER=groq</code> and <code>GROQ_API_KEY</code> (or use{" "}
          <code>ollama</code>). For production use <code>LLM_PROVIDER=gemini</code>{" "}
          + <code>GEMINI_API_KEY</code>, then restart the backend.
        </p>
      )}
    </>
  );
}

// Live trace cards rendered inside an assistant message: tool calls, the tools
// graph, the Orchestra agents, and retrieved knowledge-base chunks.

import type {
  GraphNodeName,
  GraphStepEvent,
  OrchestraAgentName,
  OrchestraStepEvent,
  RetrievedChunk,
  ToolEvent,
} from "@/lib/api";

type StepStatus = "running" | "done" | "error" | undefined;

/** Shared label and colour for a pipeline step's state. */
function stepStatus(status: StepStatus): { text: string; className: string } {
  if (status === "running") return { text: "Running…", className: "text-amber-300" };
  if (status === "done") return { text: "✓", className: "text-accent" };
  if (status === "error") return { text: "Error", className: "text-red-300" };
  return { text: "Pending", className: "text-fg-faint" };
}

function toolLabel(name: string): string {
  if (name === "calculator") return "Calculator";
  if (name === "weather") return "Weather";
  if (name === "search") return "Search";
  return name;
}

export function ToolPanel({ tools }: { tools: ToolEvent[] }) {
  if (!tools.length) return null;
  return (
    <div className="mb-2 space-y-1.5">
      {tools.map((t) => (
        <div
          key={t.tool_call_id}
          className="rounded-lg border border-line bg-surface px-3 py-2 text-xs text-fg"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold">{toolLabel(t.tool_name)}</span>
            <span
              className={
                t.status === "running"
                  ? "text-amber-300"
                  : t.status === "error"
                    ? "text-red-300"
                    : "text-accent"
              }
            >
              {t.status === "running"
                ? "Running…"
                : t.status === "error"
                  ? "Error"
                  : "Complete"}
            </span>
          </div>
          {t.result && (
            <p className="mt-1 whitespace-pre-wrap text-[11px] text-fg-muted">
              {t.result.length > 280 ? `${t.result.slice(0, 277)}…` : t.result}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

const GRAPH_NODE_LABELS: Record<GraphNodeName, string> = {
  planner: "Planner",
  tool: "Tool",
  reviewer: "Reviewer",
  answer: "Final Answer",
};
const GRAPH_NODE_ORDER: GraphNodeName[] = ["planner", "tool", "reviewer", "answer"];

export function GraphExecutionPanel({ steps }: { steps: GraphStepEvent[] }) {
  if (!steps.length) return null;
  const latestByNode = new Map<GraphNodeName, GraphStepEvent>();
  for (const step of steps) {
    latestByNode.set(step.node, step);
  }

  return (
    <div className="mb-2 rounded-lg border border-line bg-surface px-3 py-2 text-xs text-fg">
      <p className="mb-1 font-semibold text-fg">Execution</p>
      <div className="space-y-1.5">
        {GRAPH_NODE_ORDER.map((node) => {
          const step = latestByNode.get(node);
          const { text, className } = stepStatus(step?.status);
          return (
            <div key={node}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{GRAPH_NODE_LABELS[node]}</span>
                <span className={className}>{text}</span>
              </div>
              {step?.summary && (
                <p className="mt-0.5 text-[11px] text-fg-subtle">{step.summary}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const AGENT_LABELS: Record<OrchestraAgentName, string> = {
  planner: "Planner",
  research: "Research",
  writer: "Writer",
  reviewer: "Reviewer",
  fast_answer: "Fast Answer",
};

export function OrchestraExecutionPanel({ steps }: { steps: OrchestraStepEvent[] }) {
  if (!steps.length) return null;
  const route = steps.find((s) => s.route)?.route;
  const ordered: OrchestraAgentName[] =
    route === "simple"
      ? ["planner", "research", "fast_answer"]
      : ["planner", "research", "writer", "reviewer"];
  const latest = new Map<OrchestraAgentName, OrchestraStepEvent>();
  for (const step of steps) {
    latest.set(step.agent, step);
  }

  return (
    <div className="mb-2 rounded-lg border border-indigo-400/30 bg-indigo-500/10 px-3 py-2 text-xs text-fg">
      <p className="mb-1.5 font-semibold text-indigo-200">
        Agent Execution{route ? ` · ${route}` : ""}
      </p>
      <div className="space-y-1.5">
        {ordered.map((agent, idx) => {
          const step = latest.get(agent);
          const { text, className } = stepStatus(step?.status);
          return (
            <div key={agent}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{AGENT_LABELS[agent]}</span>
                <span className={className}>{text}</span>
              </div>
              {step?.summary && (
                <p className="mt-0.5 text-[11px] text-fg-subtle">{step.summary}</p>
              )}
              {idx < ordered.length - 1 && (
                <p className="text-[10px] text-fg-faint">↓</p>
              )}
            </div>
          );
        })}
        {(latest.get("reviewer")?.status === "done" ||
          latest.get("fast_answer")?.status === "done") && (
          <p className="pt-1 font-semibold text-accent">↓ Done</p>
        )}
      </div>
    </div>
  );
}

export function RetrievedContextPanel({ chunks }: { chunks: RetrievedChunk[] }) {
  if (!chunks.length) return null;
  return (
    <div className="mb-2 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-xs text-fg">
      <p className="mb-1.5 font-semibold text-emerald-300">
        Retrieved Sources ({chunks.length})
      </p>
      <div className="space-y-1.5">
        {chunks.map((chunk) => (
          <div key={chunk.chunk_id} className="rounded-md border border-emerald-500/25 bg-surface px-2 py-1.5">
            <p className="font-medium text-fg">
              ✓ Chunk {chunk.chunk_index + 1} · {chunk.document_name}
              {typeof chunk.score === "number" && (
                <span className="ml-1.5 font-normal text-fg-subtle">
                  ({chunk.score.toFixed(3)})
                </span>
              )}
            </p>
            <p className="mt-0.5 line-clamp-2 text-[11px] text-fg-muted">
              {chunk.content}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

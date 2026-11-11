// Pure updates applied to the in-flight assistant message as SSE events arrive.
// Each returns a patch; `patchMessage` applies it to the one message it targets.

import type {
  GraphStepEvent,
  OrchestraStepEvent,
  RetrievedChunk,
  ToolEvent,
} from "@/lib/api";

import type { UiMessage } from "./types";

/** Placeholder content shown in the assistant bubble until the first token. */
export const PENDING_CONTENT = "…";

type Patch = (message: UiMessage) => UiMessage;

export function patchMessage(
  messages: UiMessage[],
  id: string,
  patch: Patch,
): UiMessage[] {
  return messages.map((m) => (m.id === id ? patch(m) : m));
}

export const withToolStarted =
  (tool: ToolEvent): Patch =>
  (m) => ({
    ...m,
    tools: [...(m.tools || []).filter((t) => t.tool_call_id !== tool.tool_call_id), tool],
  });

export const withToolResult =
  (tool: ToolEvent): Patch =>
  (m) => ({
    ...m,
    tools: (m.tools || []).map((t) =>
      t.tool_call_id === tool.tool_call_id ? { ...t, ...tool } : t,
    ),
  });

export const withRetrievedChunks =
  (chunks: RetrievedChunk[]): Patch =>
  (m) => ({ ...m, retrievedChunks: chunks });

// Steps are re-sent as they change state; drop an exact repeat, keep progress.
export const withGraphStep =
  (step: GraphStepEvent): Patch =>
  (m) => ({
    ...m,
    graphSteps: [
      ...(m.graphSteps || []).filter(
        (s) => !(s.node === step.node && s.status === step.status && s.summary === step.summary),
      ),
      step,
    ],
  });

export const withOrchestraStep =
  (step: OrchestraStepEvent): Patch =>
  (m) => ({
    ...m,
    orchestraSteps: [
      ...(m.orchestraSteps || []).filter(
        (s) =>
          !(s.agent === step.agent && s.status === step.status && s.summary === step.summary),
      ),
      step,
    ],
  });

export const withToken =
  (text: string): Patch =>
  (m) => ({
    ...m,
    content: m.content === PENDING_CONTENT ? text : m.content + text,
  });

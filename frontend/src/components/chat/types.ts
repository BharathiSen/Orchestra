import type {
  ChatMessage,
  GraphStepEvent,
  OrchestraStepEvent,
  RetrievedChunk,
  ToolEvent,
} from "@/lib/api";

export type UiMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  retrievedChunks?: RetrievedChunk[];
  tools?: ToolEvent[];
  graphSteps?: GraphStepEvent[];
  orchestraSteps?: OrchestraStepEvent[];
};

/** Trace extras for one conversation that the message history API does not return. */
export type ConversationExtras = {
  retrievedChunks: RetrievedChunk[];
  tools: ToolEvent[];
  graphSteps: GraphStepEvent[];
  orchestraSteps: OrchestraStepEvent[];
};

export const EMPTY_EXTRAS: ConversationExtras = {
  retrievedChunks: [],
  tools: [],
  graphSteps: [],
  orchestraSteps: [],
};

/**
 * Turn stored rows into UI messages. Persisted traces come from the message
 * itself; live extras from the current session win for the latest assistant
 * turn, so a reload right after a stream does not drop its panels.
 */
export function attachExtrasToMessages(
  rows: ChatMessage[],
  extras: ConversationExtras | undefined,
): UiMessage[] {
  const filtered = rows.filter((m) => m.role === "user" || m.role === "assistant");
  const lastAssistantIdx = filtered.map((x) => x.role).lastIndexOf("assistant");
  return filtered.map((m, idx) => {
    const isLastAssistant = m.role === "assistant" && idx === lastAssistantIdx;
    const persisted = m.trace || null;
    const retrieved =
      (isLastAssistant && extras?.retrievedChunks?.length
        ? extras.retrievedChunks
        : undefined) ||
      persisted?.retrieved_chunks ||
      undefined;
    const tools =
      (isLastAssistant && extras?.tools?.length ? extras.tools : undefined) ||
      persisted?.tools ||
      undefined;
    const graphSteps =
      (isLastAssistant && extras?.graphSteps?.length
        ? extras.graphSteps
        : undefined) ||
      persisted?.graph_steps ||
      undefined;
    const orchestraSteps =
      (isLastAssistant && extras?.orchestraSteps?.length
        ? extras.orchestraSteps
        : undefined) ||
      persisted?.orchestra_steps ||
      undefined;
    return {
      id: String(m.id),
      role: m.role as "user" | "assistant",
      content: m.content,
      retrievedChunks: retrieved?.length ? retrieved : undefined,
      tools: tools?.length ? tools : undefined,
      graphSteps: graphSteps?.length ? graphSteps : undefined,
      orchestraSteps: orchestraSteps?.length ? orchestraSteps : undefined,
    };
  });
}

import { useEffect, useRef } from "react";

import { ChatEmptyState } from "./ChatEmptyState";
import { MessageBody } from "./MessageBody";
import {
  GraphExecutionPanel,
  OrchestraExecutionPanel,
  RetrievedContextPanel,
  ToolPanel,
} from "./TracePanels";
import type { UiMessage } from "./types";

export function MessageList({
  messages,
  sending,
  enableOrchestra,
  enableTools,
  onSelectStarter,
}: {
  messages: UiMessage[];
  sending: boolean;
  enableOrchestra: boolean;
  enableTools: boolean;
  onSelectStarter: (prompt: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  return (
    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
      {messages.length === 0 && (
        <ChatEmptyState
          enableOrchestra={enableOrchestra}
          enableTools={enableTools}
          onSelect={onSelectStarter}
        />
      )}
      {messages.map((m) => (
        <div
          key={m.id}
          className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
            m.role === "user" ? "ml-auto bg-fg text-ground" : "bg-raised text-fg"
          }`}
        >
          <p className="mb-1 text-[10px] font-semibold tracking-wide uppercase opacity-70">
            {m.role}
          </p>
          {m.role === "assistant" && m.orchestraSteps && m.orchestraSteps.length > 0 && (
            <OrchestraExecutionPanel steps={m.orchestraSteps} />
          )}
          {m.role === "assistant" && m.retrievedChunks && m.retrievedChunks.length > 0 && (
            <RetrievedContextPanel chunks={m.retrievedChunks} />
          )}
          {m.role === "assistant" && m.graphSteps && m.graphSteps.length > 0 && (
            <GraphExecutionPanel steps={m.graphSteps} />
          )}
          {m.role === "assistant" && m.tools && m.tools.length > 0 && (
            <ToolPanel tools={m.tools} />
          )}
          {m.content ? (
            <MessageBody role={m.role} content={m.content} />
          ) : sending ? (
            <span className="text-fg-faint" aria-label="Assistant is responding">
              …
            </span>
          ) : null}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

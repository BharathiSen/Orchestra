import type { Agent, ChatModel } from "@/lib/api";

/** Model, agent, temperature, and pipeline toggles above the message list. */
export function ChatControls({
  models,
  model,
  onModelChange,
  agents,
  agentId,
  onAgentChange,
  temperature,
  onTemperatureChange,
  enableOrchestra,
  onOrchestraChange,
  enableTools,
  onToolsChange,
  sidebarOpen,
  onOpenSidebar,
}: {
  models: ChatModel[];
  model: string;
  onModelChange: (model: string) => void;
  agents: Agent[];
  agentId: number | "";
  onAgentChange: (agentId: number | "") => void;
  temperature: number;
  onTemperatureChange: (temperature: number) => void;
  enableOrchestra: boolean;
  onOrchestraChange: (on: boolean) => void;
  enableTools: boolean;
  onToolsChange: (on: boolean) => void;
  sidebarOpen: boolean;
  onOpenSidebar: () => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-2 border-b border-line p-3 sm:gap-3">
      <button
        type="button"
        onClick={onOpenSidebar}
        aria-expanded={sidebarOpen}
        aria-controls="conversation-drawer"
        className="touch-row inline-flex items-center gap-2 rounded-lg border border-line-strong px-3 text-sm font-medium hover:bg-raised lg:hidden"
      >
        <span aria-hidden className="text-base leading-none">☰</span>
        Chats
      </button>
      <label className="text-xs text-fg-muted">
        Model
        <select
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          className="touch-row mt-1 block rounded-lg border border-line-strong px-2 text-sm"
        >
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </label>
      <label className="text-xs text-fg-muted">
        Agent (system prompt)
        <select
          value={agentId}
          onChange={(e) => onAgentChange(e.target.value ? Number(e.target.value) : "")}
          className="touch-row mt-1 block max-w-[220px] rounded-lg border border-line-strong px-2 text-sm"
        >
          <option value="">Default mentor prompt</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
              {a.knowledge_base_ids && a.knowledge_base_ids.length > 0 ? " · KB" : ""}
            </option>
          ))}
        </select>
      </label>
      <label className="touch-row flex flex-col justify-center text-xs text-fg-muted">
        Temperature ({temperature.toFixed(1)})
        <input
          type="range"
          min={0}
          max={1.5}
          step={0.1}
          value={temperature}
          onChange={(e) => onTemperatureChange(Number(e.target.value))}
          aria-label={`Temperature ${temperature.toFixed(1)}`}
          className="mt-2 block h-6 w-40 cursor-pointer"
        />
      </label>
      <label className="touch-row inline-flex items-center gap-2 rounded-lg border-2 border-indigo-400 bg-indigo-500/10 px-3 text-sm font-semibold text-indigo-200">
        <input
          type="checkbox"
          checked={enableOrchestra}
          onChange={(e) => onOrchestraChange(e.target.checked)}
          className="h-5 w-5"
        />
        Orchestra {enableOrchestra ? "(ON)" : "(OFF)"}
      </label>
      <label
        className={`touch-row inline-flex items-center gap-2 rounded-lg border-2 px-3 text-sm font-semibold ${
          enableOrchestra
            ? "border-line bg-raised text-fg-faint"
            : "border-accent bg-accent/10 text-accent"
        }`}
      >
        <input
          type="checkbox"
          checked={enableTools}
          disabled={enableOrchestra}
          onChange={(e) => onToolsChange(e.target.checked)}
          className="h-5 w-5"
        />
        Tools {enableTools ? "(ON)" : "(OFF)"}
      </label>
    </div>
  );
}

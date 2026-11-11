import type { MemoryStatus, UserMemoryItem } from "@/lib/api";

export type PreferenceDraft = { key: string; value: string };

export function MemoryPanel({
  status,
  preferences,
  onSavePreference,
  prefDraft,
  setPrefDraft,
  savingPref,
}: {
  status: MemoryStatus | null;
  preferences: UserMemoryItem[];
  onSavePreference: () => void;
  prefDraft: PreferenceDraft;
  setPrefDraft: (v: PreferenceDraft) => void;
  savingPref: boolean;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface px-3 py-2.5 text-xs text-fg">
      <p className="mb-2 font-semibold text-fg">Memory Panel</p>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        <span className="text-fg-subtle">Conversation</span>
        <span className="font-medium">
          Memory Size {status?.memory_size ?? 0} / {status?.buffer_limit ?? 10}
        </span>
        <span className="text-fg-subtle">Session</span>
        <span className="font-medium">
          {status?.session_active ? "Active" : "Idle"}
        </span>
        <span className="text-fg-subtle">Redis</span>
        <span
          className={
            status?.redis_connected
              ? "font-medium text-accent"
              : "font-medium text-amber-300"
          }
        >
          {status?.redis_connected ? "Connected" : "Offline"}
        </span>
        <span className="text-fg-subtle">Memory Used</span>
        <span className="font-medium">{status?.memory_used ? "✓ Yes" : "No"}</span>
        <span className="text-fg-subtle">Summary</span>
        <span className="font-medium">
          {status?.has_summary ? "✓ Compressed" : "—"}
        </span>
        <span className="text-fg-subtle">Long-term</span>
        <span className="font-medium">{status?.long_term_count ?? 0} facts</span>
      </div>

      {preferences.length > 0 && (
        <ul className="mt-2 space-y-1 border-t border-line pt-2">
          {preferences.slice(0, 5).map((p) => (
            <li key={p.id} className="truncate text-[11px] text-fg-muted">
              <span className="font-medium text-fg">{p.key}</span>: {p.value}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-2 space-y-1.5 border-t border-line pt-2">
        <p className="font-medium text-fg">Add preference</p>
        <input
          value={prefDraft.key}
          onChange={(e) => setPrefDraft({ ...prefDraft, key: e.target.value })}
          placeholder="e.g. preferred_language"
          aria-label="Preference name"
          className="w-full rounded-md border border-line-strong px-2 py-1 text-[11px]"
        />
        <input
          value={prefDraft.value}
          onChange={(e) => setPrefDraft({ ...prefDraft, value: e.target.value })}
          placeholder="e.g. Python"
          aria-label="Preference value"
          className="w-full rounded-md border border-line-strong px-2 py-1 text-[11px]"
        />
        <button
          type="button"
          disabled={savingPref || !prefDraft.key.trim() || !prefDraft.value.trim()}
          onClick={onSavePreference}
          className="rounded-md bg-fg px-2 py-1 text-[11px] font-medium text-ground disabled:opacity-50"
        >
          {savingPref ? "Saving…" : "Save to long-term memory"}
        </button>
      </div>
    </div>
  );
}

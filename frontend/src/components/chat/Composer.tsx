import type { FormEvent } from "react";

export function Composer({
  value,
  onChange,
  onSubmit,
  sending,
  enableOrchestra,
  enableTools,
  showReplayBanner,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  sending: boolean;
  enableOrchestra: boolean;
  enableTools: boolean;
  showReplayBanner: boolean;
}) {
  return (
    // sticky + pb-safe keeps the composer above the iOS home indicator and the
    // Android gesture bar; the page is h-dvh so it never sits under a
    // collapsing browser chrome.
    <form
      onSubmit={onSubmit}
      className="pb-safe sticky bottom-0 z-10 border-t border-line bg-surface/95 px-3 pt-3 backdrop-blur"
    >
      {showReplayBanner && (
        <p className="mb-2 rounded-lg border border-accent/30 bg-accent/10 px-3 py-2 text-xs text-accent">
          Replay loaded — same prompt and pipeline flags are ready. Press Send to
          re-run, then compare in Observability.
        </p>
      )}
      <div className="flex items-end gap-2">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          placeholder={
            enableOrchestra
              ? "Ask something that needs multiple agents…"
              : enableTools
                ? "Ask something that needs a tool…"
                : "Ask anything…"
          }
          aria-label="Message"
          className="min-h-[48px] flex-1 rounded-xl border border-line-strong px-3 py-2 text-base outline-none ring-accent focus:ring-2 sm:text-sm"
          disabled={sending}
        />
        <button
          type="submit"
          disabled={sending || !value.trim()}
          className="touch-target inline-flex items-center justify-center rounded-xl bg-accent px-5 text-sm font-semibold text-ground hover:brightness-110 disabled:opacity-60"
        >
          {sending ? "…" : "Send"}
        </button>
      </div>
    </form>
  );
}

"use client";

import { useBackendStatus } from "@/lib/warm";

/**
 * Explains a slow first sign-in instead of leaving the visitor staring at a
 * spinner. Silent when the backend answers promptly — it only speaks up when
 * the hosted instance is waking from sleep, once it is up, or if it is down.
 */
export function BackendStatusNotice() {
  const status = useBackendStatus();

  if (status === "waking") {
    return (
      <p
        role="status"
        aria-live="polite"
        className="mb-3 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300"
      >
        <span
          aria-hidden
          className="mt-1 inline-block h-2 w-2 shrink-0 animate-pulse rounded-full bg-amber-300"
        />
        <span>
          Waking up the backend — the free hosting tier sleeps when idle, so the
          first request can take a minute or more. You can sign in now; it will go
          through as soon as the server is up.
        </span>
      </p>
    );
  }

  if (status === "awake") {
    return (
      <p
        role="status"
        aria-live="polite"
        className="mb-3 rounded-lg border border-accent/30 bg-accent/10 px-3 py-2 text-xs text-accent"
      >
        Backend is awake.
      </p>
    );
  }

  if (status === "unreachable") {
    return (
      <p
        role="status"
        aria-live="polite"
        className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300"
      >
        Can&apos;t reach the backend right now. Check your connection, or try again
        in a moment.
      </p>
    );
  }

  return null;
}

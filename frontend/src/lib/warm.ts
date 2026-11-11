// Kept out of lib/api.ts on purpose: the landing page imports this, and pulling
// the whole API client into it cost ~2 kB of JavaScript for one fetch.

import { useSyncExternalStore } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** How long a healthy backend gets before we tell the visitor it is booting. */
const SLOW_AFTER_MS = 1500;

/**
 * idle        — no ping sent yet
 * checking    — ping sent, under SLOW_AFTER_MS
 * waking      — still no answer: the hosted backend is booting from sleep
 * ready       — the backend answered promptly
 * awake       — the backend answered after having been "waking"
 * unreachable — the request failed outright (offline, DNS, server down)
 */
export type BackendStatus =
  | "idle"
  | "checking"
  | "waking"
  | "ready"
  | "awake"
  | "unreachable";

let status: BackendStatus = "idle";
const listeners = new Set<() => void>();

function setStatus(next: BackendStatus) {
  status = next;
  for (const listener of listeners) listener();
}

/**
 * Fire-and-forget request that starts waking the backend.
 *
 * The hosted backend sleeps when idle, and the first request after that waits
 * for it to boot. Calling this from the landing and login pages starts the boot
 * while the visitor is still reading or typing, instead of after they press
 * "Sign in". `/health/live` checks nothing external, so it is the cheapest
 * request that still wakes the instance. Once per tab.
 *
 * `no-cors`: only "did the server answer" matters, not the body. An opaque
 * response still resolves when the server replies, so a CORS mismatch (e.g. a
 * local build pointed at the hosted API) is not misreported as "unreachable".
 */
export function warmBackend(): void {
  if (status !== "idle" || typeof window === "undefined") return;
  setStatus("checking");
  const slowTimer = window.setTimeout(() => {
    if (status === "checking") setStatus("waking");
  }, SLOW_AFTER_MS);
  fetch(`${API_URL}/health/live`, { cache: "no-store", mode: "no-cors" })
    .then(() => setStatus(status === "waking" ? "awake" : "ready"))
    .catch(() => setStatus("unreachable"))
    .finally(() => window.clearTimeout(slowTimer));
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** The wake-up ping's progress, for showing a "waking up" notice. */
export function useBackendStatus(): BackendStatus {
  return useSyncExternalStore(subscribe, () => status, () => "idle");
}

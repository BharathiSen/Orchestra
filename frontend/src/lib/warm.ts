// Kept out of lib/api.ts on purpose: the landing page imports this, and pulling
// the whole API client into it cost ~2 kB of JavaScript for one fetch.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let backendWarmed = false;

/**
 * Fire-and-forget request that starts waking the backend.
 *
 * The hosted backend sleeps when idle, and the first request after that waits
 * for it to boot. Calling this from the landing and login pages starts the boot
 * while the visitor is still reading or typing, instead of after they press
 * "Sign in". `/health/live` checks nothing external, so it is the cheapest
 * request that still wakes the instance. Once per tab; failures are ignored.
 */
export function warmBackend(): void {
  if (backendWarmed || typeof window === "undefined") return;
  backendWarmed = true;
  void fetch(`${API_URL}/health/live`, { cache: "no-store" }).catch(() => {});
}

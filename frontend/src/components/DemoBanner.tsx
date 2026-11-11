"use client";

import { useSession } from "@/lib/auth";

const DEMO_EMAIL = (process.env.NEXT_PUBLIC_DEMO_EMAIL || "").trim().toLowerCase();

/**
 * Shown only while signed in as the shared demo account.
 *
 * Deliberately does not claim the workspace is read-only — the demo account can
 * create projects and send messages, and labelling it read-only would be false.
 * What visitors actually need to know is that the workspace is shared and its
 * contents are not durable.
 *
 * Rendered from the root layout so it survives navigation without waiting for
 * the application shell that arrives in a later milestone.
 */
export default function DemoBanner() {
  // Subscribed, so the banner appears on demo sign-in and disappears on
  // log-out without a reload. (It used to be read once, when the root layout
  // first mounted, so a client-side sign-in never showed it.)
  const { user } = useSession();
  const isDemo =
    Boolean(DEMO_EMAIL) && user?.email?.trim().toLowerCase() === DEMO_EMAIL;

  if (!isDemo) return null;

  return (
    <div
      role="status"
      className="border-b border-amber-500/30 bg-amber-500/15 px-4 py-2 text-center text-xs text-amber-300"
    >
      <span className="font-semibold">Demo workspace</span> — shared with everyone
      trying Orchestra. Anything you create here is visible to others and may be
      reset at any time.
    </div>
  );
}

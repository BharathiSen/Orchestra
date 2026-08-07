"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { ApiError, api } from "@/lib/api";
import { getToken, saveSession } from "@/lib/auth";

const DEMO_EMAIL = (process.env.NEXT_PUBLIC_DEMO_EMAIL || "").trim();
const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD || "";
const DEMO_ENABLED = Boolean(DEMO_EMAIL && DEMO_PASSWORD);

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getToken()) {
      router.replace("/dashboard");
    }
  }, [router]);

  const signInAsDemo = useCallback(async () => {
    if (!DEMO_ENABLED) return;
    setError(null);
    setLoading(true);
    setMode("login");
    setEmail(DEMO_EMAIL);
    setPassword(DEMO_PASSWORD);
    try {
      const result = await api.login({ email: DEMO_EMAIL, password: DEMO_PASSWORD });
      saveSession(result.access_token, result.user);
      router.push("/dashboard");
    } catch (err) {
      // Leave the credentials filled in so the visitor can retry manually
      // rather than being dropped on an empty form.
      setError(
        err instanceof ApiError
          ? `Demo sign-in failed: ${err.message}`
          : "Demo sign-in failed. Try the credentials below.",
      );
      setLoading(false);
    }
  }, [router]);

  // Arriving from the landing page's "Try the demo" button signs in directly.
  // Read from the URL rather than useSearchParams: this is a client-only
  // concern, and useSearchParams would force a Suspense boundary at build time.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (new URLSearchParams(window.location.search).get("demo") !== "1") return;
    if (getToken()) return;
    void signInAsDemo();
  }, [signInAsDemo]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result =
        mode === "login"
          ? await api.login({ email, password })
          : await api.signup({
              email,
              password,
              full_name: fullName || undefined,
            });
      saveSession(result.access_token, result.user);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-5xl items-center px-6 py-12">
      <section className="grid w-full gap-10 md:grid-cols-2 md:items-center">
        <div>
          <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
            Orchestra
          </p>
          <h1 className="mt-3 font-display text-4xl font-bold leading-tight text-ink md:text-5xl">
            Build the platform before the agents.
          </h1>
          <p className="mt-4 max-w-md text-base text-slate-600">
            Sign in to manage projects, agents, and chat with tool-powered
            assistants in your AI engineering workspace.
          </p>
          <Link href="/" className="mt-6 inline-block text-sm font-medium text-accent hover:underline">
            ← Back to landing
          </Link>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-2xl border border-slate-200 bg-white/80 p-6 shadow-sm backdrop-blur"
        >
          <div className="mb-6 flex gap-2">
            <button
              type="button"
              onClick={() => setMode("login")}
              className={`rounded-lg px-3 py-2 text-sm font-medium ${
                mode === "login"
                  ? "bg-ink text-white"
                  : "bg-slate-100 text-slate-600"
              }`}
            >
              Login
            </button>
            <button
              type="button"
              onClick={() => setMode("signup")}
              className={`rounded-lg px-3 py-2 text-sm font-medium ${
                mode === "signup"
                  ? "bg-ink text-white"
                  : "bg-slate-100 text-slate-600"
              }`}
            >
              Sign up
            </button>
          </div>

          {mode === "signup" && (
            <label className="mb-3 block text-sm">
              <span className="mb-1 block text-slate-600">Full name</span>
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
                placeholder="Ada Lovelace"
              />
            </label>
          )}

          <label className="mb-3 block text-sm">
            <span className="mb-1 block text-slate-600">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
              placeholder="you@example.com"
            />
          </label>

          <label className="mb-4 block text-sm">
            <span className="mb-1 block text-slate-600">Password</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-accent focus:ring-2"
              placeholder="At least 8 characters"
            />
          </label>

          {error && (
            <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60"
          >
            {loading ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
          </button>

          {DEMO_ENABLED && mode === "login" && (
            <div className="mt-5 border-t border-slate-200 pt-4">
              <button
                type="button"
                onClick={() => void signInAsDemo()}
                disabled={loading}
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-semibold transition hover:border-accent hover:text-accent disabled:opacity-60"
              >
                Sign in to the demo workspace
              </button>
              <p className="mt-2 text-center text-xs text-slate-500">
                Shared account — <span className="font-medium">{DEMO_EMAIL}</span>.
                Data may be reset at any time.
              </p>
            </div>
          )}

          <p className="mt-4 text-center text-xs text-slate-500">
            After login you land on the{" "}
            <Link href="/dashboard" className="text-accent underline">
              dashboard
            </Link>
            .
          </p>
        </form>
      </section>
    </main>
  );
}

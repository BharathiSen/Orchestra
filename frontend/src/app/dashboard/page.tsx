"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, type User } from "@/lib/api";
import { clearSession, getStoredUser, getToken } from "@/lib/auth";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    const cached = getStoredUser();
    if (cached) setUser(cached);

    api
      .me(token)
      .then((me) => setUser(me))
      .catch(() => {
        clearSession();
        router.replace("/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

  function logout() {
    clearSession();
    router.replace("/login");
  }

  if (loading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-6">
        <p className="text-slate-500">Loading workspace...</p>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <header className="mb-10 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
            Orchestra
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold">Dashboard</h1>
          <p className="mt-1 text-slate-600">
            Welcome{user?.full_name ? `, ${user.full_name}` : ""} — platform foundation is live.
          </p>
        </div>
        <button
          onClick={logout}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-white"
        >
          Log out
        </button>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-slate-200 bg-white/80 p-6">
          <h2 className="font-display text-xl font-semibold">Projects</h2>
          <p className="mt-2 text-sm text-slate-600">
            Create and manage workspaces that will later hold agents, tools, and
            knowledge bases.
          </p>
          <Link
            href="/projects"
            className="mt-4 inline-flex rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
          >
            Open projects
          </Link>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white/80 p-6">
          <h2 className="font-display text-xl font-semibold">Account</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Email</dt>
              <dd className="font-medium">{user?.email}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">User ID</dt>
              <dd className="font-medium">{user?.id}</dd>
            </div>
          </dl>
        </article>
      </section>
    </main>
  );
}

import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col items-center justify-center px-6 py-16 text-center">
      <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent uppercase">
        Orchestra
      </p>
      <h1 className="mt-4 font-display text-5xl font-bold text-ink">404</h1>
      <p className="mt-3 max-w-md text-slate-600">
        This page is not part of the score. Head back to the landing page or your
        dashboard.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-4">
        <Link
          href="/"
          className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-700"
        >
          Landing
        </Link>
        <Link
          href="/dashboard"
          className="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-semibold text-ink hover:border-accent hover:text-accent"
        >
          Dashboard
        </Link>
      </div>
    </main>
  );
}

"use client";

import { useEffect } from "react";

export default function ErrorPage({
  error,
  reset,
}: Readonly<{ error: Error & { digest?: string }; reset: () => void }>) {
  useEffect(() => {
    console.error("InsightHR page rendering failed", error.name);
  }, [error]);

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-6 text-slate-950">
      <section className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-semibold text-red-700">Page unavailable</p>
        <h1 className="mt-2 text-2xl font-semibold">InsightHR could not load this page.</h1>
        <p className="mt-3 text-slate-600">Try the request again. No data has been changed.</p>
        <button
          className="mt-6 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white outline-none hover:bg-slate-700 focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
          onClick={reset}
          type="button"
        >
          Try again
        </button>
      </section>
    </main>
  );
}


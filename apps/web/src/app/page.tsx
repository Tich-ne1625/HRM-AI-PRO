import { getApiStatus } from "../features/system-status/api";
import { SystemStatus } from "../features/system-status/system-status";

export default async function HomePage() {
  const apiStatus = await getApiStatus();

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-12 text-slate-950 sm:px-10 lg:px-16">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-12">
        <header className="flex items-center justify-between border-b border-slate-200 pb-6">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-700">
              InsightHR
            </p>
            <p className="mt-1 text-sm text-slate-600">Performance management platform</p>
          </div>
          <span className="rounded-full bg-slate-900 px-3 py-1.5 text-xs font-medium text-white">
            Foundation
          </span>
        </header>

        <section className="grid items-start gap-10 lg:grid-cols-[1.4fr_0.8fr]">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold text-blue-700">Phase 1</p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
              A reliable foundation for fair, explainable performance reviews.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
              The web application, API, migrations, and PostgreSQL readiness checks are wired
              together. Employee workflows and authentication will be added in the next phases.
            </p>
          </div>

          <SystemStatus status={apiStatus} />
        </section>

        <section aria-labelledby="foundation-heading" className="border-t border-slate-200 pt-8">
          <h2 id="foundation-heading" className="text-sm font-semibold text-slate-900">
            Foundation services
          </h2>
          <dl className="mt-5 grid gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 sm:grid-cols-3">
            {[
              ["Web", "Next.js App Router"],
              ["API", "FastAPI modular monolith"],
              ["Data", "PostgreSQL with Alembic"],
            ].map(([term, description]) => (
              <div className="bg-white p-5" key={term}>
                <dt className="text-sm text-slate-500">{term}</dt>
                <dd className="mt-1 font-medium text-slate-900">{description}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </main>
  );
}


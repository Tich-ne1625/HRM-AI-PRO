import type { ApiStatus } from "./api";

export function SystemStatus({ status }: Readonly<{ status: ApiStatus }>) {
  const available = status.kind === "available";

  return (
    <aside
      aria-labelledby="system-status-heading"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div className="flex items-center justify-between gap-4">
        <h2 id="system-status-heading" className="font-semibold text-slate-900">
          System status
        </h2>
        <span
          aria-hidden="true"
          className={`h-2.5 w-2.5 rounded-full ${available ? "bg-emerald-500" : "bg-amber-500"}`}
        />
      </div>
      <p className={`mt-5 text-lg font-semibold ${available ? "text-emerald-700" : "text-amber-700"}`}>
        {available ? "API connected" : "API unavailable"}
      </p>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        {available
          ? "The FastAPI process is responding. Database readiness is monitored separately by the API."
          : "The page remains available while the API is offline. Check the backend service and try again."}
      </p>
    </aside>
  );
}


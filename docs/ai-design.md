# AI design status

Phases 1–6 are implemented; Gemini integration remains absent. No model name, API key, prompt, provider SDK, background call, or placeholder analysis is present in the running applications. The [Phase 7 contract](phase-7-contract.md) and [eight-task implementation plan](superpowers/plans/2026-10-22-phase-7-gemini.md) were prepared on 2026-10-22; this is a plan, not runtime acceptance.

The implemented boundary:

- An authorized HR user must explicitly request generation or regeneration.
- Deterministic KPI, feedback, and final scores remain independent of Gemini.
- The input excludes names, email addresses, reviewer identities, credentials, and unnecessary personal information.
- PUBLIC advice uses numerical evidence and confidentiality-filtered aggregates without comments. HR_PRIVATE is a separate HR-only generation/read path for sanitized comments from the exact calculation revision. Private-derived output is never reused in a public response.
- Feedback comments are treated as untrusted evidence and sanitized before transmission in HR_PRIVATE only. Redaction is best effort; fictional data is used for live smoke.
- Gemini receives no tools and no authority to modify scores, users, permissions, employees, KPIs, or reviews.
- The six-field structured response is strictly validated before a successful result is persisted.
- Provider timeout, invalid JSON, schema errors, quota errors, and stale evidence never break the numeric review workflow.
- Saved analyses record model, prompt version, calculation version, evidence hash, generation timestamp, and advisory status.

The operator selects the model through GEMINI_MODEL; enabled configuration requires both a model and a secret key. No model name will be hard-coded in business logic.

The implementation uses a short reservation transaction, release locks and DB connections for the bounded provider request, then revalidate authorization, evidence/calculation versions and a fenced lease in a short completion transaction. Idempotency, a single RUNNING attempt per review and a cooldown limit duplicate calls. Crashes cannot guarantee exactly-once external billing. Finalized/CLOSED numeric reviews may receive advisory analyses without reopening evidence.

The [official Python SDK documentation](https://googleapis.github.io/python-genai/), [structured-output contract](https://ai.google.dev/gemini-api/docs/structured-output) and [model catalog](https://ai.google.dev/gemini-api/docs/models) were checked for planning. The locked SDK is google-genai 2.32.0. Its generate_content structured-JSON method uses a 20-second default total deadline and an SDK timeout in milliseconds; HttpRetryOptions(attempts=1) disables retries. Real SDK transport tests run offline through MockTransport. Both async and sync client resources close in finally. No model alias is pinned or claimed live-verified. Server-side strict validation remains required. Default deployment/CI stays keyless and offline; live provider acceptance is recorded separately when explicitly configured and exercised.


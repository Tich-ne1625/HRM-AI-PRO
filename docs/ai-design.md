# AI design status

2026-11-25 planning update: [Phase 13 contextual coaching](superpowers/plans/2026-11-25-phase-13-contextual-ai-coaching.md) and its [draft contract](phase-13-contract.vi.md) add a proposed private conversation workflow using Phase 11–12 work/progress data. It is not implemented. Existing review-based generation below remains unchanged. Coaching will use a separate schema/module, owner and current-scope authorization, bounded server-selected history, source manifests, fenced attempts and explicit handoffs; HR receives coordination metadata only. Current runtime head remains `20261125_0012`.

Phases 1–10 are implemented. Optional Gemini generation, saved advice and separate PUBLIC/HR_PRIVATE audiences are available. HR explicitly requests generation; model/key are configured by the operator. See the [Phase 7 contract](phase-7-contract.md), [implementation plan and acceptance](superpowers/plans/2026-10-22-phase-7-gemini.md), and [Phase 10 delivery report](phase-10-report.vi.md). For a plain-language explanation of who creates and reads advice, see the [Vietnamese role and workflow guide](vai-tro-va-quy-trinh.vi.md).

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


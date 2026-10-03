# AI design status

Gemini integration is intentionally absent from Phase 1. No model name, API key, prompt, provider SDK, background call, or placeholder analysis is present in the running applications.

Phase 7 will implement the approved boundary:

- An authorized HR user must explicitly request generation or regeneration.
- Deterministic KPI, feedback, and final scores remain independent of Gemini.
- The input excludes names, email addresses, reviewer identities, credentials, and unnecessary personal information.
- Feedback comments are treated as untrusted evidence and sanitized before transmission.
- Gemini receives no tools and no authority to modify scores, users, permissions, employees, KPIs, or reviews.
- The six-field structured response is strictly validated before a successful result is persisted.
- Provider timeout, invalid JSON, schema errors, quota errors, and stale evidence never break the numeric review workflow.
- Saved analyses record model, prompt version, calculation version, evidence hash, generation timestamp, and advisory status.

The model will be selected through an environment variable after verifying the then-current official Google Gemini documentation. No model name will be hard-coded in business logic.


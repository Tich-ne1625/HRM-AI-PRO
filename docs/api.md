# API contract

## Dashboard and saved advice (Phase 8)

`GET /api/v1/ai-reports?audience=PUBLIC&cycle_id=<optional>&page=1&page_size=20` lists SUCCEEDED generations only. It returns scoped metadata, not analysis output. HR_PRIVATE is HR-only and rejected before count; ADMIN is forbidden. Employee scope is applied in SQL before count/offset/limit, DRAFT is excluded, and count/items use REPEATABLE READ. Sort is generated_at/UUID descending. The `matches_current_calculation` flag compares calculation/hash plus current/finalized validity; it does not mean latest generation. Use existing `/reviews/{review_id}/ai-analyses/{id}` for explicit content access.

Dashboard now includes `recent_activities` (maximum six), using explicit action/type allowlists. ADMIN gets user created/role/status events with no subject identity. Other roles get scoped performance calculated/finalized events for the selected cycle, with snapshot name and report context. Neither DTO exposes actor, metadata, request ID, login or AI events. See the [complete contract](phase-8-contract.md).

`GET /api/v1/dashboard?cycle_id=<optional UUID>` is authenticated, read-only and `no-store`. ADMIN receives only account totals by active status/role and own pending feedback count; an explicit cycle returns 404. HR/MANAGER/EMPLOYEE use existing SQL employee/cycle scope and receive cycle choices, selected-cycle participant states, valid-score average/sample/distribution, KPI actual-entry coverage and department snapshots. The own pending-feedback count spans active cycles and never exposes other reviewers.

Default cycle order is ACTIVE, CLOSED, DRAFT (HR only), then newest start date and UUID. Choices and department groups are bounded to 100 with truncation flags; an explicitly selected older authorized cycle is appended. Unauthorized and missing cycles both return 404. All aggregates share one REPEATABLE READ snapshot. Empty averages/coverage are null; decimals are JSON strings rounded HALF_UP to two places. No domain writes, provider initialization or generation occur. See [the exact definitions](phase-8-contract.md).

Gemini generation HTTP 404 is returned as sanitized `provider_model_unavailable` (503); HTTP 400/401/403 map to `provider_configuration`. No provider response body, key or prompt is logged. Replaying a previously failed request reads its stored result; retrying after configuration changes requires a fresh confirmed intent.

## Authentication and accounts (Phase 2)

All responses use `Cache-Control: no-store` for successful personalized endpoints. Public user JSON contains only `id`, normalized `email`, `role`, `is_active`, `employee_id` (linked employee UUID, otherwise null). No response returns a password/hash or access/refresh token in JSON.

## Organization and employees (Phase 3)

| Method/path under `/api/v1` | Contract |
| --- | --- |
| GET `/departments`, `/positions` | Scoped `{items,total,page,page_size}`; `page>=1`, `page_size=1..100`, optional `q` (literal code/label search, max 100), `is_active`, allowlisted ascending `sort` |
| POST `/departments` | HR only, `{"code":"ENG","name":"Engineering"}`; optional is_active default true; 201 |
| POST `/positions` | HR only, `{"code":"DEV","title":"Developer"}`; optional is_active default true; 201 |
| PATCH `/departments/{id}`, `/positions/{id}` | HR, at least one code/name-or-title/is_active change; 200; required fields cannot be null |
| GET `/employees` | Scoped page; `page`, `page_size`, `q` (literal code/name), `department_id`, `position_id`, `employment_status`, `sort` |
| GET `/employees/{id}` | Scoped detail; nonexistent and inaccessible UUIDs both return 404 employee_not_found |
| POST `/employees` | HR; employee payload below; 201 |
| PATCH `/employees/{id}` | HR; supported employee fields, at least one; manager_id/user_id allow null to clear; 200 |
| GET `/employees/linkable-users?email=...` | HR-only exact normalized email lookup; returns `{items:[{id,email,is_active,employee_id}]}` or empty items; does not allow user creation/role changes |

All mutations require Origin + family-bound CSRF and recheck current HR authorization under locks. ADMIN has no implicit domain permission. HR sees all; MANAGER sees self + current direct reports only; EMPLOYEE sees self. Unlinked users see empty lists. Reference data is restricted to records referenced by visible employees for non-HR readers. Filtered count and items apply the same SQL scope.

Employee create example (UUID placeholders must be replaced):

```json
{"employee_code":"EMP-01","display_name":"Nguyễn An","department_id":"<department UUID>","position_id":"<position UUID>","manager_id":null,"user_id":null,"employment_status":"ACTIVE"}
```

Codes trim/uppercase to ASCII pattern `[A-Z0-9][A-Z0-9_-]{1,31}`; names trim to 1–200 characters and reject control characters with 422. Employee output contains id/code/display_name, department_id/name, position_id/title, manager_id/name, user_id, employment_status, created_at/updated_at. It never contains account secrets. Status is ACTIVE/INACTIVE, independent of user activation. New department/position/manager assignments must be active; unchanged retired references may be retained. No hard delete exists.

Reference sorts: code, name (department)/title (position), created_at, is_active. Employee sorts: employee_code, display_name, created_at, employment_status. UUID breaks ties. PATCH rejects unknown fields, empty bodies and null required fields. New errors: 409 duplicate_code, employee_code_already_exists, user_already_linked, reference_inactive, manager_inactive, reporting_cycle; 404 reference_not_found, employee_not_found, user_not_found. Other auth/validation errors retain the common envelope.

## Authentication endpoint reference

| Method/path under `/api/v1` | Input | Success | Authorization |
| --- | --- | --- | --- |
| `POST /auth/login` | `{"email":"admin@example.com","password":"<password>"}` | `200` user + cookies | Exact Origin |
| `GET /auth/me` | None | `200` user | Valid access + current user/family |
| `POST /auth/refresh` | No body | Empty `204` + rotated cookies | Refresh cookie, Origin, CSRF |
| `POST /auth/logout` | No body | Empty `204`, clears cookies | Access, active family, Origin, CSRF |
| `POST /auth/change-password` | `{"old_password":"<old>","new_password":"<new>"}` | Empty `204` | Access, active family, Origin, CSRF |
| `GET /users` | Query parameters below | `200` page | Current ADMIN |
| `POST /users` | `{"email":"hr@example.com","password":"<initial>","role":"HR"}` | `201` user | Current ADMIN, Origin, CSRF |
| `PATCH /users/{uuid}` | `{"role":"MANAGER","is_active":false}`; one or both fields | `200` user | Current ADMIN, Origin, CSRF |

Passwords contain 12–128 Unicode characters and are not trimmed. Replacement must differ from current. Login accepts shorter existing password input for verification; account creation enforces policy. No self-registration or email reset is provided. Roles: `ADMIN`, `HR`, `MANAGER`, `EMPLOYEE`; ADMIN has no implicit HR privileges.

`GET /users?page=1&page_size=20&sort=email&role=HR&is_active=true` returns `{"items":[],"total":0,"page":1,"page_size":20}`. Page starts at 1; page size is 1–100; ascending sort permits only `email`, `created_at`, `role`, `is_active`, with UUID tie-breaking. Role/status filters are optional. PATCH rejects empty, unknown-only, or explicitly null updates.

### Cookies and mutation headers

| Cookie | Path | HttpOnly | Lifetime |
| --- | --- | --- | --- |
| `insighthr_access` | `/` | Yes | 15 minutes by default |
| `insighthr_refresh` | `/api/v1/auth/refresh` | Yes | Remaining absolute family lifetime |
| `insighthr_csrf` | `/` | No | Same absolute family lifetime |

All use SameSite=Lax and Secure according to validated configuration. HTTPS production requires Secure. Login/refresh set cookies; logout deletes each with its original attributes/path. Use the same browser origin for web and `/api/v1/*`; Next.js proxies API calls. Origin must match `WEB_ORIGIN` byte-for-byte, including scheme/host/port, with exactly one header and no trailing slash. Missing/null/comma-separated/duplicate origins are rejected.

For mutations, send `Origin: <WEB_ORIGIN>` and `X-CSRF-Token: <insighthr_csrf cookie value>`. Header/cookie must match and their SHA-256 must match the session family. Login requires Origin but no CSRF. Reads need neither Origin nor CSRF. Refresh preserves family CSRF and absolute expiry; a consumed token presented with valid family CSRF revokes its whole family. Authorization always checks the current DB user and an active family, so replay/logout/deactivation immediately invalidate existing signed access tokens.

### Stable errors

| Status/code | Meaning |
| --- | --- |
| `401 invalid_credentials` | Wrong, unknown, or inactive login; also wrong old password |
| `401 authentication_required` | Missing/invalid access or inactive/missing user/family on protected reads |
| `401 invalid_session` | Missing/random/expired/revoked refresh; invalid access session for auth mutations |
| `401 refresh_reuse_detected` | Consumed refresh replay; family revocation committed |
| `403 origin_not_allowed` | Exact Origin check failed |
| `403 csrf_failed` | Missing/mismatched/cross-family CSRF |
| `403 forbidden` | Current DB role lacks permission |
| `404 user_not_found` | Target user does not exist |
| `409 email_already_exists` | Normalized duplicate email |
| `409 last_active_admin` | Would remove the final active ADMIN |
| `422 validation_error` / `invalid_password` | Invalid input or replacement policy |
| `500 internal_server_error` | Sanitized internal failure; transaction rolled back |

Errors follow the envelope below. Audit/database failures do not commit partial changes. Client code retries an authenticated request only once after one shared refresh; login and refresh never recursively refresh themselves.

## Base paths

Operational health endpoints are intentionally unversioned:

- `GET /health/live`
- `GET /health/ready`

Implemented authentication and account-management endpoints use `/api/v1`. OpenAPI is available at `/docs`. Health routes remain public.

## Liveness

Successful response (`200`):

```json
{
  "status": "ok",
  "service": "api"
}
```

This endpoint does not contact PostgreSQL or future external providers.

## Readiness

Successful response (`200`):

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "migrations": "current"
  }
}
```

Readiness returns `503` when PostgreSQL is unavailable, the Alembic marker is missing, or the revision is not the single current head.

## Error envelope

Every handled HTTP, validation, dependency, and unexpected error uses this shape:

```json
{
  "error": {
    "code": "service_not_ready",
    "message": "Service dependencies are not ready",
    "details": [
      { "check": "database", "status": "unavailable" },
      { "check": "migrations", "status": "unavailable" }
    ]
  },
  "request_id": "4f4f9bdc9b244467a5299a823448004d"
}
```

The same request ID is returned in the `X-Request-ID` response header. A caller-provided ID is accepted only when it is 8–128 characters and contains alphanumeric characters, hyphens, underscores, or periods. Unexpected exceptions return a generic message and never serialize exception text.

## Phase 6 performance reports and lifecycle

Implemented under `/api/v1`, all no-store. Read scope is HR/self/current direct manager, with ADMIN excluded. Missing/outside resources share 404. Every mutation requires exact Origin, family-bound CSRF and locked account/role/family revalidation. No automatic retry with refreshed versions after 409.

| Method/path | Payload and behavior |
| --- | --- |
| GET `/performance/{employee_id}?cycle_id=...` | Scoped report: NOT_CALCULATED/CURRENT/STALE/FINALIZED, readiness, frozen labels, capability flags; current_result=null when stale/not calculated; last_calculation explicitly historical |
| GET `/performance/{employee_id}/readiness?cycle_id=...` | Public actionable issue codes/KPI IDs; HR additionally receives pending/blocked required assignment IDs |
| POST `/performance/{employee_id}/calculate` | HR/current eligible direct manager, ACTIVE/unfinalized; `{cycle_id,expected_evidence_version}`. First 201, later 200. Same hash returns reused=true without a revision/audit |
| GET `/reviews/{id}/revisions` | Scoped history, page >=1, page_size 1–100; newest calculation_version first |
| GET `/reviews/{id}/revisions/{calculation_version}` | Scoped immutable calculation detail with allowed feedback aggregates and at most caller's own submission in that revision |
| GET `/reviews/{id}/finalization-context` | HR-only current evidence/calculation versions, readiness, open_optional_count |
| POST `/reviews/{id}/finalize` | HR-only `{expected_evidence_version,expected_calculation_version,acknowledge_open_optional_count}`; acknowledgement is mandatory even when zero; locks evidence and returns FINALIZED report |
| POST `/review-cycles/{id}/close` | HR-only `{expected_version}`; ACTIVE, nonempty, every review finalized/consistent; returns `{id,status:"CLOSED",version}` |

Versions and acknowledgement counts are strict integers; extra fields/forged scores are forbidden. Score outputs are two-decimal strings. Calculation reads raw integer ratings, not the display mean. Optional OPEN does not block calculation, optional SUBMITTED contributes equally. Finalization rechecks the exact evidence hash, both versions and optional count. Submitted/cancelled/open historical records remain; all later evidence writes fail. Closure never finalizes automatically and has no reopen API. Errors include stale_evidence_version/stale_calculation_version/stale_version, evidence_incomplete/evidence_inconsistent, review_stale/review_already_finalized, participant_finalized, cycle_not_active/cycle_already_closed, optional_feedback_acknowledgement_required and cycle_reviews_incomplete. The latter returns bounded participant issues and total issue count only to HR.

The reviewed endpoint map, pagination contract, role scopes, error meanings, and evidence-version concurrency rules are defined in [architecture.md](architecture.md). Documentation will add concrete request/response schemas as each phase implements them.


## Phase 4 cycles, KPI evidence and scoring defaults

All endpoints below are implemented under `/api/v1`, use the existing error envelope and no-store responses. POST resource creation is 201; other successes are 200. Mutations require exact Origin, family-bound CSRF, current role/status/family revalidation and atomic audit. No endpoint computes a score.

| Method/path | Contract |
| --- | --- |
| GET/PATCH `/settings/scoring` | ADMIN only; `{version,policy}`. PATCH `{expected_version,policy}`; weights total 100.00, cap positive or null; affects future activations only |
| GET/POST `/review-cycles` | HR sees all; other domain roles see ACTIVE/CLOSED with self/current direct report participation. POST HR `{name,start_date,end_date}` creates DRAFT |
| GET/PATCH `/review-cycles/{id}` | Scoped detail includes policy preview/snapshot, source version, scoped participant_count and can_edit/can_activate. PATCH HR metadata + expected_version, DRAFT only |
| GET/POST `/review-cycles/{id}/participants` | GET paginated scoped DTO; POST HR `{expected_version,employee_ids}` adds 1?100 distinct active employees atomically in DRAFT |
| DELETE `/review-cycles/{id}/participants/{participant_id}` | HR, DRAFT with no evidence; JSON `{expected_version}`; returns `{version,count:1}` |
| POST `/review-cycles/{id}/activate` | HR `{expected_version}`; validates eligibility, freezes policy/organization/relationships, increments versions and activates atomically |
| GET/POST `/kpis`; PATCH `/kpis/{id}` | HR manages definitions; GET other domain roles only definitions assigned within live scope. PATCH expected_version + supported changes; retirement via is_active |
| GET `/employees/{id}/kpi-options?cycle_id=...` | HR/eligible current direct manager only, ACTIVE/unfinalized participant; paginated active definitions available to assign |
| GET/PUT `/employees/{id}/kpis?cycle_id=...` | GET scoped aggregate; PUT HR/current eligible direct manager `{expected_evidence_version,items:[{definition_id,target,weight}]}` atomically replaces complete allocation |
| PATCH `/employee-kpis/{id}` | HR/current eligible direct manager `{expected_evidence_version,actual}`; actual null clears; target/weight/snapshot are forbidden |

Allocation response is `{participant,cycle_status,items}`. The participant DTO exposes id/cycle_id/employee_id, employee_code/display_name, department_id/name, position_title, evidence_version, is_snapshot and can_manage_kpis. It never exposes the private user/manager/direct-report snapshot. Items expose id/definition_id, a definition snapshot (schema_version/version/code/name/description/unit/direction), target/actual/weight. No score fields are fabricated. Nonexistent and out-of-scope detail requests use the same 404 code for that resource type.

Lists return `{items,total,page,page_size}` with page >=1, page_size 1?100 and UUID tie-breakers. Cycles: status/q (max 100), ascending sort start_date/name/created_at. Participants: q and department_id refer to snapshots after activation and live employee fields in DRAFT; sort employee_code. Definitions/options: q/is_active/direction, sort code/name/created_at; options only allow is_active=true. Search is literal. Definition/code uniqueness and retired-definition conflicts return 409. All count queries have the same SQL scope as item queries; cycle participant_count for a manager is not an organization total.

Quantity/percentage inputs and outputs are decimal strings. Target >0; actual >=0 or null; each allocation weight in (0,100], total exactly 100.00. Quantity NUMERIC(14,4), weight NUMERIC(5,2), policy cap NUMERIC(7,2). Booleans, numeric JSON values, exponents, NaN/Infinity, negative or excessive precision are rejected with 422 rather than rounded. Body extra fields and empty PATCH changes are rejected. A no-op still checks identity, state and version, without incrementing versions/audit.

PUT preserves each retained definition's assignment UUID and snapshot. Same target retains actual; target change clears it; weight changes retain it. Removed then re-added definitions get a new snapshot. Retired definitions can remain and receive actuals, but cannot be newly assigned. A new LOWER_IS_BETTER requires a finite cycle cap. Evidence writes serialize on the participant and increment one shared evidence_version. Do not retry automatically with a fresh version after 409.

Errors: 409 stale_version/stale_evidence_version, duplicate_code, participant_already_enrolled, cycle_not_draft/cycle_not_active, active_cycle_exists, activation_requirements_not_met, kpi_definition_inactive/kpi_policy_incompatible, participant_finalized; 404 cycle_not_found/participant_not_found/kpi_not_found/employee_kpi_not_found/employee_not_found; 422 validation_error. Activation details list at most 100 `{employee_id,code}` issues plus total issue_count, only for HR. Missing system singleton returns 503 configuration_unavailable. The Phase 6 `/close` endpoint below now implements the finalization prerequisite.

Policy defaults are `{schema_version:1,kpi_weight:"70.00",feedback_weight:"30.00",kpi_cap:"100.00"}`. Review history, role rules and allowed state transitions are documented in the [Phase 4 contract](phase-4-contract.md).

## Phase 5 assignments and feedback

Implemented and CI-accepted endpoints use `/api/v1`, no-store responses and the existing error envelope. Mutations require exact Origin, session-bound CSRF and authorization revalidation under locks. The [feedback contract](phase-5-contract.md) records all eligibility and recovery decisions.

| Method/path | Scope and payload |
| --- | --- |
| GET `/feedback-assignments` | Default `view=mine`, all roles, SQL owner scope. `view=administration` is HR-only with a separate raw DTO. Filters: cycle_id, participant_id, status, relationship; page >=1, page_size 1–100, sort due_at/created_at with UUID ties |
| GET `/feedback-assignments/{id}` | Exact reviewer or HR; outside and missing return the same 404. HR receives administrative fields; own mode never exposes another reviewer |
| GET `/feedback-context?participant_id=...` | HR-only participant labels, cycle status, evidence version and required coverage, even before any assignment exists |
| GET `/feedback-coverage?participant_id=...` | HR-only readiness, missing submitted SELF/MANAGER, pending/blocked required counts and corresponding assignment IDs; public summaries expose only readiness |
| GET `/feedback-reviewer-options?participant_id=...&relationship=...` | HR-only historical/current eligibility, pagination, literal code/name q <=100; no email. Includes disabled historical accounts and cancelled assignments to guide recovery |
| POST `/feedback-assignments` | HR `{participant_id,reviewer_id,relationship,required,due_at,expected_evidence_version}`; 201 |
| PATCH `/feedback-assignments/{id}` | HR versions plus required/deadline; CANCELLED requires explicit status=OPEN, preserving original identity and eligibility snapshot |
| DELETE `/feedback-assignments/{id}` | HR versions + reason_code, optional OPEN only; soft cancellation |
| POST `/feedback-assignments/{id}/replace` | HR versions + reviewer_id/due_at/reason_code, OPEN PEER/SUBORDINATE only; atomic cancel plus create/reopen preserving relationship/required |
| POST `/feedback` | Exact reviewer `{assignment_id,expected_assignment_version,expected_evidence_version,rating,comment}`; 201 immutable submission |
| GET `/employees/{id}/feedback?cycle_id=...` | HR/self/current direct manager live SQL scope; privacy-filtered summary, no client-selectable raw mode |

Versions are strict positive integers. Ratings are strict integer 1–5, rejecting booleans/floats/strings. Comments normalize CRLF to LF and trim, allow LF/tab, reject remaining unsupported controls and are limited to 2,000 plain-text characters. Extra identity fields are forbidden. A deadline is null or an ISO datetime with an explicit timezone, normalized to UTC; numeric Unix/naive values are rejected. Assignment creation, deadline edits and reopening require a future deadline or null. Submissions check `now >= due_at` after acquiring locks, and require ACTIVE/unfinalized evidence. End_date does not close a cycle or impose an automatic deadline.

All assignment changes and submissions increment one shared participant.evidence_version, with appropriate assignment.version increments. No-op validates lifecycle/authority/versions without incrementing/auditing. Submitted assignment fields are immutable. Replay returns 409 feedback_already_submitted without a second audit/version increment. A lost response can be checked through GET; do not automatically retry with fresh versions. Errors include stale_assignment_version/stale_evidence_version, deadline_passed, assignment_not_open, reviewer_ineligible/reviewer_inactive, assignment_already_exists, required_relationship_exists, required_coverage_conflict and assignment_limit_reached.

Summary exposes count/Decimal HALF_UP mean as a two-decimal string (null if none), readiness, relationship groups and at most the caller's own authored submission. Each PEER/SUBORDINATE group with fewer than three submitted reviewers has exactly `{relationship,suppressed:true,count:null,mean:null}`. No other comments/reviewer identifiers/submission timestamps appear. HR raw access is explicit, and aggregate inference remains possible. No feedback_score/final_score or AI output is created.


## Phase 7 audience-separated AI advice

All endpoints are no-store. GETs never generate, audit, expire or recover attempts. HR/self/current direct manager reads are scoped in SQL; ADMIN has no implicit HR role. HR_PRIVATE is HR-only, including count/history/detail; a non-HR request guessing a private analysis UUID receives 404.

| Method/path | Behavior |
| --- | --- |
| GET `/performance/{review_id}/ai-analysis?audience=PUBLIC` | State/configuration/capabilities plus current, last successful and latest attempt; default PUBLIC |
| POST `/performance/{review_id}/ai-analysis` | HR, exact Origin/session-bound CSRF; explicit generation/replay |
| GET `/reviews/{review_id}/ai-analyses?audience=PUBLIC&page=1&page_size=20` | Audience-scoped history; page_size 1-100 |
| GET `/reviews/{review_id}/ai-analyses/{analysis_id}` | Saved attempt; no provider call |

POST body: `{client_request_id:UUID,expected_calculation_version:int,expected_evidence_version:int,audience?:PUBLIC|HR_PRIVATE,regenerate?:bool,expected_latest_generation?:int}`. Versions are strict positive integers, booleans are strict, extras forbidden. Regeneration requires expected_latest_generation equal to the current successful generation for this calculation/audience, or 0 when absent. That field is forbidden for ordinary generation. Capture versions before confirming; never silently replace them after 409.

201 means a new successful generation, 200 a reused success or terminal replay, 202 an unexpired RUNNING replay. A matching request key never causes a second provider call. Different intent with the same key returns 409 idempotency_conflict. One RUNNING attempt per review across audiences, a 60-second lease and 30-second cooldown limit duplication. Expired status is derived on GET; an authorized fresh POST performs recovery. Failed regeneration preserves the last success. Changed evidence/calculation or revoked authority discards pending output. Finalized reviews in CLOSED cycles remain eligible for advice without reopening evidence.

Responses expose only attempt UUID/audience/generation and calculation/evidence versions/status/model/prompt version/times/sampled flag/advisory/output/error code. No requester, hashes, fence, prompt or raw source comments. Output has exactly summary, strengths, improvement_areas, feedback_themes, recommended_actions and caveats. PUBLIC never uses private comments as input; HR_PRIVATE is a separate generation and cannot be reused publicly.

Errors include ai_not_configured (503), provider_timeout (504), provider_invalid_output/provider_blocked (502), provider_quota/provider_configuration/provider_unavailable (503), generation_cooldown (429), generation_in_progress/generation_expired/analysis_stale/stale_analysis_version/stale_calculation_version/stale_evidence_version/review_stale/idempotency_conflict (409), and normal authorization/validation errors. Provider exception bodies and credentials are never returned. See [the full contract](phase-7-contract.md).

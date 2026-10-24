# Deployment and operations

## Current release: Phase 10 local Kubernetes and UI

Phase 10 application UI `559e74a` and tooling `d4a78bc` are documented in the [report](phase-10-report.vi.md), [contract](phase-10-contract.md) and [completed plan](superpowers/plans/2026-10-24-phase-10-kubernetes-docs.md). [Full CI](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40118504207) covers 843 backend/141 web tests, quality/build/Docker; [local-cluster CI](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40118509036) covers fresh deployment, real browser forms, migration failure/exclusion, database outage, persistence/restart/restore and verified TLS. Current migration head remains **20261024_0008**. Follow the [Vietnamese Kubernetes guide](kubernetes.vi.md); Compose remains the everyday option. Production/HA/cloud deployment is outside this acceptance.

## Historical Phase 9 acceptance

Runtime `9821e82` passed [full CI](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40109252558) (843 backend/140 web tests, quality/build/Docker smoke) and [isolated browser/upgrade/persistence CI](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40109315010). Current migration head is **`20261024_0008`**. Sections below retain historical acceptance evidence; use the current head rather than an old revision mentioned in those sections.

Run `docker compose --env-file .env up --build --wait` to upgrade without resetting data. The [Vietnamese operations guide](phase-9-operations.vi.md) documents request/login limits, expiry cleanup, nonce CSP/HSTS, role/session semantics, audit reads and exact isolated test commands. Defaults are compatible with existing `.env`; no extra runtime service/dependency or Gemini call is required. Read the [report](phase-9-report.vi.md) for the workload-specific performance baseline and remaining limitations. Phase 10 adds local Kubernetes acceptance; production hosting remains outside scope.

## Phase 6 performance operations

Accepted runtime `f595f23ca2c8a11605a833784bcf55648ee31712`: [InsightHR CI 39715137000](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39715137000), backend/frontend/docker-smoke all success. Final logs show 767 backend tests without skips, Ruff/mypy clean (85 files), 104 web tests and clean lint/types/build. All 15 new concurrency/read-consistency/revalidation cases passed five local rounds. Both local acceptance stacks are stopped with their volumes retained.

Apply current head `20261022_0006` with `docker compose --env-file .env up --build --wait` in an existing stack. No new environment variables, dependencies or services are required. The migration adds only result/history tables, retaining accounts, organization, cycle/KPI evidence and submitted/cancelled feedback. Direct-host users run `alembic upgrade head` from `apps/api`, then restart the API/web production processes.

Use **Chu kỳ đánh giá → Kết quả** for a participant. HR/current eligible direct manager calculates only after every KPI actual and required response is present. A zero component policy weight still requires complete evidence. The report becomes STALE after any evidence mutation; explicitly recalculate. HR checks the current optional OPEN count and confirms finalization. All evidence writers then reject changes for that participant. HR closes only once every participant is finalized, then activates the next draft. Neither finalization nor closure has a reopen operation. Dates do not close cycles automatically. The [Vietnamese guide](../README.vi.md#dùng-chức-năng-theo-role) explains the workflow.

Smoke now retains two cycles (CLOSED/ACTIVE), two participants, one KPI actual=90, seven assignments (five SUBMITTED, one CANCELLED, one OPEN), five feedback ratings totaling 20, one finalized review and two revisions with scores 24.00/87.00. Before restart and again after PostgreSQL-only startup, run `python scripts/check_performance_persistence.py --compose-project <disposable-project>`. It asserts this fixture and prints only a SHA-256 fingerprint of complete persisted result/history/evidence data. Compare identical fingerprints before starting migrations/API again. This exact-fixture checker is intended for acceptance, not an arbitrary existing user database.

Local acceptance used separate projects `insighthr-phase6-acceptance` (13006/18006) and `insighthr-phase6-final-acceptance` (13016/18016), separate volumes and image tags; the working stack at 3000/8000 was left untouched. Edge performed actual calculate/recalculate/finalize/close actions and checked role navigation, history, stale display, keyboard focus and existing pages at 390/1280px without viewport overflow. Restart retained complete hashes/scores/versions/finalized timestamps before migration reruns. Final CI results are recorded in the [Phase 6 plan](superpowers/plans/2026-10-22-phase-6-performance.md); review boundaries and limits are in [phase-6-review.md](phase-6-review.md).

## Environment files

The repository root `.env.example` lists foundation and authentication variables. Compose reads a root `.env`; direct-host applications read `apps/api/.env` and `apps/web/.env.local` from their respective working directories.

## Phase 2 authentication operations

| Variable | Contract |
| --- | --- |
| `AUTH_ACCESS_SECRET` | Signing key, nondefault and at least 32 characters in test/production; replace the development placeholder before shared use |
| `WEB_ORIGIN` | Exact browser origin, no trailing slash; e.g. `http://localhost:3000`. Changing port/hostname requires changing this value |
| `COOKIE_SECURE` | False only for explicit local HTTP; production requires true and HTTPS |
| `ACCESS_TOKEN_MINUTES` | Positive integer; default 15 |
| `REFRESH_SESSION_DAYS` | Positive integer; default 7, fixed absolute family expiry |
| `API_INTERNAL_URL` | Server-only API origin; never `NEXT_PUBLIC_*`. Rewrites resolve during web build; local default localhost:8000, image builder defaults api:8000 |

Compose forwards auth settings to migrate/API. Production must supply a real signing key via an environment/secret store, secure cookies and the correct HTTPS origin; this local Compose database is not a production operations design. Raw PostgreSQL passwords and their percent-encoded URL forms must remain equivalent. Do not percent-encode signing keys. Never put credentials/tokens into Git, command arguments or logs.

After migrations, bootstrap the first administrator from repository root:

```bash
docker compose --env-file .env exec api python -m app.cli.create_admin --email admin@example.com
```

The CLI uses hidden interactive prompts and confirms a 12–128 Unicode-character password. If no interactive TTY is available it refuses to echo a password. Direct-host alternative from `apps/api`: `python -m app.cli.create_admin --email admin@example.com`. `--password-stdin` reads two matching lines for automation; supply them through a secret provider or process stdin, never literal shell arguments/history. Creation and `user.bootstrap_created` audit commit atomically; duplicate email or validation failure changes nothing.

Open `/login`, then `/account`; ADMIN can open `/admin/users`. Employee references now reflect Phase 3 links (null for unlinked users). ADMIN does not inherit HR privileges. Account changes require exact Origin and family-bound CSRF; the browser client reads only the CSRF cookie, never the HttpOnly access/refresh cookies. A 403 origin error commonly means a trailing slash, port mismatch or localhost versus 127.0.0.1; fix configuration rather than bypassing checks.

Access lasts 15 minutes by default. The client shares one refresh across concurrent 401s and retries once. Refresh consumes a token, preserves absolute expiry/CSRF, and issues only cookies. Reuse with valid family CSRF revokes the whole family. Logout clears matching cookie paths and revokes the family. Password change keeps the caller's family and revokes every other family; deactivation revokes all families. Current DB role/status is always authoritative.

### Lost administrator password

Phase 2 has no email reset or administrative password-reset endpoint. An operator with trusted host access can create a replacement ADMIN with a different email through the bootstrap CLI, log in, and deactivate the lost account. Duplicate-email bootstrap does not overwrite passwords. Do not edit password hashes directly or delete users/audits. If another active ADMIN exists, they can manage role/status but cannot retrieve or reset another user's password through the UI.

### Acceptance and reproducibility

The workflow `.github/workflows/phase1-ci.yml` is named **InsightHR CI** and retains its filename to preserve existing branch checks. It runs PostgreSQL unit/integration/concurrency tests and web tests/lint/types/build, builds nonroot locked images, checks runtime contents, starts a fresh Compose project, and exercises authentication through the actual Next.js proxy. `scripts/smoke_auth.py` generates passwords in memory, bootstraps via process stdin, and checks login/me, ADMIN creation, HR denial, CSRF rejection, password revocation, refresh and logout. It never prints credentials.

For an already running disposable acceptance project:

```bash
python scripts/smoke_auth.py --compose-project insighthr-acceptance
```

That command creates disposable accounts, organization profiles, KPI/feedback evidence, two calculation revisions, a CLOSED finalized cycle and a next ACTIVE cycle. Smoke requires a fresh acceptance project without an existing ACTIVE cycle; choose the project intentionally. Use a unique Compose project/empty volume when checking a clean install. Normal `down`/`up` must preserve users, employees, cycles/KPI evidence, feedback and revision `20261022_0006`; CI checks counts/statuses/ratings plus a complete performance snapshot fingerprint before migrations run again. Cleanup must name only that acceptance project. An HTTPS deployment additionally needs a real browser cookie check with Secure enabled.

Local evidence on 2026-10-19: Python 3.12.10, PostgreSQL 16.15, Node 26.8.1 and npm 11.19.0; 387 backend tests, 35 frontend tests, Ruff/mypy, ESLint, TypeScript and production build passed. Direct versions include Next.js 16.3.8, React 19.3.0, SQLAlchemy 2.1.3 and FastAPI 0.142.2; lockfiles record the complete dependency graph. Images/CI target Node 24. `npm audit --omit=dev` reported zero vulnerabilities; full audit reported five high findings in the existing ESLint → fast-glob → micromatch → braces dev-tool chain, with no compatible fix offered (the suggested downgrade to Next 14 is not applied). Local clean-container execution remains unavailable because Docker's Linux engine/WSL prerequisite is absent.

Phase 2 acceptance passed on Linux in [InsightHR CI run 39194000937](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39194000937), commit `74ba64023020bbcf2595e98fd5eab955209671bf`: backend, frontend and docker-smoke all succeeded. This verifies both migrations, full PostgreSQL suite, frontend checks/build under Node 24, clean Compose startup, actual web proxy authentication, cookie attributes, bootstrap through stdin, HR denial, CSRF rejection, password/session revocation, refresh/logout, final nonroot image contents and persisted user count/revision after restarting PostgreSQL before migrations. The initial CI attempt stopped at an incorrect grep for hydrated login text; the corrected check validates the prerendered Suspense HTML shell, while Vitest covers hydrated form behavior. Production HTTPS/browser acceptance remains an environment-specific deployment check.

The sample password is for an isolated local workstation only. Replace it before using a shared network or CI secret store. `POSTGRES_PASSWORD` is the raw PostgreSQL password; `POSTGRES_PASSWORD_URLENCODED` is its percent-encoded equivalent for Compose's SQLAlchemy URL. If a direct-host database password contains URL-reserved characters, percent-encode it in `DATABASE_URL` as well.

## Phase 3 organization operations

No additional environment variables or services are required. Rebuild web/API images and run `alembic upgrade head` to apply `20261019_0003`. Back up any data that must be kept first. Bootstrap ADMIN as above, create HR/MANAGER/EMPLOYEE accounts through `/admin/users`, then sign in as HR to create departments/positions and employee records. The fresh database intentionally has no demo organization or seed.

HR uses `/departments`, `/positions`, `/employees` and `/employees/{id}`. Exact-email account lookup links existing users without granting HR account-administration permissions. One account links to at most one employee; `GET /auth/me`, login/refresh and ADMIN user representations report current employee IDs. Managers see self/direct reports; employees see self; unlinked accounts see empty scope; ADMIN cannot access HR data through system privileges.

Reference retirement keeps old links and prevents new assignments. Manager changes reject self/multi-node cycles, including concurrent opposing requests. Employment ACTIVE/INACTIVE does not automatically disable login. Audit metadata excludes credentials and free-text names. See [contract](phase-3-contract.md) and [API](api.md).

Phase 3 validation: the local full backend suite passed 459 tests before final acceptance/regression additions; the real-account E2E and focused creation/retirement/control-character regressions also passed. All 49 frontend tests, lint/typecheck and production build passed with the four new organization routes. The initial four PostgreSQL concurrency scenarios passed in each of five runs; final coverage adds concurrent code uniqueness and department/position retirement versus assignment. API labels reject database-unsupported control characters with 422.

Final [InsightHR CI run 39221690393](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39221690393) at commit `8f193b39f44c8e791849847111400eecdfc0eff4` succeeded for **backend (467 collected tests), frontend (49 tests) and docker-smoke**. It applies all three migrations; exercises organization references, linking, SQL scope, cycle rejection and transfer through the actual web proxy; verifies image contents/nonroot users; and confirms persisted employee/user counts and revision before migrations run again after restart. Earlier Phase 3 runs 39220889772 and 39221435063 also passed. Linux CI supplies clean-stack evidence because the local Windows Docker/WSL prerequisite remains unavailable.

## Phase 4 cycle/KPI operations

No new environment variables, dependencies or services. Rebuild images and apply `alembic upgrade head` for `20261020_0004`; Compose migrate runs before API startup. The migration preserves Phase 3 organization/accounts and creates five domain tables plus singleton scoring defaults. Back up data that must be kept before upgrading; normal upgrade needs no user bootstrap or volume deletion. See [database](database.md) and [API](api.md).

ADMIN uses `/settings/scoring`; HR uses `/kpis` and `/review-cycles`. DRAFT enrollment is editable, activation freezes policy and organization/relationship snapshots and requires eligible active employee/manager accounts and references. A root employee without a manager is not activation-eligible under the required SELF/MANAGER policy. HR does not need a profile to administer cycles. Only one ACTIVE cycle exists; Phase 6 implements HR finalization and closure, and end_date does not close automatically.

From cycle participants, HR/current direct manager opens `/employees/{id}/kpis?cycle_id=...`. Allocate full positive targets/weights totalling exactly 100.00 and enter actuals separately. All domain decimals are strings; use `0.0000` for a real zero and null to clear. Target changes clear corresponding actuals; weight changes retain them. Assignment and cycle snapshots are historical; transferred managers gain/lose live scope without changing them. A 409 stale-version requires explicit reload and a fresh deliberate edit, not automatic mutation retry.

Local verification on 2026-10-20: full backend 566 passed before the final security/real-account additions; the five focused security/real-account tests passed, with final collection 570. Ruff/mypy clean (69 source files). Frontend 69 tests, lint, TypeScript and production build passed. Fifteen race cases passed in each of five PostgreSQL runs. Direct security review covered SQL scopes/counts/DTOs, Origin/CSRF and session revalidation on all ten mutation paths, stale writers, account disable/role/manager changes while waiting, deadlocks, snapshot consistency and audit rollback; no independent-review claim is made.

Docker Desktop/WSL2 is now available locally. An isolated project `insighthr-phase4-acceptance` used ports 13004/18004 and separate image tags/volume; the existing user's stack at 3000/8000 was not changed. Both images built with locked dependencies, ran as 10001:10001 and contained no app .env files or test tooling. The actual Next.js proxy passed auth + organization + cycle/KPI HTTP smoke with generated in-memory passwords. Headless Edge accepted real login by Enter, keyboard focus, HR desktop/390px layouts, MANAGER saving actual, EMPLOYEE read-only and ADMIN settings without viewport overflow. Restarting only the acceptance PostgreSQL preserved revision/users/employees/cycles/participants/allocations/non-null actual counts before migrations could rerun.

Final CI at runtime commit `adcbabe1a77e73042aea7e67552ea510ae450832` succeeded for backend (570 tests), frontend (69 tests) and docker-smoke: [InsightHR CI 39356761739](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39356761739). The updated Linux workflow also checks cycle/participant/allocation/actual counts after PostgreSQL-only restart. The isolated local acceptance project was stopped afterward, preserving its volume and the user's existing running stack. Production HTTPS/Secure-cookie acceptance remains specific to the deployed environment.

## Phase 5 feedback operations

Phase 5 is CI-accepted at runtime `bf04fe2c5ff162993fafec857f25f87b1c2b7621`: [InsightHR CI 39369977157](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39369977157), backend/frontend/docker-smoke all success. It adds no dependencies, environment variables or services. Apply head `20261020_0005`; upgrade preserves accounts/cycle/KPI evidence without inventing assignments. HR opens assignments from cycle participants, while any assigned role uses `/feedback`. Live employee scope controls `/employees/{id}/feedback?cycle_id=...`; historical assignment ownership remains valid after transfer/unlink/role/employment changes, provided the reviewer account and session are active. See the [Vietnamese walkthrough](../README.vi.md).

SELF/MANAGER must be assigned explicitly and remain required. Disabled historical accounts block that coverage; ADMIN must restore the correct account. The current account recovery tools cannot reset another user's password; replacing a historical reviewer with a new account is outside this contract. HR can extend expired OPEN deadlines; no cron job cancels them. Submitted feedback cannot be edited/deleted. For stale-version conflicts retain text, explicitly reload versions, review and confirm again.

Local isolated project `insighthr-phase5-acceptance` used ports 13005/18005 and separate images/volume, leaving the working stack alone. Auth/organization/cycle/KPI/feedback HTTP smoke passed through Next.js, including real SELF/MANAGER/PEER/SUBORDINATE/ADMIN reviewers. PostgreSQL-only restart retained revision `20261020_0005`, six assignments (five SUBMITTED, one CANCELLED), five feedback rows and rating sum 20, together with account/organization/KPI counts, before migrations reran. CI built final images and passed the same smoke/nonroot/runtime-content/persistence checks. Final logs show **661 backend tests passed without skips**, Ruff/mypy clean (77 files), **89 web tests**, lint/types/build clean. All 26 concurrency cases passed five local runs. Edge checked HR UI assignment, employee/ADMIN one-time submissions, transferred-manager scope and existing organization/KPI/cycle pages at 390/1280px without viewport overflow. The isolated local stack was stopped, retaining its volume. See the [acceptance plan](superpowers/plans/2026-10-20-phase-5-feedback.md) and [direct review](phase-5-review.md).

## Direct-host PostgreSQL setup

Create a local role and database with PostgreSQL 16 administrative credentials:

```sql
CREATE USER insighthr WITH PASSWORD 'change-me@local-only';
CREATE DATABASE insighthr OWNER insighthr;
```

The value above matches `.env.example`; replace it in both places outside an isolated workstation. Set `DATABASE_URL=postgresql+psycopg://insighthr:change-me%40local-only@localhost:5432/insighthr`, then run from `apps/api`:

```bash
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Start the web application from `apps/web`:

```bash
npm ci
npm run dev
```

`API_INTERNAL_URL` defaults to `http://localhost:8000`. The root page remains usable and displays `API unavailable` when the backend is offline.

## Docker Compose lifecycle

Validate configuration without starting containers:

```bash
docker compose --env-file .env.example config --quiet
```

Build and start:

```bash
cp .env.example .env
docker compose --env-file .env up --build --wait
docker compose --env-file .env ps
```

Compose starts PostgreSQL, waits for database health, runs `alembic upgrade head` once, waits for successful migration, then starts the API and web services. The API readiness check requires both database connectivity and the exact current Alembic head. Gemini is intentionally not a readiness dependency.

Inspect logs:

```bash
docker compose --env-file .env logs migrate
docker compose --env-file .env logs api
docker compose --env-file .env logs web
```

If migration fails, read the `migrate` logs, correct the migration or configuration, and run:

```bash
docker compose --env-file .env run --rm migrate
docker compose --env-file .env up --wait
```

Normal shutdown preserves PostgreSQL:

```bash
docker compose --env-file .env down
```

The following command permanently deletes the local PostgreSQL volume and all data in it. Use it only for an intentionally disposable environment:

```bash
docker compose --env-file .env down --volumes
```

## Windows Docker prerequisite

Docker Desktop Linux containers require WSL 2 and Virtual Machine Platform. If Docker reports that WSL is missing, run these commands in an Administrator PowerShell and restart Windows:

```powershell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

After restart, launch Docker Desktop and confirm `docker info` reports a server before running Compose.

## Health semantics

`GET /health/live` proves that the API process can serve HTTP and never contacts external dependencies. `GET /health/ready` proves PostgreSQL responds and its single Alembic revision equals the application head. A failed readiness check returns `503`; liveness continues returning `200` during a database outage.

## Production image properties

Both images use multi-stage builds and run as UID/GID `10001:10001`. The API runtime contains application wheels and Alembic runtime files without test tooling. The web runtime contains Next.js standalone output. Neither image runs a development server or mounts source code through the default Compose file.

## Phase 1 verification

Verified locally on 2026-10-03:

- Python 3.12.10 and PostgreSQL 16.15
- 28 backend tests, including two real PostgreSQL integration tests
- Ruff and mypy clean
- Node.js 26.8.1 used to verify the Node 24-targeted application
- 8 frontend tests, ESLint, strict TypeScript, and Next.js production build clean
- Docker Compose v5.5.1 accepted the Compose model
- Static container-contract tests passed

The local Docker engine could not start because this Windows installation requires an Administrator session and restart to enable WSL. GitHub's Linux runner built both production images with locked runtime constraints and passed the clean Compose startup, reserved-character database password, migration, API readiness, web-to-API connectivity, final-image inspection, and normal `down`/`up` persistence checks in [`Phase 1 CI` run 37132907757](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/37132907757). The persistence check reads the retained Alembic revision after restarting PostgreSQL alone, before migrations can run again.



## Phase 8 final acceptance — 2026-10-24

Runtime `88700d8` passed [CI 40086271058](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40086271058): **830 backend/133 web tests**, Ruff/mypy (99 source files), lint/typecheck/build and Docker smoke/persistence. `/ai-reports` lists SQL-scoped saved successes without output, with HR-only private scope and explicit detail reads. Dashboard includes six allowlisted activity projections. Shared mutation settlement invalidates dashboard/AI-list GET caches without retrying a write; dashboard hides cached personal metrics after a failed refresh.

The user stack was rebuilt with `docker compose --env-file .env up --build --detach --wait`, reusing its PostgreSQL volume; no new migration or service. Edge production acceptance covered 32 cases/80 screenshots at 390 and 1280px, seven representative accounts, saved-detail focus and keyboard table scrolling, with no document overflow/runtime exceptions/API writes. Read-only fingerprints of the checked domain tables and non-secret account attributes matched before/after, retaining all three existing AI attempts; no demo reset or new Gemini call. See the [Vietnamese report](phase-8-report.vi.md) for the role matrix, exact evidence and Phase 9 boundaries. Earlier records below are historical milestones.

## Phase 7 optional Gemini operations

### Local follow-up on 2026-10-22

Dashboard runtime `7d10da5` passed [CI 39745189991](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39745189991): 821 backend/122 web tests, Ruff/mypy (97 source files), lint/types/build and Docker smoke/persistence. This accepts Phase 8 part 1; the central AI listing, sanitized activity and full cross-screen UX acceptance remain open.

The user's configured `gemini-2.5-flash-lite` could list its model metadata but returned HTTP 404 for content generation. The local non-secret model setting was changed to `gemini-3.5-flash-lite`; the API container was recreated and then rebuilt with the dashboard changes. Effective settings were checked as enabled/key-present/model-name only; no key was printed or committed.

A bounded real adapter probe with fictional numbers validated the six-field output. Subsequently one explicit PUBLIC request through the application's authenticated same-origin API succeeded for the fictional `DEMO-AN` active-cycle report. The saved analysis was read back with matching contents and the performance result/state stayed unchanged. This is actual provider output, not an injected fixture. It is a limited live PUBLIC smoke; HR_PRIVATE, live concurrent recovery and qualitative accuracy are not claimed as accepted. The successful advice remains in the user's demo for inspection, alongside the previous failed attempt.

The local stack at 3000/8000 now runs the dashboard build, with the original PostgreSQL volume and user/demo data retained. Edge checks covered HR, MANAGER, EMPLOYEE and ADMIN at 390/1280px (eight screenshots), no document horizontal overflow and no AI POST from visiting the dashboard. HR saw five participants and a valid average of 84.90 from two samples; manager saw three participants/82.80 from one sample; the unfinished employee had no fabricated average; ADMIN received thirteen active accounts and no HR metrics. Evidence is stored locally under ignored `.superpowers/sdd/phase-8/` without credentials or full prompts. Earlier Phase 7 statements below describe the original offline acceptance, before this follow-up.

[CI 39728715722](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39728715722) accepted `b16efd6`: 811 backend/117 web tests, Ruff/mypy (92 source files), lint/types/build and Docker smoke including four nonempty AI attempts persisted through restart. Local Edge verified the existing layout and role scopes at 390/1280px. Five local concurrency rounds passed 6/6 each. The isolated acceptance stack is stopped, its volume retained and its two image tags removed; the user stack at 3000/8000 was not changed. Live provider acceptance remains unperformed.

Upgrade to head `20261022_0007` with `docker compose --env-file .env up --build --wait`. Existing volumes/data are retained. The new locked google-genai 2.32.0 SDK is installed in the API image only; no new service or frontend SDK is required. API startup, readiness, numeric workflow and saved analysis GETs do not contact Gemini. The previous Phase 6 acceptance above is historical.

| Variable | Default and boundary |
| --- | --- |
| GEMINI_ENABLED | false; keyless startup remains supported |
| GEMINI_API_KEY | empty SecretStr; required when enabled, API runtime only |
| GEMINI_MODEL | empty; operator chooses a supported structured-JSON model |
| GEMINI_TIMEOUT_SECONDS | 20; integer 5-30, total deadline and SDK millisecond timeout |
| GEMINI_MAX_OUTPUT_TOKENS | 2048; integer 512-4096 |

Keep secrets out of Git, NEXT_PUBLIC_ variables, build args, screenshots and logs. Compose forwards Gemini settings only to the API service. Migrate/web do not receive the key. Changing these runtime settings requires recreating the API container; updating code/dependencies also requires rebuilding. Direct-host users supply API environment variables, run `alembic upgrade head`, and restart the API and production web process.

HR selects PUBLIC or HR_PRIVATE in the report and explicitly confirms each generation. PUBLIC transmits only aliased numeric evidence and filtered aggregate statistics. HR_PRIVATE additionally transmits up to twenty sanitized comments of at most 500 characters each from the exact revision. Redaction is best effort. Requests are bounded to 64 KiB and output to 32 KiB with strict six-field validation. No tools, background generation or SDK retry; failures do not block scoring/finalization/closure.

A lost response should be checked by replaying the same client_request_id. Do not create a new request key automatically. RUNNING leases expire after 60 seconds, then an explicit authorized fresh request can recover. Cooldown is 30 seconds across audiences. Old success/history remain readable after a failed regeneration. Crashes after provider acceptance cannot guarantee exactly-once billing.

Offline CI uses real SDK MockTransport tests and injected-provider integration tests. Fresh Docker smoke runs keyless first. Only in the explicitly disposable `insighthr-ci` or `insighthr-phase7-acceptance` project, a separate test-runner process receives `apps/api/tests/acceptance/seed_ai_fixture.py` through stdin. That test code is absent from the runtime image and running API; it creates clearly labelled demo-fixture public/private successes, a failed regeneration and an expired lease. `check_performance_persistence.py` asserts these four nonempty attempts and fingerprints complete content, output, versions, hashes and numeric evidence before/after PostgreSQL-only restart, before migrations run again. Never run this fixture/checker on a user database.

Live Gemini acceptance has not been performed. To opt in, configure a valid key and supported model yourself, use fictional employee/feedback evidence, enable Gemini, then have HR explicitly create PUBLIC and HR_PRIVATE advice. Check saved schema/model/times, correct privacy scope, controlled regeneration and numeric score stability. Record the live model/SDK/result separately; never label injected-provider output as a real Gemini response. Do not put credentials or full prompts in acceptance artifacts.

# InsightHR

[Đọc hướng dẫn bằng tiếng Việt](README.vi.md)

InsightHR is an AI-assisted employee performance management system built as a university capstone. It focuses on employee records, review cycles, KPIs, authorized 360-degree feedback, deterministic scoring, and advisory Gemini analysis.

The project is a modular monolith: a Next.js web application, a FastAPI backend, and PostgreSQL. Read the approved [architecture proposal](docs/architecture.md) for the complete design and business rules.

## Current scope

Phases 1–10 are implemented. Phase 10 adds isolated local Kubernetes deployment, guarded migration Jobs, ingress/TLS, tested backup/restore and a simpler role-aware workspace. Application UI is `559e74a`; deployment tooling is `d4a78bc`. [Full CI](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40118504207) passed 843 backend/141 web tests; [cluster acceptance](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40118509036) verifies browser forms, failure/recovery, restore and TLS. Read the [Vietnamese report](docs/phase-10-report.vi.md), [Kubernetes guide](docs/kubernetes.vi.md) and [short Vietnamese README](README.vi.md). Compose remains the everyday setup; production/cloud hosting is outside scope.

## Earlier acceptance milestones

Phases 1–9 are implemented and accepted. Phase 9 runtime `9821e82` passed [full CI](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40109252558): **843 backend / 140 web tests**, quality/build and Docker smoke. [Isolated browser/persistence CI](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40109315010) also passed. It adds session/cache fencing, request/login limits, security headers/CSP and a scoped audit reader. Five race rounds passed 145 tests each; the fictional 1,000-profile baseline completed 1,472 reads with zero errors. See the [Vietnamese report](docs/phase-9-report.vi.md), [operations guide](docs/phase-9-operations.vi.md), [contract](docs/phase-9-contract.md) and [completed plan](docs/superpowers/plans/2026-10-24-phase-9-security-integration.md).

Phases 1–8 are implemented and accepted as of 2026-10-24. Final runtime `88700d8` passed [CI 40086271058](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40086271058): **830 backend tests, 133 web tests**, Ruff/mypy (99 source files), lint/typecheck/build and Docker smoke/persistence. The workspace covers role-scoped organization, cycles, KPIs, feedback, scoring/history/finalization, optional AI advice, dashboards and saved advice listings. See the [Vietnamese Phase 8 report](docs/phase-8-report.vi.md).

Phase 7 is [offline CI-accepted](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39728715722) at `b16efd6`: **811 backend and 117 web tests**, quality/build and Docker persistence passed. It implements explicit Gemini generation on the existing report: PUBLIC numeric advice and separate HR_PRIVATE sanitized-comment analysis. AI is disabled and keyless by default. HR confirms each generation; saved advice/history remain readable without a configured provider. See the [plan and acceptance](docs/superpowers/plans/2026-10-22-phase-7-gemini.md), [contract](docs/phase-7-contract.md), [review](docs/phase-7-review.md) and [Vietnamese guide](README.vi.md). Live Gemini acceptance is separate from offline provider tests.

## Performance workflow

`/dashboard` is the default login destination: scoped metrics, valid-score samples/distribution, department snapshots, own feedback tasks and sanitized activity. `/ai-reports` lists saved successful generations with cycle/audience filters, pagination and explicit content access; HR_PRIVATE remains HR-only. The shared role-aware layout, keyboard-scrollable tables, focus management and mutation refresh flow are accepted. See the [contract](docs/phase-8-contract.md) and [completed plan](docs/superpowers/plans/2026-10-22-phase-8-dashboard.md).

A bounded live adapter probe with fictional numbers succeeded on `gemini-3.5-flash-lite` on 2026-10-22, validating all six output fields. This verifies connectivity/schema, not full live business acceptance or advice quality. Provider HTTP 404 now maps to `provider_model_unavailable`; raw provider errors and keys are never exposed.

To use Phase 6, open **Review cycles → participant → Kết quả**. Complete KPI actuals and required SELF/MANAGER/other assignments, then HR or the current eligible direct manager calculates. Changed evidence makes the report STALE until explicit recalculation; history remains available. HR reviews the open optional assignment count and confirms finalization, which locks all evidence writers. HR closes a cycle only after every participant is finalized, then activates the next draft. Closed reports retain live access controls. ADMIN has no implicit HR access. Use `docker compose --env-file .env up --build --wait` after updating code; existing data is preserved. See the [Vietnamese walkthrough](README.vi.md#dùng-chức-năng-theo-role).

## Sample data

For a hands-on role walkthrough, use the [fictional office demo](docs/demo.vi.md). After rebuilding the API image, run `docker compose --env-file .env exec api python -m app.cli.seed_demo`. It adds ten accounts, eight employees and three cycles atomically, prints a generated password once, preserves existing data and practice progress on rerun, refuses production/conflicting ACTIVE cycles, and never invokes Gemini. No schema migration is required.

## Technology stack

- Web: Next.js 16, React 19, strict TypeScript, Tailwind CSS
- API: Python 3.12, FastAPI, SQLAlchemy 2, Pydantic Settings, Alembic, psycopg 3
- Data: PostgreSQL 16
- Delivery: Docker, Docker Compose, GitHub Actions
- Quality: pytest, Ruff, mypy, Vitest, ESLint, TypeScript compiler

## Repository layout

```text
apps/
  api/               FastAPI application, migrations, and backend tests
  web/               Next.js application and frontend tests
docs/                Architecture and operational documentation
infrastructure/
  docker/            Production container definitions
docker-compose.yml   Local complete stack
```

## Prerequisites

For direct-host development:

- Git
- Python 3.12
- Node.js 24 LTS and npm
- PostgreSQL 16

For the recommended complete-stack workflow:

- Docker Desktop on Windows/macOS or Docker Engine on Linux
- Docker Compose v2+
- WSL 2 and virtualization enabled when using Docker Desktop on Windows

## Start with Docker Compose

PowerShell:

```powershell
Copy-Item .env.example .env
docker compose --env-file .env up --build --wait
```

Portable shell:

```bash
cp .env.example .env
docker compose --env-file .env up --build --wait
```

Open `http://localhost:3000`. The page should report `API connected`.

Create the first administrator interactively, without passing a password in arguments:

```bash
docker compose --env-file .env exec api python -m app.cli.create_admin --email admin@example.com
```

Enter the same 12–128-character password twice. Open `http://localhost:3000/login`, sign in, and visit `/account`. ADMIN accounts can open `/admin/users` to create accounts, change roles, and activate/deactivate users. The final active ADMIN is protected. ADMIN does not inherit HR permissions.

For a direct-host API, run `python -m app.cli.create_admin --email admin@example.com` from `apps/api`. `--password-stdin` is available for automation and reads two matching lines; do not put passwords in environment variables, process arguments, or shell history. See the [authentication runbook](docs/deployment.md#phase-2-authentication-operations).

Operational endpoints:

- `http://localhost:8000/health/live`
- `http://localhost:8000/health/ready`

Stop containers while preserving PostgreSQL data:

```bash
docker compose --env-file .env down
```

See [deployment.md](docs/deployment.md) before deleting volumes or troubleshooting startup.

## Direct-host development

Create separate local environment files for each application:

```powershell
Copy-Item .env.example apps/api/.env
Copy-Item .env.example apps/web/.env.local
```

Backend from `apps/api`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --constraint requirements.lock -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Before applying migrations on a fresh workstation, create the PostgreSQL role and database using the matching credentials in `.env`. See [Direct-host PostgreSQL](docs/deployment.md#direct-host-postgresql) for the SQL and connection details.

Frontend from `apps/web` in a second terminal:

```powershell
npm ci
npm run dev
```

On portable shells, create the environment with `python3.12 -m venv .venv` and activate it with `source .venv/bin/activate`; all following commands are the same.

## Database migrations

Create a migration after adding SQLAlchemy metadata:

```bash
cd apps/api
alembic revision --autogenerate -m "describe the schema change"
alembic upgrade head
```

Review every generated migration before running it. Current head is `20261024_0008` (login limiter), following AI `20261022_0007` and performance `20261022_0006`; Phase 10 adds no schema change. Back up data that must be kept before upgrades.

## Tests and quality gates

Backend from `apps/api` with a dedicated PostgreSQL test database:

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://insighthr_test:insighthr-test-password@127.0.0.1:5432/insighthr_test"
python -m pytest -q
python -m ruff check app tests alembic
python -m mypy app
```

Frontend from `apps/web`:

```bash
npm run test -- --run
npm run lint
npm run typecheck
npm run build
```

The integration fixture drops user/session/audit tables and `alembic_version`; the database name must end in `_test`. Never use a database containing application data.

## Environment and secrets

`.env.example` is the public configuration contract. Copy it to `.env` and replace the sample password for any shared environment. `POSTGRES_PASSWORD_URLENCODED` must be the percent-encoded form of the raw `POSTGRES_PASSWORD`; Compose uses the encoded value inside `DATABASE_URL`. `.env` files are ignored by Git and excluded recursively from image build contexts.

Set `AUTH_ACCESS_SECRET` to a nondefault key of at least 32 characters outside development. `WEB_ORIGIN` must match the browser's exact scheme, hostname, and port, without a trailing slash. `COOKIE_SECURE=true` is mandatory for production HTTPS; local HTTP uses `false`. Access defaults to 15 minutes (`ACCESS_TOKEN_MINUTES`), with fixed seven-day families (`REFRESH_SESSION_DAYS`). Change `WEB_ORIGIN` when changing `WEB_PORT`. Browser code never receives the signing key or `API_INTERNAL_URL`; the API proxy destination is fixed when building the web image. See [configuration and recovery](docs/deployment.md#phase-2-authentication-operations).

## Delivery milestones

The [architecture](docs/architecture.md) lists ten incremental phases. Organization/cycles/KPIs, feedback, deterministic scoring, optional AI and dashboards were delivered in Phases 3–8; Phase 9 added security/integration acceptance, and Phase 10 adds local Kubernetes/recovery plus UI refinement. See the [Phase 10 report](docs/phase-10-report.vi.md) for the current delivery boundary; production hosting is a separate decision.

Phase 5 is complete against the [plan](docs/superpowers/plans/2026-10-20-phase-5-feedback.md) and [contract](docs/phase-5-contract.md), with CI acceptance at `bf04fe2`. It separates historical reviewer rights from live report scope and suppresses small peer/subordinate groups without promising anonymity. All 26 concurrency cases passed in each of five runs.

The [Phase 6 plan](docs/superpowers/plans/2026-10-22-phase-6-performance.md) and [contract](docs/phase-6-contract.md) were prepared on 2026-10-22 against the current Phase 4–5 implementation. Phase 6 is implemented and CI-accepted at runtime `f595f23`. Eight tasks cover exact scoring, versioned reports/history, stale evidence, HR finalization/cycle closure, responsive UI reuse and acceptance; Gemini remains Phase 7.

## Feedback walkthrough (Phase 5)

Rebuild with `docker compose --env-file .env up --build --wait` to apply current head `20261024_0008`, preserving accounts and Phase 4 evidence.

1. HR opens an ACTIVE cycle and selects **Phân công phản hồi** beside a participant. Assign SELF and MANAGER explicitly; activation does not create these required assignments. Historical accounts cannot be delegated to a new manager; ADMIN must restore a disabled historical account.
2. Each assigned reviewer, including ADMIN when assigned, opens **Phản hồi của tôi**, enters a 1–5 rating and up to 2,000 plain-text characters, and confirms the immutable submission. HR has access to raw feedback.
3. HR can extend OPEN deadlines, cancel optional OPEN assignments, explicitly reopen cancelled assignments, or atomically replace PEER/SUBORDINATE reviewers while preserving the relationship/required flag. Submitted assignments cannot change. SELF/MANAGER cannot be replaced or made optional.
4. Conflicts retain draft input. Explicitly reload versions and review before confirming again; the client does not retry with new versions automatically. Expired assignments require HR to extend the deadline.
5. Current self/direct-manager scope controls employee summaries. Only the exact author's own comment is included; PEER/SUBORDINATE group statistics require three distinct submitted reviewers per group. The overall mean permits residual small-group inference; this is not an anonymity guarantee or a performance score.

All protected screens share grouped desktop navigation, a collapsible mobile menu, responsive panels and contained table scrolling. The Vietnamese guide has the complete role walkthrough.

## Organization walkthrough

As ADMIN, create HR, MANAGER and EMPLOYEE accounts in `/admin/users`. Sign out and sign in as HR: ADMIN does not inherit HR privileges. Create reference data in `/departments` and `/positions`, then employee profiles in `/employees`; select a manager and link an existing account through exact-email lookup before saving. Open a profile by clicking its name. Reference selectors support search/pagination; retiring a reference preserves existing links and prevents new assignment.

HR manages all profiles. MANAGER reads self plus direct reports; EMPLOYEE reads self. Unlinked accounts see empty scoped lists, and inaccessible UUIDs return 404. One account links to at most one employee. Employment ACTIVE/INACTIVE is independent of account activation; organization changes do not grant roles or reset passwords. See the [Phase 3 contract](docs/phase-3-contract.md).

The [Phase 2 implementation plan](docs/superpowers/plans/2026-10-03-phase-2-authentication.md) records the authentication sequence and verification gates.


## Cycle and KPI walkthrough (Phase 4)

Rebuild an existing Compose stack with `docker compose --env-file .env up --build --wait` to apply current head `20261024_0008`, retaining its volume and accounts; cycle/KPI functionality was introduced in `20261020_0004`. Back up valuable data before upgrading.

1. ADMIN may edit `/settings/scoring`: component weights must total 100.00; defaults affect future activations only. ADMIN has no HR access.
2. HR creates definitions at `/kpis`, then creates a DRAFT at `/review-cycles`, selects active employees in paginated batches, and confirms activation. Employees and their active managers need active linked accounts; references must be active. Validation identifies profiles needing attention.
3. Activation freezes policy and organization/relationship history. Only one ACTIVE is permitted. HR can close after all participants have finalized reviews; dates do not automatically close a cycle.
4. From cycle participants, HR/current direct manager opens employee KPIs. Replace a complete nonempty allocation of at most 100 distinct definitions with positive targets/weights summing exactly to 100.00. Partial edits stay in the browser.
5. Enter nonnegative actuals one row at a time; zero is valid and blank clears. Changing a target clears its actual after confirmation; changing weight retains it. Definition edits do not rewrite assignment snapshots.
6. Employees read their own allocation; managers read self/current direct reports and cannot edit their own KPIs. Transfer changes live access while preserving historical snapshots. A 409 conflict retains input until explicit reload; reload fresh data and re-enter changes, without an automatic version retry.

All business decimals are JSON strings. Feedback, calculation, finalization, AI, dashboards and demo seed remain outside Phase 4. See the [Vietnamese walkthrough](README.vi.md) and [contract](docs/phase-4-contract.md).

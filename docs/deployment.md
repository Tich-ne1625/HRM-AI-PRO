# Deployment and operations

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

That command creates disposable accounts and organization profiles; choose the project intentionally. Use a unique Compose project/empty volume when checking a clean install. Normal `down`/`up` must preserve users, employees and revision `20261019_0003`; CI checks counts before migrations run again. Cleanup must name only that acceptance project. An HTTPS deployment additionally needs a real browser cookie check with Secure enabled.

Local evidence on 2026-10-19: Python 3.12.10, PostgreSQL 16.15, Node 26.8.1 and npm 11.19.0; 387 backend tests, 35 frontend tests, Ruff/mypy, ESLint, TypeScript and production build passed. Direct versions include Next.js 16.3.8, React 19.3.0, SQLAlchemy 2.1.3 and FastAPI 0.142.2; lockfiles record the complete dependency graph. Images/CI target Node 24. `npm audit --omit=dev` reported zero vulnerabilities; full audit reported five high findings in the existing ESLint → fast-glob → micromatch → braces dev-tool chain, with no compatible fix offered (the suggested downgrade to Next 14 is not applied). Local clean-container execution remains unavailable because Docker's Linux engine/WSL prerequisite is absent.

Phase 2 acceptance passed on Linux in [InsightHR CI run 39194000937](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39194000937), commit `74ba64023020bbcf2595e98fd5eab955209671bf`: backend, frontend and docker-smoke all succeeded. This verifies both migrations, full PostgreSQL suite, frontend checks/build under Node 24, clean Compose startup, actual web proxy authentication, cookie attributes, bootstrap through stdin, HR denial, CSRF rejection, password/session revocation, refresh/logout, final nonroot image contents and persisted user count/revision after restarting PostgreSQL before migrations. The initial CI attempt stopped at an incorrect grep for hydrated login text; the corrected check validates the prerendered Suspense HTML shell, while Vitest covers hydrated form behavior. Production HTTPS/browser acceptance remains an environment-specific deployment check.

The sample password is for an isolated local workstation only. Replace it before using a shared network or CI secret store. `POSTGRES_PASSWORD` is the raw PostgreSQL password; `POSTGRES_PASSWORD_URLENCODED` is its percent-encoded equivalent for Compose's SQLAlchemy URL. If a direct-host database password contains URL-reserved characters, percent-encode it in `DATABASE_URL` as well.

## Phase 3 organization operations

No additional environment variables or services are required. Rebuild web/API images and run `alembic upgrade head` to apply `20261019_0003`. Back up any data that must be kept first. Bootstrap ADMIN as above, create HR/MANAGER/EMPLOYEE accounts through `/admin/users`, then sign in as HR to create departments/positions and employee records. The fresh database intentionally has no demo organization or seed.

HR uses `/departments`, `/positions`, `/employees` and `/employees/{id}`. Exact-email account lookup links existing users without granting HR account-administration permissions. One account links to at most one employee; `GET /auth/me`, login/refresh and ADMIN user representations report current employee IDs. Managers see self/direct reports; employees see self; unlinked accounts see empty scope; ADMIN cannot access HR data through system privileges.

Reference retirement keeps old links and prevents new assignments. Manager changes reject self/multi-node cycles, including concurrent opposing requests. Employment ACTIVE/INACTIVE does not automatically disable login. Audit metadata excludes credentials and free-text names. See [contract](phase-3-contract.md) and [API](api.md).

Local validation: 459 backend tests passed before the final real-account end-to-end test was added; that test and six container-contract checks subsequently passed. All 49 frontend tests, lint/typecheck and production build passed with the four new organization routes. Four PostgreSQL concurrency scenarios passed in each of five runs. CI is extended to apply all three migrations and test account linking/scope/transfer/cycle rejection through the actual web proxy, then verify persisted employee counts before rerunning migrations after restart. Final CI evidence follows when the workflow completes.

## Direct-host PostgreSQL

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


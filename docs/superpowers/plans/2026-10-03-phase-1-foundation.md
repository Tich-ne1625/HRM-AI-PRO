# InsightHR Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reproducible InsightHR foundation in which the Next.js application and FastAPI service build, the API reports liveness and PostgreSQL-backed readiness, Alembic owns the schema baseline, and the complete stack starts through Docker Compose.

**Architecture:** Create the two applications as independent deployable units under `apps/`, with FastAPI using synchronous SQLAlchemy sessions and PostgreSQL and Next.js using the App Router. Keep operational health endpoints outside the versioned business API; use a real system-status page to exercise web-to-API connectivity without introducing Phase 2 authentication or domain models. Docker Compose supplies local orchestration while direct host commands remain supported for development.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Pydantic Settings, Alembic, psycopg 3, pytest, Next.js App Router, React, TypeScript strict mode, Tailwind CSS, npm, Node.js 24 LTS, PostgreSQL 16, Docker, Docker Compose.

**Spec:** `docs/architecture.md`

## Global Constraints

- Use a modular monolith; do not add microservices, Redis, queues, Kafka, or other infrastructure.
- Backend dependencies flow from API to service to repository/data access to PostgreSQL; Phase 1 health code may call a focused readiness service.
- Use synchronous SQLAlchemy sessions and synchronous database route handlers so database calls do not block an asynchronous event loop.
- Business endpoints will live under `/api/v1`; operational endpoints are exactly `/health/live` and `/health/ready`.
- `/health/live` reports process availability without touching external dependencies.
- `/health/ready` fails unless PostgreSQL is reachable and its Alembic revision equals the application's head revision.
- Gemini availability must never affect readiness.
- Use UTC-aware timestamps and UUID primary keys when domain tables are introduced; Phase 1 creates no domain tables.
- Keep secrets in environment variables; `.env.example` contains placeholders and safe local defaults only.
- Run containers as nonroot and use production-capable multi-stage images.
- Pin direct dependencies and commit Python and npm lock data generated during implementation.
- Do not implement authentication, employee management, scoring, feedback, Gemini calls, dashboard analytics, seed data, or Kubernetes manifests in this phase.
- Preserve the approved architecture decisions in `docs/architecture.md`.

## Review Focus

- A PostgreSQL process that accepts TCP connections but lacks the current Alembic revision must make `/health/ready` return `503`, proven in Task 3.
- A malformed or missing `DATABASE_URL` must fail configuration clearly without exposing credentials, proven in Task 2.
- A database outage must make readiness fail while liveness continues returning `200`, proven in Task 3.
- Server-side web rendering must handle an unreachable API with a visible degraded status instead of failing the page, proven in Task 4.
- A clean Compose start must wait for PostgreSQL, apply migrations once, and only then expose healthy API and web services, proven in Task 5.

---

## Planned file map

| Path | Responsibility |
| --- | --- |
| `.editorconfig`, `.gitattributes`, `.gitignore` | Cross-platform text and repository hygiene |
| `.env.example` | Public environment contract with non-secret development examples |
| `README.md` | Phase 1 setup, commands, and scope |
| `apps/api/pyproject.toml`, `apps/api/requirements.lock` | Backend package metadata and reproducible dependency input |
| `apps/api/app/main.py` | FastAPI application factory and router registration |
| `apps/api/app/core/config.py` | Typed environment settings only |
| `apps/api/app/core/database.py` | SQLAlchemy engine/session lifecycle and connection probe |
| `apps/api/app/core/errors.py` | Stable API error envelope and exception handlers |
| `apps/api/app/modules/health/router.py` | Operational liveness/readiness HTTP routes |
| `apps/api/app/modules/health/service.py` | Database and migration readiness checks |
| `apps/api/alembic/` | Migration environment and revision history |
| `apps/api/tests/` | Configuration, health, and migration tests |
| `apps/web/src/app/` | App Router root page, metadata, styling, and error/loading boundaries |
| `apps/web/src/features/system-status/` | Typed server-side API status query and presentation |
| `apps/web/src/lib/env.ts` | Validated server/browser environment access |
| `infrastructure/docker/*.Dockerfile` | Nonroot production images for web and API |
| `docker-compose.yml` | PostgreSQL, migration, API, and web local stack |
| `docs/deployment.md` | Direct-host and Compose runbook plus troubleshooting |

### Task 1: Repository and environment contract

**Files:**
- Create: `.gitignore`
- Create: `.gitattributes`
- Create: `.editorconfig`
- Create: `.env.example`
- Create: `README.md`

**Interfaces:**
- Consumes: Approved repository root `hrm-ai/` and `docs/architecture.md`.
- Produces: Environment names `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `API_INTERNAL_URL`, `NEXT_PUBLIC_API_BASE_URL`, `CORS_ALLOWED_ORIGINS`, `APP_ENV`, `API_PORT`, and `WEB_PORT`; repository initialized on branch `main`.

- [ ] **Step 1: Initialize Git at the project root**

Run from `hrm-ai/`: `git init -b main`

Expected: `git status --short` succeeds and reports only untracked project files.

- [ ] **Step 2: Add cross-platform repository hygiene files**

Create `.editorconfig` with UTF-8, LF, final newlines, four-space Python indentation, and two-space JSON/YAML/TypeScript indentation. Create `.gitattributes` to normalize text to LF and preserve Windows scripts as CRLF if any are later added. Ignore `.env`, Python caches/virtual environments, test caches, coverage, Next.js build output, `node_modules`, logs, IDE metadata, and OS metadata; do not ignore `.env.example`.

- [ ] **Step 3: Define the public environment contract**

Create `.env.example` containing safe local values for ports/database names and placeholder values for secrets. `DATABASE_URL` uses the SQLAlchemy psycopg form `postgresql+psycopg://...`; `API_INTERNAL_URL` defaults to `http://localhost:8000`; `NEXT_PUBLIC_API_BASE_URL` defaults to `/api/v1`. Include comments distinguishing direct-host values from Compose overrides. Do not add Gemini or authentication variables until their owning phases.

- [ ] **Step 4: Add a Phase 1 README skeleton**

Document the project purpose, architecture link, prerequisites, repository layout, and Phase 1 boundary. Link to `docs/deployment.md` for commands that Task 6 will complete; do not claim unimplemented features work.

- [ ] **Step 5: Verify tracked secret hygiene**

Run: `git check-ignore .env`

Expected: `.env` is ignored.

Run: `git check-ignore .env.example`

Expected: nonzero exit because `.env.example` is not ignored.

- [ ] **Step 6: Commit the repository contract**

```bash
git add .editorconfig .gitattributes .gitignore .env.example README.md docs
git commit -m "chore: initialize InsightHR repository"
```

### Task 2: FastAPI application and validated configuration

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/requirements.lock`
- Create: `apps/api/app/__init__.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/app/core/__init__.py`
- Create: `apps/api/app/core/config.py`
- Create: `apps/api/app/core/errors.py`
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/unit/test_config.py`
- Create: `apps/api/tests/unit/test_errors.py`

**Interfaces:**
- Consumes: `APP_ENV`, `DATABASE_URL`, and an optional `CORS_ALLOWED_ORIGINS` JSON array from Task 1's environment contract.
- Produces: `Settings(BaseSettings)`, cached `get_settings() -> Settings`, `create_app() -> FastAPI`, `ApiError`, and JSON error shape `{"error":{"code":str,"message":str,"details":list},"request_id":str}`.

- [ ] **Step 1: Define backend package metadata and pinned direct dependencies**

Set package name `insighthr-api`, Python requirement `>=3.12,<3.13`, application dependencies for FastAPI, Uvicorn, SQLAlchemy 2.x, psycopg 3 binary distribution, Alembic, and Pydantic Settings, plus a `dev` extra for pytest, pytest-cov, HTTPX, Ruff, and mypy. Configure pytest paths, Ruff, and strict-enough mypy rules in `pyproject.toml`. Generate `requirements.lock` from the resolved environment with exact transitive versions after installation; do not hand-invent hashes or versions.

- [ ] **Step 2: Write failing configuration tests**

In `test_config.py`, assert:

- `Settings(app_env="test", database_url="postgresql+psycopg://user:pass@db/test")` accepts the psycopg URL and exposes no password through `repr(settings)`.
- a missing `database_url` raises a Pydantic validation error naming the `database_url` field.
- a SQLite URL raises validation error code `value_error` with a message stating PostgreSQL is required.
- production configuration rejects loopback CORS origins and wildcard `*`.

- [ ] **Step 3: Run configuration tests and verify failure**

Run from `apps/api/`: `python -m pytest tests/unit/test_config.py -q`

Expected: FAIL because `app.core.config` does not exist.

- [ ] **Step 4: Implement typed settings**

Implement `class Settings(BaseSettings)` using `SettingsConfigDict(env_file=".env", extra="ignore")`. Fields are `app_name: str = "InsightHR API"`, `app_env: Literal["development", "test", "production"]`, `database_url: SecretStr`, and `cors_allowed_origins: list[AnyHttpUrl]`. Validate PostgreSQL+psycopg scheme, reject unsafe production origins, and keep secret values out of repr/error strings. Implement `@lru_cache get_settings() -> Settings`.

- [ ] **Step 5: Run configuration tests**

Run: `python -m pytest tests/unit/test_config.py -q`

Expected: all configuration tests PASS.

- [ ] **Step 6: Write failing application/error-envelope tests**

In `test_errors.py`, construct `create_app()` with dependency-safe test settings and assert an unknown route returns `404` with exactly the stable envelope keys and a nonempty `request_id`; assert an unexpected exception returns a generic `500` message without the original exception text. Configure the test client to avoid re-raising server exceptions for the latter test.

- [ ] **Step 7: Run error-envelope tests and verify failure**

Run: `python -m pytest tests/unit/test_errors.py -q`

Expected: FAIL because the application factory and handlers do not exist.

- [ ] **Step 8: Implement the application factory and centralized errors**

Implement `ApiError(status_code: int, code: str, message: str, details: list[dict[str, object]] | None = None)`. Register handlers for `ApiError`, Starlette HTTP errors, request validation errors, and unexpected exceptions. Obtain or create an `X-Request-ID`, return it in both header and envelope, and log unexpected failures without serializing settings or request bodies. `create_app() -> FastAPI` registers middleware/handlers and will register the health router in Task 3.

- [ ] **Step 9: Run backend unit checks**

Run: `python -m pytest tests/unit -q`

Expected: all tests PASS.

Run: `python -m ruff check app tests`

Expected: no violations.

Run: `python -m mypy app`

Expected: success with no errors.

- [ ] **Step 10: Commit backend bootstrap**

```bash
git add apps/api
git commit -m "feat(api): bootstrap validated FastAPI application"
```

### Task 3: PostgreSQL, Alembic, and operational health

**Files:**
- Create: `apps/api/app/core/database.py`
- Create: `apps/api/app/modules/__init__.py`
- Create: `apps/api/app/modules/health/__init__.py`
- Create: `apps/api/app/modules/health/router.py`
- Create: `apps/api/app/modules/health/schemas.py`
- Create: `apps/api/app/modules/health/service.py`
- Create: `apps/api/alembic.ini`
- Create: `apps/api/alembic/env.py`
- Create: `apps/api/alembic/script.py.mako`
- Create: `apps/api/alembic/versions/20261003_0001_baseline.py`
- Create: `apps/api/tests/unit/test_health.py`
- Create: `apps/api/tests/integration/test_database_readiness.py`
- Modify: `apps/api/app/main.py`

**Interfaces:**
- Consumes: `Settings.database_url` from Task 2.
- Produces: `get_engine(settings: Settings) -> Engine`, `get_session_factory(engine: Engine) -> sessionmaker[Session]`, `ReadinessService.check() -> ReadinessResult`, `GET /health/live`, and `GET /health/ready`.

- [ ] **Step 1: Write failing liveness and readiness route tests**

In `test_health.py`, override the readiness dependency with a fake and assert:

- `GET /health/live` returns `200` and `{"status":"ok","service":"api"}` without calling readiness.
- ready database/current migration returns `200` and `{"status":"ready","checks":{"database":"ok","migrations":"current"}}`.
- database failure returns `503`, code `service_not_ready`, and sanitized check `database: unavailable` without the supplied password/error string.
- migration mismatch returns `503` with `migrations: pending`.
- after either readiness failure, `/health/live` still returns `200`.

- [ ] **Step 2: Run health tests and verify failure**

Run: `python -m pytest tests/unit/test_health.py -q`

Expected: FAIL because the health module does not exist.

- [ ] **Step 3: Implement database lifecycle and readiness service**

Implement lazy engine creation with `pool_pre_ping=True`, no module-level connection attempt, and explicit `dispose()` during application shutdown. `ReadinessService` executes `SELECT 1`, reads the single `alembic_version.version_num`, and compares it with the script directory's sole head. Map connection errors and absent/mismatched revisions to typed sanitized results; never return exception strings.

- [ ] **Step 4: Implement health schemas and routes**

Define Pydantic response models for liveness and readiness. Keep both routes synchronous. The readiness route turns an unsuccessful result into `ApiError(503, "service_not_ready", "Service dependencies are not ready", details=[...])`. Register the router in `create_app()`.

- [ ] **Step 5: Run unit tests**

Run: `python -m pytest tests/unit/test_health.py -q`

Expected: all health tests PASS.

- [ ] **Step 6: Configure Alembic and create an empty baseline revision**

Configure Alembic to import the application settings at runtime rather than storing a URL in `alembic.ini`. Use synchronous SQLAlchemy migration execution. The baseline revision has ID `20261003_0001`, no parent, and empty upgrade/downgrade functions because Phase 1 introduces no domain tables.

- [ ] **Step 7: Write PostgreSQL integration tests**

Mark tests with `integration`. Against an isolated PostgreSQL database supplied through `TEST_DATABASE_URL`, assert:

- readiness fails with migration status `missing` before upgrade.
- `alembic upgrade head` creates exactly one `alembic_version` row equal to `20261003_0001`.
- readiness succeeds after upgrade.
- manually setting the revision to a different value makes readiness report `pending`.
- disposing/stopping connectivity causes readiness failure without changing liveness behavior already pinned by the unit test.

- [ ] **Step 8: Run migration integration tests**

Run with an isolated PostgreSQL URL: `python -m pytest -m integration tests/integration/test_database_readiness.py -q`

Expected: all integration tests PASS and the test database is dropped by the fixture even after a failed assertion.

- [ ] **Step 9: Run the complete backend gate**

Run: `python -m pytest -q`

Expected: all unit and configured integration tests PASS; integration tests skip with an explicit reason only when `TEST_DATABASE_URL` is absent.

Run: `python -m ruff check app tests alembic`

Expected: no violations.

Run: `python -m mypy app`

Expected: success with no errors.

- [ ] **Step 10: Commit database health foundation**

```bash
git add apps/api
git commit -m "feat(api): add PostgreSQL readiness and migrations"
```

### Task 4: Next.js system-status application

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/package-lock.json`
- Create: `apps/web/next.config.ts`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/postcss.config.mjs`
- Create: `apps/web/eslint.config.mjs`
- Create: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/app/page.tsx`
- Create: `apps/web/src/app/loading.tsx`
- Create: `apps/web/src/app/error.tsx`
- Create: `apps/web/src/app/globals.css`
- Create: `apps/web/src/features/system-status/api.ts`
- Create: `apps/web/src/features/system-status/system-status.tsx`
- Create: `apps/web/src/lib/env.ts`
- Create: `apps/web/src/features/system-status/api.test.ts`
- Create: `apps/web/vitest.config.ts`

**Interfaces:**
- Consumes: server-only `API_INTERNAL_URL`; FastAPI response `{"status":"ok","service":"api"}` from Task 3.
- Produces: `getApiStatus(fetcher: typeof fetch = fetch) -> Promise<ApiStatus>`, where `ApiStatus` is `{kind:"available"; service:"api"}` or `{kind:"unavailable"}`; production standalone Next.js application.

- [ ] **Step 1: Create the strict Next.js package configuration**

Use Next.js App Router, React, TypeScript with `strict: true` and no unchecked indexed access, Tailwind CSS, ESLint, Vitest, and Testing Library only for behavior that needs a browser component. Add scripts `dev`, `build`, `start`, `lint`, `typecheck`, and `test`. Set `output: "standalone"` in `next.config.ts`. Generate and commit `package-lock.json` using npm.

- [ ] **Step 2: Write failing API status tests**

Assert `getApiStatus()`:

- returns `{kind:"available", service:"api"}` for a valid `200` liveness payload.
- returns `{kind:"unavailable"}` for non-200 responses, network rejection, timeout/abort, malformed JSON, and a successful payload with unknown fields.
- passes `{cache:"no-store"}` and a bounded abort signal to the fetch call.

- [ ] **Step 3: Run the status tests and verify failure**

Run from `apps/web/`: `npm test -- --run src/features/system-status/api.test.ts`

Expected: FAIL because `getApiStatus` does not exist.

- [ ] **Step 4: Implement validated server-side status retrieval**

Keep `API_INTERNAL_URL` server-only and validate it as an HTTP(S) URL in `src/lib/env.ts`. Implement a three-second abort timeout and validate the liveness response without trusting arbitrary JSON. Convert every provider/network/validation failure to `{kind:"unavailable"}`; do not throw from the page data path.

- [ ] **Step 5: Run status tests**

Run: `npm test -- --run src/features/system-status/api.test.ts`

Expected: all status tests PASS.

- [ ] **Step 6: Implement the Phase 1 status page and boundaries**

Create a responsive, accessible page titled `InsightHR` that explains this deployment is the project foundation and displays `API connected` or `API unavailable`. Use semantic HTML, visible keyboard focus, reduced-motion-safe styles, and a restrained neutral palette. Add root metadata, loading UI, and a client error boundary with a retry action. Do not create the application sidebar or any requested business screen yet.

- [ ] **Step 7: Run frontend gates**

Run: `npm run test -- --run`

Expected: all tests PASS.

Run: `npm run lint`

Expected: no violations.

Run: `npm run typecheck`

Expected: no TypeScript errors.

Run: `npm run build`

Expected: production build succeeds and emits standalone output.

- [ ] **Step 8: Commit the web foundation**

```bash
git add apps/web
git commit -m "feat(web): add InsightHR system status page"
```

### Task 5: Production images and Docker Compose workflow

**Files:**
- Create: `infrastructure/docker/api.Dockerfile`
- Create: `infrastructure/docker/web.Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Create: `apps/api/tests/smoke/test_container_contract.py`

**Interfaces:**
- Consumes: Backend and frontend build/run commands from Tasks 2–4 and Task 1 environment contract.
- Produces: Compose services `postgres`, `migrate`, `api`, and `web`; named volume `postgres_data`; API port `${API_PORT:-8000}`; web port `${WEB_PORT:-3000}`.

- [ ] **Step 1: Write failing container contract tests**

In `test_container_contract.py`, parse `docker-compose.yml` and assert:

- service names are exactly the required four services.
- PostgreSQL has a health check and named persistent volume.
- `migrate` waits for healthy PostgreSQL and runs `alembic upgrade head`.
- API waits for successful migration and has `/health/ready` health check.
- web waits for healthy API.
- neither application service runs as root.
- no source directory bind mounts are present in the default production-like Compose file.

- [ ] **Step 2: Run contract tests and verify failure**

Run: `python -m pytest tests/smoke/test_container_contract.py -q`

Expected: FAIL because Compose and image files do not exist.

- [ ] **Step 3: Implement the API image**

Use a multi-stage Python 3.12 slim build, install only locked runtime dependencies in the final stage, copy the application and Alembic files, create an unprivileged `insighthr` user, and start Uvicorn with one process on port 8000. Keep migration execution in the Compose `migrate` service rather than every API container entrypoint. Add a health-check-capable standard-library probe or installed client without adding curl solely for health checks.

- [ ] **Step 4: Implement the web image**

Use dependency, build, and runtime stages based on a Node 24 LTS slim image. Build Next.js standalone output, copy only standalone/server/static/public artifacts into the final stage, create an unprivileged `nextjs` user, and start on port 3000.

- [ ] **Step 5: Implement Compose orchestration**

Configure PostgreSQL 16 with its named volume and `pg_isready`. Override internal connection variables with service DNS names. Use `depends_on` conditions so migrations follow database health, API follows successful migration, and web follows API health. Add restart policies for long-running services, init processes where useful, and health intervals/timeouts that surface failure promptly. Do not mount host source in this default file.

- [ ] **Step 6: Pass static container contract tests and Compose validation**

Run: `python -m pytest tests/smoke/test_container_contract.py -q`

Expected: all contract tests PASS.

Run: `docker compose --env-file .env.example config --quiet`

Expected: exit code 0 with no schema errors.

- [ ] **Step 7: Build images without cache-dependent assumptions**

Run: `docker compose --env-file .env.example build`

Expected: both application images build successfully.

- [ ] **Step 8: Run clean-stack smoke verification**

Use a unique Compose project name for this verification so no existing volume is touched. Start the stack, then assert:

- migration exits successfully exactly once.
- API container becomes healthy and `/health/live` plus `/health/ready` return `200`.
- web container becomes healthy or its root HTTP probe returns `200`.
- the root page contains `InsightHR` and reports `API connected`.
- the `postgres_data` volume retains Alembic state across a normal `docker compose down` followed by `up`.

After verification, run `docker compose down --volumes` only for the exact unique project name created by this step.

- [ ] **Step 9: Commit container workflow**

```bash
git add .dockerignore docker-compose.yml infrastructure apps/api/tests/smoke
git commit -m "build: add reproducible Compose stack"
```

### Task 6: Developer documentation and final Phase 1 verification

**Files:**
- Create: `docs/deployment.md`
- Create: `docs/database.md`
- Create: `docs/api.md`
- Create: `docs/ai-design.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`

**Interfaces:**
- Consumes: Every command, environment name, endpoint, image, and limitation implemented in Tasks 1–5.
- Produces: Reproducible direct-host and Compose runbooks; Phase 1 completion record in architecture documentation.

- [ ] **Step 1: Document direct-host development**

In `README.md` and `docs/deployment.md`, give copyable commands for prerequisites, `.env` creation, Python environment installation, frontend installation, starting PostgreSQL, applying Alembic, starting API/web, and stopping services. Document Windows PowerShell and portable commands where syntax differs. State which terminal and working directory each command uses.

- [ ] **Step 2: Document Docker Compose operation and recovery**

Describe build/start/status/log/stop commands, health endpoints, expected ports, how migration failures appear, how to retry a failed migration after correction, and how to remove the demo database volume with an explicit data-loss warning. Do not imply that `down` removes the database volume.

- [ ] **Step 3: Document Phase 1 database and API contracts**

In `docs/database.md`, describe SQLAlchemy/Alembic ownership, baseline revision, direct-host versus container URLs, migration workflow, and the absence of domain tables. In `docs/api.md`, document health payloads, status codes, request IDs, and stable error envelope. In `docs/ai-design.md`, record that Gemini is intentionally absent until Phase 7 and restate the approved isolation constraints without inventing an integration.

- [ ] **Step 4: Update architecture status truthfully**

Add a short implementation-status section to `docs/architecture.md` marking only Phase 1 artifacts actually completed. Keep all future trees and APIs described as planned. Do not mark Phase 1 complete until the remaining checks pass.

- [ ] **Step 5: Run the complete local quality gate**

Backend from `apps/api/`:

```bash
python -m pytest -q
python -m ruff check app tests alembic
python -m mypy app
```

Frontend from `apps/web/`:

```bash
npm run test -- --run
npm run lint
npm run typecheck
npm run build
```

Expected: every command exits 0. PostgreSQL integration tests must run rather than skip in the final gate.

- [ ] **Step 6: Reproduce the documented clean Compose setup**

Follow the README from a clean unique Compose project and empty project-specific volume. Confirm migrations, API readiness, root page connectivity, normal stop/start persistence, and clean shutdown. Record the exact commands and observed versions in a short `Phase 1 verification` section of `docs/deployment.md`.

- [ ] **Step 7: Inspect production artifacts**

Verify both application containers run as nonroot, `.env` and tests are absent from final image layers, the API image contains Alembic runtime files, the web image contains standalone output, and neither image exposes development servers.

- [ ] **Step 8: Review scope and repository state**

Run: `git status --short`

Expected: only intentional documentation changes remain before the final commit.

Confirm no authentication, domain entities, scoring, Gemini client, seed data, dashboard charts, or Kubernetes manifests were added.

- [ ] **Step 9: Commit Phase 1 documentation and completion evidence**

```bash
git add README.md docs
git commit -m "docs: complete Phase 1 foundation runbook"
```

- [ ] **Step 10: Final branch verification**

Run: `git status --short`

Expected: clean working tree.

Run: `git log --oneline --decorate -6`

Expected: the Phase 1 commits are present in task order, with no generated secrets or build output tracked.

## Phase 1 definition of done

- A new developer can follow the documentation on Windows or through Docker Compose without undocumented steps.
- The API starts only with valid configuration, returns stable error envelopes, and exposes tested liveness/readiness endpoints.
- Readiness proves both PostgreSQL connectivity and current Alembic schema state.
- The Next.js root page builds in strict mode and communicates API status without crashing during API failure.
- Compose starts PostgreSQL, runs migrations, then starts healthy API and web containers using persistent database storage.
- Backend tests, PostgreSQL integration tests, linting, type checking, frontend tests, frontend linting/type checking/build, and the clean Compose smoke flow all pass.
- Documentation states clearly that business features begin in Phase 2 and are not yet implemented.

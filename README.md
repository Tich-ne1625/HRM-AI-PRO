# InsightHR

[Đọc hướng dẫn bằng tiếng Việt](README.vi.md)

InsightHR is an AI-assisted employee performance management system built as a university capstone. It focuses on employee records, review cycles, KPIs, authorized 360-degree feedback, deterministic scoring, and advisory Gemini analysis.

The project is a modular monolith: a Next.js web application, a FastAPI backend, and PostgreSQL. Read the approved [architecture proposal](docs/architecture.md) for the complete design and business rules.

## Current scope

Phase 1 foundation and Phase 2 authentication are implemented and CI-verified: secure cookie login, refresh rotation/replay detection, logout, password change, current identity, ADMIN account management, transactional audits, and reusable role policies. Container acceptance evidence is recorded in [deployment.md](docs/deployment.md). Organization and employee workflows begin in Phase 3; `employee_id` remains `null`.

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

Review every generated migration before running it. The sole head is `20261003_0002`, after baseline `20261003_0001`; it adds users, refresh sessions, and audits.

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

## Future phases

The [Phase 3 plan (Vietnamese)](docs/superpowers/plans/2026-10-19-phase-3-organization.md) introduces departments, positions, employee records, user–employee links, and organization-scoped access. Review cycles, KPIs, feedback, performance scoring, Gemini, dashboards, seed data, and Kubernetes follow [the architecture](docs/architecture.md).

The [Phase 2 implementation plan](docs/superpowers/plans/2026-10-03-phase-2-authentication.md) records the authentication sequence and verification gates.


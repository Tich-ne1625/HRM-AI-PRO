# InsightHR

[Đọc hướng dẫn bằng tiếng Việt](README.vi.md)

InsightHR is an AI-assisted employee performance management system built as a university capstone. It focuses on employee records, review cycles, KPIs, authorized 360-degree feedback, deterministic scoring, and advisory Gemini analysis.

The project is a modular monolith: a Next.js web application, a FastAPI backend, and PostgreSQL. Read the approved [architecture proposal](docs/architecture.md) for the complete design and business rules.

## Current scope

Phase 1 is implemented: repository conventions, validated API configuration, stable API errors, liveness/readiness checks, PostgreSQL/Alembic integration, a Next.js system-status page, production container definitions, Docker Compose, and CI verification. Authentication and business features begin in Phase 2 and are not implemented yet.

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

Review every generated migration before running it. Phase 1 contains the empty baseline revision `20261003_0001`; domain tables begin in later phases.

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

The integration fixture removes the `alembic_version` table. Never point `TEST_DATABASE_URL` at a development, staging, or production database.

## Environment and secrets

`.env.example` is the public configuration contract. Copy it to `.env` and replace the sample password for any shared environment. `POSTGRES_PASSWORD_URLENCODED` must be the percent-encoded form of the raw `POSTGRES_PASSWORD`; Compose uses the encoded value inside `DATABASE_URL`. `.env` files are ignored by Git and excluded recursively from image build contexts. Phase 1 does not contain authentication or Gemini secrets.

## Future phases

Authentication and RBAC are Phase 2. Departments, positions, employees, review cycles, KPI scoring, feedback, performance calculations, Gemini analysis, dashboards, seed data, and Kubernetes will be added incrementally according to [the architecture](docs/architecture.md). Gemini configuration and demo seed commands will be documented when their implementations exist.

The reviewed implementation sequence for the next slice is in the [Phase 2 authentication plan](docs/superpowers/plans/2026-10-03-phase-2-authentication.md).


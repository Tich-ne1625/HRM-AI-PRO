# Deployment and operations

## Environment files

The repository root `.env.example` lists every Phase 1 variable. Compose reads a root `.env`; direct-host applications read `apps/api/.env` and `apps/web/.env.local` from their respective working directories.

The sample password is for an isolated local workstation only. Replace it before using a shared network or CI secret store. If a database password contains URL-reserved characters, percent-encode it in `DATABASE_URL`.

## Direct-host PostgreSQL

Create a local role and database with PostgreSQL 16 administrative credentials:

```sql
CREATE USER insighthr WITH PASSWORD 'replace-this-password';
CREATE DATABASE insighthr OWNER insighthr;
```

Set `DATABASE_URL=postgresql+psycopg://insighthr:<encoded-password>@localhost:5432/insighthr`, then run from `apps/api`:

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
- 18 backend tests, including two real PostgreSQL integration tests
- Ruff and mypy clean
- Node.js 26.8.1 used to verify the Node 24-targeted application
- 6 frontend tests, ESLint, strict TypeScript, and Next.js production build clean
- Docker Compose v5.5.1 accepted the Compose model
- Static container-contract tests passed

The local Docker engine could not start because this Windows installation requires an Administrator session and restart to enable WSL. GitHub's Linux runner built both production images and passed the clean Compose startup, migration, API readiness, and web-to-API smoke checks in [`Phase 1 CI` run 37131367452](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/37131367452).


# InsightHR

InsightHR is an AI-assisted employee performance management system built as a university capstone. It focuses on employee records, review cycles, KPIs, authorized 360-degree feedback, deterministic scoring, and advisory Gemini analysis.

The project uses a modular monolith: a Next.js web application, a FastAPI backend, and PostgreSQL. Read the approved [architecture proposal](docs/architecture.md) for the complete design and business rules.

## Phase 1 scope

Phase 1 establishes the repository, FastAPI health and readiness endpoints, PostgreSQL and Alembic connectivity, a Next.js system-status page, and a Docker Compose workflow. Authentication and business features begin in later phases and are not implemented yet.

## Repository layout

```text
apps/
  api/       FastAPI application
  web/       Next.js application
docs/        Architecture and operational documentation
infrastructure/
  docker/    Production container definitions
```

## Prerequisites

- Git
- Python 3.12
- Node.js 24 LTS and npm
- PostgreSQL 16 for direct-host development
- Docker with Docker Compose for the container workflow

Setup and execution commands will be maintained in `docs/deployment.md` as Phase 1 is implemented.


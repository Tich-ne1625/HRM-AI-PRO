# Database design status

## Phase 1 baseline

PostgreSQL 16 is the only supported database. SQLAlchemy uses the synchronous psycopg 3 driver, and Alembic exclusively owns schema migrations. Phase 1 deliberately creates no domain tables; revision `20261003_0001` establishes the migration baseline and creates Alembic's version marker.

The API creates its SQLAlchemy engine lazily with connection pre-ping. Application startup does not require an immediate database connection, so liveness can report process health during an outage. Readiness executes `SELECT 1`, verifies `alembic_version` exists, requires one row, and compares that revision with Alembic's sole application head.

## Migration workflow

Run migration commands from `apps/api` so `.env`, `alembic.ini`, and the application package resolve consistently:

```bash
alembic current
alembic upgrade head
alembic history
```

Future SQLAlchemy models must register their metadata through `app.core.database.metadata`. Every generated migration must be reviewed for constraints, indexes, nullability, data conversion, and downgrade behavior before it is applied.

Do not edit a migration that has already been used by another environment. Add a new revision instead.

## Test isolation

Integration tests require `TEST_DATABASE_URL` pointing to a dedicated PostgreSQL database. The test resets `alembic_version` to exercise missing, current, and stale migration states. It must never target a database containing application data.

## Planned domain model

The approved tables, constraints, snapshots, concurrency rules, and ERD remain in [architecture.md](architecture.md). They will be introduced only by the phase that owns each feature, beginning with users and refresh sessions in Phase 2.


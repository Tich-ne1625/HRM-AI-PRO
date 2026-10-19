# Database design status

## Phase 2 authentication schema

Sole current head: `20261003_0002`, following baseline `20261003_0001`. The migration creates:

| Table | Fields/constraints |
| --- | --- |
| `users` | UUID PK; normalized email `VARCHAR(254)` UNIQUE with lowercase check; Argon2id `password_hash VARCHAR(255)`; constrained `ADMIN/HR/MANAGER/EMPLOYEE` role; active boolean; UTC-aware created/updated timestamps |
| `auth_sessions` | UUID PK/family/user FK; unique SHA-256 `token_hash VARCHAR(64)`; family-bound `csrf_hash VARCHAR(64)`; absolute UTC expiry; nullable consumed/revoked timestamps and successor FK; active-family partial index, expiry index |
| `audit_logs` | UUID PK; nullable actor user FK; action/entity/request identifiers; UTC timestamp; allowlisted JSONB metadata; actor/timestamp indexes |

User/refresh/audit foreign keys use RESTRICT; no delete cascade removes security history. `app.models` imports all models for Alembic metadata. Application services append audits and never expose general edit/delete routes for audit rows. This is an application convention, not a database-enforced immutable ledger.

Emails use email-validator normalization with `check_deliverability=False`, then Unicode casefold; creation/login do not depend on DNS availability. Raw refresh or CSRF credentials are never stored in PostgreSQL. Access tokens reference user/family, without authoritative role/status claims.

Refresh rows form a chain with one `replacement_id` per consumed predecessor. Rotation locks owner then token row, checks persisted state after locking, keeps absolute expiry and family CSRF, inserts one successor, and commits with audit. Consumed rows stay available for replay detection at least through expiry; automated pruning is not implemented. Replay revokes every family row, including the current successor. Logout revokes one family; password change revokes all other families; deactivation revokes all user families.

Login, rotation, logout and password changes lock the user first, preventing a concurrent old-password login from creating a surviving family after password change. User management locks active ADMINs in UUID order before actor/target locks and rechecks authorization/count under those locks. Services own transactions; repositories flush without committing. Audit failure rolls back the entire mutation.

Implemented audit actions: `user.bootstrap_created`, `user.created`, `user.role_changed`, `user.status_changed`, `user.password_changed`, `auth.login_succeeded`, `auth.login_failed`, `auth.refresh_succeeded`, `auth.refresh_reuse_detected`, `auth.logout`. Metadata permits only role/previous-role and active/previous-active fields; no passwords, cookies, tokens, hashes or request bodies.

Employee, department, position and business tables are still planned for Phase 3 onward. No user–employee foreign key exists yet; API employee references remain null.

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

Integration tests require `TEST_DATABASE_URL` pointing to a disposable PostgreSQL database whose name ends with `_test`. Fixtures drop only known user/session/audit tables in FK-safe order and `alembic_version`, then migrate to the sole head. Never point them at data that must be kept. Concurrency tests use independent SQLAlchemy sessions and barriers; all database connections set UTC session time zone.

## Planned domain model

The remaining tables, constraints, snapshots, concurrency rules and ERD are in [architecture.md](architecture.md). Only the phase that owns a feature introduces its tables.


# Database design status

## Phase 3 organization schema

Current sole head is `20261020_0005` (feedback assignments/submissions), following cycle/KPI `20261020_0004`, organization `20261019_0003`, authentication `20261003_0002` and baseline `20261003_0001`. Upgrade/downgrade and metadata parity are tested against PostgreSQL.

| Table | Contract |
| --- | --- |
| `departments` | UUID, unique normalized `code VARCHAR(32)`, nonblank `name VARCHAR(200)`, active boolean, UTC-aware created/updated timestamps |
| `positions` | UUID, unique normalized code, nonblank title, active boolean, UTC timestamps |
| `employees` | UUID, unique normalized employee_code, nonblank display_name, required department/position FK, nullable manager self-FK, nullable UNIQUE user FK, constrained ACTIVE/INACTIVE employment status, UTC timestamps |

Codes have a database ASCII-uppercase regex check. Employee self-management is blocked by CHECK; indexes support department/position/manager lookups, and the unique user constraint enforces one employee per account while permitting multiple unlinked employees. Foreign keys use RESTRICT; no history-deleting cascades or DELETE APIs are added.

All organization writers acquire advisory transaction lock `730031`, then ordered active-admin locks, ordered participating user locks, then organization rows. This matches user-management/auth lock order and prevents reporting-tree write skew, duplicate link races and cross-module deadlocks. The service rereads graph/reference/user state under the guard. A single shared guard intentionally serializes the modest capstone write workload; scoped reads do not acquire it.

Retiring references/managers preserves existing links. Newly changed links must target active references; unchanged inactive links can be retained. Employment status does not activate/deactivate login accounts. SQL list/detail/count scopes derive employee identity from the current user link, not JWT fields. Account presentation batches employee links for user lists.

Organization audits are department.created/updated, position.created/updated and employee.created/updated. Their separate metadata allowlist stores changed field names, codes, status, relevant UUIDs and previous user/manager IDs, without free-text names or lookup emails. Audit failure rolls back every mutation.

## Phase 2 authentication schema

Authentication revision: `20261003_0002`, following baseline `20261003_0001`. The migration creates:

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

Phase 3 now supplies organization/employee tables and the nullable unique `employees.user_id` foreign key. Review-cycle, KPI, feedback, scoring and AI tables remain planned. API employee references reflect current links and remain null only for unlinked accounts.

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

Integration tests require `TEST_DATABASE_URL` pointing to a disposable PostgreSQL database whose name ends with `_test`. Fixtures drop only known application tables in FK-safe order (KPI evidence/definitions, participants/cycles/config, organization, audit/sessions/users) and `alembic_version`, then migrate to the sole head. Never point them at data that must be kept. Concurrency tests use independent SQLAlchemy sessions and barriers; all database connections set UTC session time zone.

## Planned domain model

The remaining tables, constraints, snapshots, concurrency rules and ERD are in [architecture.md](architecture.md). Only the phase that owns a feature introduces its tables.


## Phase 4 cycle and KPI schema

Revision `20261020_0004` adds `system_config`, `review_cycles`, `cycle_participants`, `kpi_definitions` and `employee_kpis`. The migration inserts only singleton scoring defaults (70/30, cap 100.00); it creates no accounts or demo records. Partial unique indexing permits at most one ACTIVE cycle, dates and numeric evidence have CHECK constraints, and history references use RESTRICT. Quantities are NUMERIC(14,4), allocation weights NUMERIC(5,2). Nullable JSON snapshots use SQL NULL in DRAFT. Participant evidence versions coordinate later evidence writers. Snapshot DTO and lifecycle behavior follow the [Phase 4 contract](phase-4-contract.md); cycle/KPI workflows are implemented, while scoring/finalization remain Phase 6. PostgreSQL tests cover metadata parity, a clean install, constraints, and downgrade/upgrade preserving Phase 3 records.


| Table | Fields and consistency rules |
| --- | --- |
| `system_config` | Integer singleton id=1, version >=1, object JSONB scoring_policy and UTC timestamps; initial policy schema_version=1, 70.00/30.00/cap 100.00 |
| `review_cycles` | UUID, name VARCHAR(200), date period, constrained DRAFT/ACTIVE/CLOSED, version >=1; frozen policy JSONB + policy_source_version + activated_at required outside DRAFT, all SQL NULL in DRAFT; partial UNIQUE status where ACTIVE |
| `cycle_participants` | UUID, cycle/employee FK RESTRICT, UNIQUE(cycle_id,employee_id), evidence_version >=1, private snapshot JSONB nullable in DRAFT, finalized_at nullable; employee index for scoped lookup |
| `kpi_definitions` | UUID, unique normalized code VARCHAR(32), nonblank name VARCHAR(200)/unit VARCHAR(50), description VARCHAR(2000), constrained direction, is_active, version >=1, UTC timestamps |
| `employee_kpis` | UUID, participant/definition FK RESTRICT, UNIQUE(participant_id,definition_id), object definition_snapshot, positive target NUMERIC(14,4), nullable nonnegative actual NUMERIC(14,4), weight NUMERIC(5,2) in (0,100], UTC timestamps; NaN rejected by numeric checks |

Participant snapshots have a schema version, employee and department/position identity/labels, employee/user IDs for SELF and manager, and the direct-report relationships at activation (including people outside participation). Private snapshots are parsed into public allowlisted DTOs, never serialized wholesale. Organization/default changes do not mutate activated snapshots. Live access still follows current account linkage and manager relations.

Aggregate allocation weight is a service invariant, not a per-row CHECK: lock the participant, require expected_evidence_version, validate full unique allocation with exactly 100.00, reconcile and audit in one transaction. All evidence writers in future phases must reuse this lock/version. Assignment snapshots only refresh after removal/reassignment; changing a target clears actual, weight changes retain it. No PerformanceReview, FeedbackAssignment or AI tables are introduced here.

Every Phase 4 writer follows guard 730031 → sorted active ADMIN/user locks → active family → config if needed → cycle → participants → definitions/assignments. Activation locks SELF/manager accounts against deactivation and reads graph/defaults consistently. User administration retains its established admin-first order and does not wait on this guard. Phase 4 audit allowlist permits only field names, codes, states, UUIDs, counts and versions. Audit failure rolls back evidence, removed rows and version changes.

## Phase 5 feedback schema

Revision `20261020_0005` adds exactly `feedback_assignments` and `feedback`, without backfilling historical assignments. Assignment identity is UNIQUE(participant_id,reviewer_id), including cancelled rows. A partial unique index prevents multiple non-cancelled SELF/MANAGER assignments; CHECK constraints enforce mandatory required flags, positive versions, object eligibility snapshots and allowed statuses/relationships. Inbox indexing covers reviewer/status/deadline. `feedback.assignment_id` is UNIQUE with rating 1–5 and a 2,000-character comment. History FKs use RESTRICT.

Assignment mutations and submissions lock guard → active ADMIN → sorted actor/reviewer users → session family → cycle → participant → assignment UUIDs. They increment the shared participant evidence version once, alongside assignment versions, within the audit transaction. Feedback and KPI writes therefore compete on the same version. Cancellation retains history; reopening retains identity/snapshot; replacement cancels and creates/reopens atomically. Submitted data has no mutation API. Phase 6 must use original rating sum/count, not the rounded display mean.

SQL owner scope is independent of current organization/report access. HR raw presenters are distinct from public summaries; small-group suppression applies separately to PEER/SUBORDINATE. List presentation joins context in a bounded query count, with a regression test against N+1 reads. The [contract](phase-5-contract.md) specifies historical eligibility and account recovery limits. Phase 5 acceptance evidence is recorded in its plan.

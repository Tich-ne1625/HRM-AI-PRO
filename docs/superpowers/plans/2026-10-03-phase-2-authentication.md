# InsightHR Phase 2 Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver secure cookie authentication, refresh-token rotation, logout, current-user identity, password changes, reusable role policies, ADMIN user management, audit records, and the minimum web flows needed to exercise them end to end.

**Architecture:** Extend the existing FastAPI modular monolith with `auth`, `users`, and `audit` modules backed by PostgreSQL. Use Argon2id password hashes, 15-minute signed access tokens, opaque refresh tokens stored only as SHA-256 hashes, session-family rotation with replay revocation, exact-origin checks, and a session-bound CSRF token. Keep the public Phase 1 status page, add same-origin Next.js proxying plus a client authentication boundary, and defer employee profiles and organization scope to Phase 3.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 synchronous sessions, PostgreSQL 16, Alembic, argon2-cffi 25.1.0, PyJWT 2.15.1, email-validator 2.3.0, pytest, Next.js 16 App Router, React 19, TypeScript 6 strict mode, TanStack Query 5.104.1, React Hook Form 7.89.0, Zod 4, Testing Library, Vitest.

**Spec:** `docs/architecture.md` sections “Authentication and deployment”, “Database ERD”, “Role and scope policy”, and “REST API map”.

## Global Constraints

- Preserve the modular monolith; do not add a separate identity service, Redis, queues, or external session storage.
- All business endpoints use `/api/v1`; `/health/live` and `/health/ready` remain public and unchanged.
- Route handlers remain synchronous when they use synchronous SQLAlchemy.
- Use UUID primary keys and timezone-aware UTC timestamps.
- Passwords use Argon2id. Never log, serialize, audit, or persist a plain-text password.
- Password input is 12–128 Unicode characters, is never silently trimmed, and the replacement password must differ from the current password; do not add composition rules.
- Access cookies live for 15 minutes. Refresh session families have one fixed seven-day absolute expiry that rotation never extends.
- Refresh tokens are random opaque values; PostgreSQL stores only unique SHA-256 hashes and retains consumed hashes until absolute expiry.
- A refresh token is consumed atomically. Reuse revokes every token row in that family.
- Access authorization checks an active session family plus the user’s current `is_active` and role values on every request.
- Cookies are HttpOnly where applicable, `SameSite=Lax`, `Secure` outside explicit local HTTP development, and use the scoped paths defined in Task 3.
- Login performs an exact allowed-origin check. Every other cookie-authenticated mutation requires exact origin plus a session-bound CSRF token.
- ADMIN has system-administration privileges only; it does not inherit HR domain access.
- The last active ADMIN cannot be deactivated or demoted, including under concurrent requests.
- A user may change only their own password. Successful password change revokes every other session family.
- Successful mutations and their domain audit records commit in one transaction. Audit metadata never contains tokens, cookies, password hashes, or request bodies.
- Do not add Employee, Department, Position, review, KPI, feedback, scoring, Gemini, dashboard, seed, or Kubernetes behavior in this phase.
- Pin direct dependencies and regenerate both Python and npm lock data. Final container images must remain nonroot and free of development tooling and environment files.

## Review Focus

- Two concurrent refresh requests using the same token must never produce two usable successor sessions; replay detection revokes the family, proven with PostgreSQL concurrency tests in Task 4.
- A disabled user, demoted user, revoked family, expired family, or deleted cookie must invalidate an otherwise correctly signed access token, proven in Task 5.
- Cross-origin login and missing, mismatched, or cross-session CSRF tokens must fail without changing database state, proven in Tasks 3 and 4.
- Two concurrent attempts to deactivate or demote the final two ADMIN users must leave at least one active ADMIN, proven in Task 6.
- Malformed cookies, JWTs, UUID claims, email addresses, pagination values, and JSON bodies must return stable sanitized errors without leaking credentials or token material, proven across Tasks 1, 3, 5, and 6.

---

## Planned file map

| Path | Responsibility |
| --- | --- |
| `.env.example` | Phase 2 secret, origin, and cookie configuration contract |
| `apps/api/app/core/config.py` | Validated auth lifetimes, signing secret, origin, and cookie policy |
| `apps/api/app/core/database.py` | Request-scoped synchronous SQLAlchemy session dependency |
| `apps/api/app/core/security.py` | Password hashing, token generation/hashing, JWT encoding/decoding, cookie names |
| `apps/api/app/core/policies.py` | Current-user/session resolution, exact-origin/CSRF checks, role dependencies |
| `apps/api/app/modules/auth/` | Login, refresh, logout, current user, password change |
| `apps/api/app/modules/users/` | User model, repository, ADMIN list/create/update API |
| `apps/api/app/modules/audit/` | Append-only audit model and write helper |
| `apps/api/app/modules/auth/models.py` | Refresh-token instance rows and session-family state |
| `apps/api/alembic/versions/20261003_0002_authentication.py` | User, auth session, and audit schema |
| `apps/api/app/cli/create_admin.py` | Interactive first-ADMIN bootstrap command |
| `apps/web/src/lib/api-client.ts` | Same-origin cookie client, CSRF header, single-flight refresh and one retry |
| `apps/web/src/features/auth/` | Auth query state, login/logout/change-password UI and validation |
| `apps/web/src/app/(auth)/login/page.tsx` | Public login page |
| `apps/web/src/app/(protected)/` | Client-guarded account and ADMIN user-management pages |
| `apps/web/src/app/providers.tsx` | Query client and authentication providers |
| `apps/web/next.config.ts` | `/api/v1/*` proxy to the internal API |
| `docs/api.md`, `docs/database.md`, `docs/deployment.md` | Phase 2 API, schema, bootstrap, cookies, and recovery documentation |

### Task 1: Authentication configuration and cryptographic primitives

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/requirements.lock`
- Modify: `apps/api/app/core/config.py`
- Create: `apps/api/app/core/security.py`
- Modify: `apps/api/tests/unit/test_config.py`
- Modify: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/unit/test_security.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: existing `Settings`, `SecretStr`, and sanitized configuration validation.
- Produces: `Settings.access_signing_key`, `Settings.web_origin`, `Settings.cookie_secure`, `Settings.access_token_minutes`, `Settings.refresh_session_days`; `PasswordService.hash/verify`, `TokenService.create_access_token/decode_access_token`, `new_opaque_token()`, and `hash_opaque_token()`.

- [ ] **Step 1: Pin authentication dependencies**

Add exact direct dependencies `argon2-cffi==25.1.0`, `PyJWT==2.15.1`, and `email-validator==2.3.0`, install through `requirements.lock` constraints, and regenerate the lock from the resolved Python 3.12 environment.

- [ ] **Step 2: Write failing auth-configuration tests**

In `test_config.py`, assert that production rejects a missing/default/short `AUTH_ACCESS_SECRET`, production requires `COOKIE_SECURE=true`, `WEB_ORIGIN` is one exact HTTP(S) origin without credentials/path/query/fragment, lifetimes default to `15` minutes and `7` days, and validation errors never reveal the secret.

- [ ] **Step 3: Run configuration tests and verify failure**

Run: `python -m pytest tests/unit/test_config.py -q`

Expected: FAIL because Phase 2 fields do not exist.

- [ ] **Step 4: Implement the validated settings fields**

Add fields using these environment names: `AUTH_ACCESS_SECRET`, `WEB_ORIGIN`, `COOKIE_SECURE`, `ACCESS_TOKEN_MINUTES`, and `REFRESH_SESSION_DAYS`. Development may use the documented placeholder key and insecure cookies; test and production settings must receive an explicit key of at least 32 characters. Preserve `hide_input_in_errors=True`.

Update `tests/conftest.py` with a test-only 32-character signing key and exact test origin so pre-existing application tests continue to create settings explicitly without weakening nondevelopment validation.

- [ ] **Step 5: Write failing security primitive tests**

In `test_security.py`, test:

- Argon2id hashes never contain the password, verify correctly, reject a wrong password, and request rehash for obsolete parameters.
- access claims contain `sub`, `sid`, `type="access"`, `iat`, and `exp`; invalid signature, wrong type, malformed UUID, and expiry all fail with one sanitized token error.
- `new_opaque_token()` yields at least 256 bits of entropy and two calls differ.
- `hash_opaque_token()` is deterministic SHA-256 output and never returns the token.

- [ ] **Step 6: Run security tests and verify failure**

Run: `python -m pytest tests/unit/test_security.py -q`

Expected: FAIL because `app.core.security` does not exist.

- [ ] **Step 7: Implement security primitives**

Create immutable `AccessClaims(user_id: UUID, family_id: UUID, issued_at: datetime, expires_at: datetime)`. `PasswordService` wraps one configured Argon2id hasher. `TokenService` accepts the signing key and an injectable UTC clock. Define cookie names `insighthr_access`, `insighthr_refresh`, and `insighthr_csrf`; never accept a JWT algorithm from token input.

- [ ] **Step 8: Run Task 1 gates**

Run: `python -m pytest tests/unit/test_config.py tests/unit/test_security.py -q`

Run: `python -m ruff check app tests alembic && python -m mypy app`

Expected: all pass.

- [ ] **Step 9: Commit Task 1**

```bash
git add .env.example apps/api
git commit -m "feat(auth): add secure authentication primitives"
```

### Task 2: User, session, audit schema and first-ADMIN bootstrap

**Files:**
- Create: `apps/api/app/modules/users/__init__.py`
- Create: `apps/api/app/modules/users/models.py`
- Create: `apps/api/app/modules/users/repository.py`
- Create: `apps/api/app/modules/auth/__init__.py`
- Create: `apps/api/app/modules/auth/models.py`
- Create: `apps/api/app/modules/auth/repository.py`
- Create: `apps/api/app/modules/audit/__init__.py`
- Create: `apps/api/app/modules/audit/models.py`
- Create: `apps/api/app/modules/audit/service.py`
- Create: `apps/api/app/models.py`
- Create: `apps/api/alembic/versions/20261003_0002_authentication.py`
- Create: `apps/api/app/cli/__init__.py`
- Create: `apps/api/app/cli/create_admin.py`
- Modify: `apps/api/alembic/env.py`
- Create: `apps/api/tests/integration/test_auth_schema.py`
- Create: `apps/api/tests/integration/test_create_admin.py`

**Interfaces:**
- Consumes: shared SQLAlchemy `metadata`, `PasswordService`, `DATABASE_URL`.
- Produces: `User`, `UserRole`, `AuthSession`, `AuditLog`, repositories, `AuditWriter.record(...)`, and `python -m app.cli.create_admin --email EMAIL [--password-stdin]`.

- [ ] **Step 1: Write failing PostgreSQL schema tests**

Assert migration `20261003_0002` creates:

- `users`: UUID `id`, case-insensitive normalized email uniqueness, `password_hash`, role constrained to `ADMIN|HR|MANAGER|EMPLOYEE`, `is_active`, UTC `created_at/updated_at`.
- `auth_sessions`: UUID `id`, `family_id`, `user_id`, unique `token_hash`, `csrf_hash`, fixed `expires_at`, nullable `consumed_at/revoked_at/replacement_id`, and indexes for active family and expiry lookup.
- `audit_logs`: UUID `id`, nullable `actor_id`, action/entity/request identifiers, UTC timestamp, JSONB metadata, and timestamp/actor indexes.
- foreign keys prevent deleting referenced users and session replacement links.

- [ ] **Step 2: Run schema tests and verify failure**

Run with `TEST_DATABASE_URL`: `python -m pytest tests/integration/test_auth_schema.py -q`

Expected: FAIL because the revision and models do not exist.

- [ ] **Step 3: Implement models and migration**

Use SQLAlchemy 2 typed declarative mappings tied to shared `metadata`. `app/models.py` imports every model so Alembic sees the complete metadata. Store normalized email as lowercase text with a database unique constraint. `AuditLog` is append-only through application services; do not configure ORM delete cascades for security history.

- [ ] **Step 4: Implement focused repositories and audit writer**

Define `UserRepository.get_by_normalized_email`, `get_by_id`, `add`, and ordered active-admin locking. Define `AuthSessionRepository.get_by_token_hash_for_update`, `get_active_family`, `revoke_family`, `revoke_other_families`, and `add_successor`. Repositories flush but never commit. `AuditWriter.record(session, actor_id, action, entity_type, entity_id, request_id, metadata)` accepts allowlisted metadata assembled by services.

- [ ] **Step 5: Write failing first-ADMIN CLI tests**

Test normalization, Argon2id storage, interactive password confirmation, duplicate-email refusal, 12/128-character boundaries, audit creation, rollback on failure, and `--password-stdin` consuming two matching lines without echo. Patch `getpass`/stdin in tests; never place a password in command arguments or environment variables.

- [ ] **Step 6: Implement the bootstrap command**

`python -m app.cli.create_admin --email EMAIL` prompts twice via `getpass`. `--password-stdin` is the explicit noninteractive CI alternative and reads two lines. Both paths create one active ADMIN and `user.bootstrap_created` audit in one transaction, and exit nonzero without changing data for duplicates or invalid input. Validate then store email as `validate_email(email).normalized.casefold()` with a maximum of 254 characters.

- [ ] **Step 7: Run Task 2 gates**

Run: `python -m pytest tests/integration/test_auth_schema.py tests/integration/test_create_admin.py -q`

Expected: all pass against PostgreSQL.

- [ ] **Step 8: Commit Task 2**

```bash
git add apps/api
git commit -m "feat(auth): add user and session persistence"
```

### Task 3: Login, cookies, current-user response and exact-origin policy

**Files:**
- Modify: `apps/api/app/core/database.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/app/modules/auth/schemas.py`
- Create: `apps/api/app/modules/auth/service.py`
- Create: `apps/api/app/modules/auth/cookies.py`
- Create: `apps/api/app/modules/auth/router.py`
- Create: `apps/api/tests/unit/test_auth_cookies.py`
- Create: `apps/api/tests/integration/test_auth_login.py`

**Interfaces:**
- Consumes: `UserRepository`, `AuthSessionRepository`, security primitives, `AuditWriter`, and application `session_factory`.
- Produces: `POST /api/v1/auth/login`, cookie-writing helpers, `AuthService.login(...) -> AuthResult`, and sanitized `CurrentUser` schema reused by `/auth/me`.

- [ ] **Step 1: Write failing cookie-policy unit tests**

Assert successful login sets:

- `insighthr_access`: HttpOnly, path `/`, SameSite Lax, max age 900.
- `insighthr_refresh`: HttpOnly, path `/api/v1/auth/refresh`, SameSite Lax, max age no longer than the family absolute expiry.
- `insighthr_csrf`: readable by the browser, path `/`, SameSite Lax, same absolute session bound.
- `Secure` exactly follows validated `COOKIE_SECURE`.

Assert clear helpers expire every cookie using the same path/security attributes.

- [ ] **Step 2: Write failing login integration tests**

Cover correct normalized email/password, wrong password, unknown email with equivalent generic `401 invalid_credentials`, inactive user, missing/malformed/unapproved `Origin`, duplicate concurrent logins producing independent families, sanitized response, audit actions, and rollback if audit insertion fails. Confirm password timing uses Argon2 verification for both known and unknown emails through a fixed dummy hash.

- [ ] **Step 3: Run login tests and verify failure**

Run: `python -m pytest tests/unit/test_auth_cookies.py tests/integration/test_auth_login.py -q`

Expected: FAIL because auth service/router do not exist.

- [ ] **Step 4: Add request-scoped session lifecycle**

Store `session_factory` on `app.state`. Implement `get_db_session(request: Request) -> Iterator[Session]` that rolls back on exceptions and always closes. Services own transaction boundaries with `with session.begin()`; repositories never commit.

- [ ] **Step 5: Implement login service and route**

Define `LoginCommand(email: str, password: SecretStr, request_id: str)`. On success create a family UUID, refresh-token row, session-bound CSRF hash, signed access token, and `auth.login_succeeded` audit in one transaction. `POST /login` returns `200`; return only `id`, normalized `email`, `role`, `is_active`, and `employee_id: null`; keep Phase 3 responsible for linking an employee.

- [ ] **Step 6: Implement exact-origin dependency**

Normalize no values at request time: compare the complete `Origin` header byte-for-byte with `Settings.web_origin`. Reject missing, `null`, alternate port, alternate scheme, subdomain, userinfo, path, and comma-separated origins with `403 origin_not_allowed` before service execution.

- [ ] **Step 7: Register the `/api/v1/auth` router and run Task 3 gates**

Run: `python -m pytest tests/unit/test_auth_cookies.py tests/integration/test_auth_login.py -q`

Run: `python -m ruff check app tests alembic && python -m mypy app`

Expected: all pass.

- [ ] **Step 8: Commit Task 3**

```bash
git add apps/api
git commit -m "feat(auth): add secure cookie login"
```

### Task 4: Refresh rotation, replay protection, logout and password change

**Files:**
- Modify: `apps/api/app/modules/auth/service.py`
- Modify: `apps/api/app/modules/auth/router.py`
- Modify: `apps/api/app/modules/auth/schemas.py`
- Create: `apps/api/tests/integration/test_auth_refresh.py`
- Create: `apps/api/tests/integration/test_auth_mutations.py`

**Interfaces:**
- Consumes: login-created family/refresh/CSRF cookies and row-locking session repository.
- Produces: `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/change-password`, `AuthService.rotate_refresh`, `revoke_family`, and `change_password`.

- [ ] **Step 1: Write failing refresh behavior tests**

Assert rotation marks the presented row consumed, creates exactly one successor with the same family/user/CSRF hash and unchanged absolute expiry, links `replacement_id`, emits new access/refresh cookies, and never stores a raw token. Test missing, random, expired, consumed, and revoked refresh cookies with sanitized `401` responses.

- [ ] **Step 2: Write failing CSRF and origin tests**

For refresh/logout/change-password, assert rejection when Origin is missing/wrong, CSRF cookie/header is missing, values differ, or a valid token from another family is supplied. Confirm rejected requests do not consume/revoke sessions or change passwords.

- [ ] **Step 3: Write failing PostgreSQL concurrency and replay tests**

Use two independent SQLAlchemy sessions and a barrier to submit the same refresh token concurrently. Assert at most one successor row is created, the second consumer detects the consumed token, all family rows become revoked, and neither returned access token remains authorized. Replaying any older consumed token later has the same family-revocation result.

- [ ] **Step 4: Run refresh tests and verify failure**

Run: `python -m pytest tests/integration/test_auth_refresh.py tests/integration/test_auth_mutations.py -q`

Expected: FAIL because mutation behavior is absent.

- [ ] **Step 5: Implement atomic refresh rotation**

Hash the presented token, select its row `FOR UPDATE`, and branch only after the lock. Active token: consume and create successor. Consumed token: revoke the entire family and return `refresh_reuse_detected`. Missing/random token: generic `invalid_session`. Keep a family’s original `expires_at`; never slide it.

- [ ] **Step 6: Implement session-bound CSRF enforcement**

`require_csrf(request, active_session)` performs constant-time comparison of the header/cookie, then compares its hash to the family’s active row. It runs only after exact-origin validation and before the mutation.

- [ ] **Step 7: Implement logout and password change**

Logout revokes the caller’s family, records `auth.logout`, and clears all cookies. Password change verifies the old password, enforces the same password policy as user creation, writes a new Argon2id hash, revokes every other family, records `user.password_changed`, and leaves the current family active.

Return `204` from refresh, logout, and successful password change; refresh communicates rotated credentials only through cookies.

- [ ] **Step 8: Run Task 4 gates**

Run: `python -m pytest tests/integration/test_auth_refresh.py tests/integration/test_auth_mutations.py -q`

Expected: all pass repeatedly with `pytest -x --count=5` if `pytest-repeat` is deliberately added to dev dependencies; otherwise loop the command five times in the shell without adding a runtime dependency.

- [ ] **Step 9: Commit Task 4**

```bash
git add apps/api
git commit -m "feat(auth): rotate sessions and protect mutations"
```

### Task 5: Access authentication and reusable role policies

**Files:**
- Create: `apps/api/app/core/policies.py`
- Modify: `apps/api/app/modules/auth/router.py`
- Create: `apps/api/tests/unit/test_policies.py`
- Create: `apps/api/tests/integration/test_auth_me.py`

**Interfaces:**
- Consumes: access JWT `sub/sid`, `UserRepository`, and active session-family lookup.
- Produces: `AuthContext(user: User, family_id: UUID, session: AuthSession)`, `get_auth_context`, `require_roles(*roles)`, and `GET /api/v1/auth/me`.

- [ ] **Step 1: Write failing policy and `/auth/me` tests**

Cover valid identity; missing/malformed/expired/wrong-signature token; nonexistent user; inactive user; nonexistent, expired, revoked, or replay-revoked family; role change reflected immediately without issuing a new token; allowed role; forbidden role returning stable `403 forbidden`; and no token/hash/cookie fields in responses.

- [ ] **Step 2: Run policy tests and verify failure**

Run: `python -m pytest tests/unit/test_policies.py tests/integration/test_auth_me.py -q`

Expected: FAIL because policies and `/auth/me` are absent.

- [ ] **Step 3: Implement current authentication context**

Decode the access cookie, then load current user and one unexpired/unrevoked/unconsumed row for the claimed family. Return `401 authentication_required` for every authentication failure category. Do not trust role or active status from JWT claims.

- [ ] **Step 4: Implement reusable role dependency**

`require_roles(*allowed: UserRole) -> Callable[[AuthContext], AuthContext]` returns the context when the current database role is allowed and otherwise raises `403 forbidden`. Object-scope policies remain Phase 3.

- [ ] **Step 5: Implement `/auth/me` and run Task 5 gates**

Run: `python -m pytest tests/unit/test_policies.py tests/integration/test_auth_me.py -q`

Run: `python -m ruff check app tests alembic && python -m mypy app`

Expected: all pass.

- [ ] **Step 6: Commit Task 5**

```bash
git add apps/api
git commit -m "feat(auth): enforce current session policies"
```

### Task 6: ADMIN user-management API and last-admin protection

**Files:**
- Create: `apps/api/app/modules/users/schemas.py`
- Create: `apps/api/app/modules/users/service.py`
- Create: `apps/api/app/modules/users/router.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/integration/test_users_api.py`
- Create: `apps/api/tests/integration/test_last_admin_concurrency.py`

**Interfaces:**
- Consumes: `require_roles(UserRole.ADMIN)`, repositories, `PasswordService`, and `AuditWriter`.
- Produces: `GET /api/v1/users`, `POST /api/v1/users`, `PATCH /api/v1/users/{user_id}` and paginated sanitized user schemas.

- [ ] **Step 1: Write failing user API tests**

Assert ADMIN can list with `page`, `page_size<=100`, allowlisted `sort`, role/status filters; create normalized unique email with initial password; and update role/status. Assert HR/MANAGER/EMPLOYEE receive `403`, duplicate email returns `409 email_already_exists`, unknown IDs return `404`, invalid roles/pagination/passwords return `422`, and no response exposes hashes.

- [ ] **Step 2: Write failing audit and session-invalidation tests**

Assert create/update and their `user.created`, `user.role_changed`, or `user.status_changed` audits commit together. Deactivation invalidates every family immediately. Demotion affects authorization immediately because policies read the database role.

- [ ] **Step 3: Write failing last-admin tests including concurrency**

Test one active ADMIN cannot self-demote/deactivate. With two active ADMIN users, run two transactions concurrently attempting to remove different admins; order `SELECT ... FOR UPDATE` by UUID and assert one operation returns `409 last_active_admin` and at least one active ADMIN remains.

- [ ] **Step 4: Run user tests and verify failure**

Run: `python -m pytest tests/integration/test_users_api.py tests/integration/test_last_admin_concurrency.py -q`

Expected: FAIL because users service/router do not exist.

- [ ] **Step 5: Implement schemas, service, routes and locking rule**

Use `UserCreate(email: EmailStr, password: SecretStr, role: UserRole)` and `UserUpdate(role: UserRole | None, is_active: bool | None)` with at least one update field. Normalize emails with the same function used by login/bootstrap. `GET /users` defaults to email ascending and permits only `email`, `created_at`, `role`, and `is_active`; create returns `201`, list/update return `200`. Lock all active ADMIN rows in stable ID order before a transition that could reduce their count; validate after acquiring locks and before mutation.

- [ ] **Step 6: Register users router and run Task 6 gates**

Run: `python -m pytest tests/integration/test_users_api.py tests/integration/test_last_admin_concurrency.py -q`

Expected: all pass against PostgreSQL.

- [ ] **Step 7: Commit Task 6**

```bash
git add apps/api
git commit -m "feat(users): add administrator account management"
```

### Task 7: Same-origin web authentication client and query state

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Modify: `apps/web/next.config.ts`
- Create: `apps/web/src/lib/api-client.ts`
- Create: `apps/web/src/lib/api-client.test.ts`
- Create: `apps/web/src/features/auth/types.ts`
- Create: `apps/web/src/features/auth/api.ts`
- Create: `apps/web/src/features/auth/auth-provider.tsx`
- Create: `apps/web/src/app/providers.tsx`
- Modify: `apps/web/src/app/layout.tsx`
- Modify: `apps/web/vitest.config.ts`
- Create: `apps/web/src/test/setup.ts`

**Interfaces:**
- Consumes: same-origin `/api/v1/auth/*`, `insighthr_csrf` browser cookie, stable API error envelope.
- Produces: `apiFetch<T>()`, one shared refresh promise, `AuthProvider`, `useAuth()`, and TanStack Query client.

- [ ] **Step 1: Pin frontend state/form/test dependencies**

Add exact runtime dependencies `@tanstack/react-query@5.104.1`, `react-hook-form@7.89.0`, and `@hookform/resolvers@5.9.1`. Add exact dev dependencies `@testing-library/react@16.3.3`, `@testing-library/user-event@14.6.7`, and `jsdom@30.1.1`; regenerate `package-lock.json` with Node 24/npm.

- [ ] **Step 2: Write failing API-client tests**

Assert `credentials: "include"`, CSRF header only for mutations, stable error parsing, one refresh attempt after `401`, original-request retry exactly once, no refresh loop, no refresh for login/refresh endpoints, and ten simultaneous `401` responses sharing one refresh request.

- [ ] **Step 3: Run client tests and verify failure**

Run: `npm run test -- --run src/lib/api-client.test.ts`

Expected: FAIL because client does not exist.

- [ ] **Step 4: Implement Next same-origin API proxy**

Add a rewrite from `/api/v1/:path*` to `${API_INTERNAL_URL}/api/v1/:path*`. Validate the internal base as HTTP(S), strip one trailing slash, never expose it as `NEXT_PUBLIC_*`, and keep the existing production standalone setting.

- [ ] **Step 5: Implement API client and auth provider**

`apiFetch<T>(path, init, options)` reads the CSRF cookie for non-safe methods, parses the stable error envelope, coordinates a module-level single-flight refresh, retries once, and throws typed `ApiClientError`. `AuthProvider` owns the `/auth/me` query, login/logout mutations, cache clearing, and redirect-safe status; it never stores access or refresh tokens in JavaScript storage.

- [ ] **Step 6: Run Task 7 gates**

Run: `npm run test -- --run src/lib/api-client.test.ts`

Run: `npm run lint && npm run typecheck`

Expected: all pass.

- [ ] **Step 7: Commit Task 7**

```bash
git add apps/web
git commit -m "feat(web): add authenticated API client"
```

### Task 8: Login, protected account and ADMIN user-management screens

**Files:**
- Create: `apps/web/src/features/auth/login-form.tsx`
- Create: `apps/web/src/features/auth/change-password-form.tsx`
- Create: `apps/web/src/features/auth/protected-route.tsx`
- Create: `apps/web/src/features/auth/login-form.test.tsx`
- Create: `apps/web/src/features/auth/protected-route.test.tsx`
- Create: `apps/web/src/features/users/users-api.ts`
- Create: `apps/web/src/features/users/user-management.tsx`
- Create: `apps/web/src/features/users/user-management.test.tsx`
- Create: `apps/web/src/app/(auth)/login/page.tsx`
- Create: `apps/web/src/app/(protected)/layout.tsx`
- Create: `apps/web/src/app/(protected)/account/page.tsx`
- Create: `apps/web/src/app/(protected)/admin/users/page.tsx`
- Modify: `apps/web/src/app/globals.css`

**Interfaces:**
- Consumes: `useAuth`, `apiFetch`, auth/user schemas.
- Produces: accessible `/login`, `/account`, and ADMIN-only `/admin/users` flows.

- [ ] **Step 1: Write failing login and protected-route tests**

Test labeled email/password controls, keyboard submission, generic invalid-credentials message, disabled pending state, safe redirect only to an internal path, successful redirect to `/account`, authenticated-user redirect away from `/login`, anonymous protected-route redirect, refresh-before-redirect behavior, and inactive/revoked sessions returning to login.

- [ ] **Step 2: Write failing account and user-management tests**

Test current email/role display, logout, password change with old/new/confirmation validation, ADMIN list/create/change-role/deactivate flows, validation/conflict messages, pending controls, and non-ADMIN denial without issuing the users request.

- [ ] **Step 3: Run UI tests and verify failure**

Run: `npm run test -- --run src/features/auth src/features/users`

Expected: FAIL because components/pages do not exist.

- [ ] **Step 4: Implement login and protected account flow**

Use React Hook Form with Zod for client ergonomics while treating backend validation as authoritative. `ProtectedRoute` shows a neutral loading state during `/auth/me`/refresh and uses `router.replace`; never render protected children before authorization is known. Set protected layouts to dynamic/no-store behavior.

- [ ] **Step 5: Implement ADMIN user management**

Provide a simple accessible table, explicit create form, role selector, active-state action, pagination controls, and confirmation before deactivation. Do not add employee profile fields or HR domain controls.

- [ ] **Step 6: Run Task 8 gates**

Run: `npm run test -- --run`

Run: `npm run lint && npm run typecheck && npm run build`

Expected: all pass; production build contains public status, login, account, and admin users routes.

- [ ] **Step 7: Commit Task 8**

```bash
git add apps/web
git commit -m "feat(web): add authentication and user administration"
```

### Task 9: Documentation, containers and end-to-end Phase 2 verification

**Files:**
- Modify: `README.md`
- Modify: `README.vi.md`
- Modify: `.env.example`
- Modify: `docs/api.md`
- Modify: `docs/database.md`
- Modify: `docs/deployment.md`
- Modify: `docs/architecture.md`
- Modify: `.github/workflows/phase1-ci.yml` or rename to `.github/workflows/ci.yml`
- Modify: `apps/api/tests/smoke/test_container_contract.py`
- Create: `apps/api/tests/integration/test_auth_end_to_end.py`

**Interfaces:**
- Consumes: every Phase 2 endpoint, environment variable, migration, CLI command, UI route, and image change.
- Produces: reproducible bootstrap/login/rotation/logout/user-management runbook and final Phase 2 evidence.

- [ ] **Step 1: Add a real end-to-end authentication test**

Against PostgreSQL, bootstrap ADMIN, login, call `/auth/me`, create an HR user, login as HR, reject HR access to `/users`, change HR password, prove another HR family is revoked, rotate the current family, logout, and prove the old access and refresh cookies no longer work. Assert expected audits without secrets.

- [ ] **Step 2: Update container and CI contracts**

Ensure Compose supplies a nondefault CI-only `AUTH_ACCESS_SECRET`, exact `WEB_ORIGIN`, and correct cookie security mode; production examples remain placeholders. CI applies both revisions, runs the full PostgreSQL suite including concurrency tests, builds images from lock constraints, starts the clean stack, bootstraps an ADMIN through the CLI, exercises login/me/refresh/logout through HTTP with a cookie jar and CSRF header, and confirms web login page plus API proxy behavior.

- [ ] **Step 3: Inspect final images and secret hygiene**

Extend CI canaries so nested API/web env files and authentication secrets do not appear in final layers. Assert API runtime has Argon2/JWT runtime packages but not pytest/mypy/Ruff, both images remain UID/GID `10001:10001`, and no source test directories are present.

- [ ] **Step 4: Update English and Vietnamese documentation**

Document every auth variable, percent/secret requirements, first-ADMIN command, cookie behavior, local HTTP versus HTTPS, endpoint payload/status/error examples, database constraints, session-family replay semantics, password change, ADMIN management, audit actions, and recovery from a lost bootstrap password. Clearly state employee links remain `null` until Phase 3.

- [ ] **Step 5: Update architecture implementation status**

Mark only Phase 2 authentication artifacts complete. Keep Organization and later business phases planned.

- [ ] **Step 6: Run the complete local gate**

Backend from `apps/api` with dedicated PostgreSQL:

```bash
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

Repository root:

```bash
docker compose --env-file .env.example config --quiet
git diff --check
```

Expected: every command exits zero and PostgreSQL integration tests do not skip.

- [ ] **Step 7: Run clean Compose acceptance**

Use a unique project name and empty volume. Start the stack, run the interactive bootstrap safely, verify login and cookie attributes, current user, refresh rotation, CSRF rejection, logout revocation, ADMIN user creation, persistence across normal `down`/`up`, and final cleanup limited to that project. Record exact versions and the successful CI run in `docs/deployment.md`.

- [ ] **Step 8: Review scope and tracked files**

Confirm no plain passwords, signing keys, raw tokens, `.env` files, build output, Employee/domain tables, or later-phase features are tracked. Confirm migration history has one head and `git status --short` contains only intended documentation before commit.

- [ ] **Step 9: Commit Phase 2 completion evidence**

```bash
git add README.md README.vi.md .env.example .github apps docs
git commit -m "docs: complete Phase 2 authentication runbook"
```

## Phase 2 definition of done

- A new operator can create the first ADMIN without exposing a password in process arguments, logs, Git, or shell history.
- Active users can log in, refresh once per token, load current identity, change their password, and log out through cookie-authenticated APIs and usable web screens.
- Refresh replay and concurrent duplicate refresh revoke the affected family without leaving multiple usable successors.
- Exact-origin and session-bound CSRF checks reject unauthorized mutations without changing database state.
- Current database status/role and active session family govern every protected request; stale JWT role claims cannot retain privileges.
- ADMIN can list, create, activate/deactivate, and change roles while concurrent operations cannot remove the final active ADMIN.
- User/session mutations emit sanitized transactional audits.
- Phase 1 health and public status behavior remain operational.
- Backend unit/integration/concurrency tests, frontend behavior tests, linting, type checking, production builds, clean Compose authentication smoke tests, persistence, and image inspection all pass.
- English and Vietnamese runbooks accurately describe configuration, bootstrap, cookies, security boundaries, and the Phase 3 handoff.

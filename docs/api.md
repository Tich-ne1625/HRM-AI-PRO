# API contract

## Authentication and accounts (Phase 2)

All responses use `Cache-Control: no-store` for successful personalized endpoints. Public user JSON contains only `id`, normalized `email`, `role`, `is_active`, `employee_id` (linked employee UUID, otherwise null). No response returns a password/hash or access/refresh token in JSON.

## Organization and employees (Phase 3)

| Method/path under `/api/v1` | Contract |
| --- | --- |
| GET `/departments`, `/positions` | Scoped `{items,total,page,page_size}`; `page>=1`, `page_size=1..100`, optional `q` (literal code/label search, max 100), `is_active`, allowlisted ascending `sort` |
| POST `/departments` | HR only, `{"code":"ENG","name":"Engineering"}`; optional is_active default true; 201 |
| POST `/positions` | HR only, `{"code":"DEV","title":"Developer"}`; optional is_active default true; 201 |
| PATCH `/departments/{id}`, `/positions/{id}` | HR, at least one code/name-or-title/is_active change; 200; required fields cannot be null |
| GET `/employees` | Scoped page; `page`, `page_size`, `q` (literal code/name), `department_id`, `position_id`, `employment_status`, `sort` |
| GET `/employees/{id}` | Scoped detail; nonexistent and inaccessible UUIDs both return 404 employee_not_found |
| POST `/employees` | HR; employee payload below; 201 |
| PATCH `/employees/{id}` | HR; supported employee fields, at least one; manager_id/user_id allow null to clear; 200 |
| GET `/employees/linkable-users?email=...` | HR-only exact normalized email lookup; returns `{items:[{id,email,is_active,employee_id}]}` or empty items; does not allow user creation/role changes |

All mutations require Origin + family-bound CSRF and recheck current HR authorization under locks. ADMIN has no implicit domain permission. HR sees all; MANAGER sees self + current direct reports only; EMPLOYEE sees self. Unlinked users see empty lists. Reference data is restricted to records referenced by visible employees for non-HR readers. Filtered count and items apply the same SQL scope.

Employee create example (UUID placeholders must be replaced):

```json
{"employee_code":"EMP-01","display_name":"Nguyễn An","department_id":"<department UUID>","position_id":"<position UUID>","manager_id":null,"user_id":null,"employment_status":"ACTIVE"}
```

Codes trim/uppercase to ASCII pattern `[A-Z0-9][A-Z0-9_-]{1,31}`; names trim to 1–200 characters and reject control characters with 422. Employee output contains id/code/display_name, department_id/name, position_id/title, manager_id/name, user_id, employment_status, created_at/updated_at. It never contains account secrets. Status is ACTIVE/INACTIVE, independent of user activation. New department/position/manager assignments must be active; unchanged retired references may be retained. No hard delete exists.

Reference sorts: code, name (department)/title (position), created_at, is_active. Employee sorts: employee_code, display_name, created_at, employment_status. UUID breaks ties. PATCH rejects unknown fields, empty bodies and null required fields. New errors: 409 duplicate_code, employee_code_already_exists, user_already_linked, reference_inactive, manager_inactive, reporting_cycle; 404 reference_not_found, employee_not_found, user_not_found. Other auth/validation errors retain the common envelope.

## Authentication endpoint reference

| Method/path under `/api/v1` | Input | Success | Authorization |
| --- | --- | --- | --- |
| `POST /auth/login` | `{"email":"admin@example.com","password":"<password>"}` | `200` user + cookies | Exact Origin |
| `GET /auth/me` | None | `200` user | Valid access + current user/family |
| `POST /auth/refresh` | No body | Empty `204` + rotated cookies | Refresh cookie, Origin, CSRF |
| `POST /auth/logout` | No body | Empty `204`, clears cookies | Access, active family, Origin, CSRF |
| `POST /auth/change-password` | `{"old_password":"<old>","new_password":"<new>"}` | Empty `204` | Access, active family, Origin, CSRF |
| `GET /users` | Query parameters below | `200` page | Current ADMIN |
| `POST /users` | `{"email":"hr@example.com","password":"<initial>","role":"HR"}` | `201` user | Current ADMIN, Origin, CSRF |
| `PATCH /users/{uuid}` | `{"role":"MANAGER","is_active":false}`; one or both fields | `200` user | Current ADMIN, Origin, CSRF |

Passwords contain 12–128 Unicode characters and are not trimmed. Replacement must differ from current. Login accepts shorter existing password input for verification; account creation enforces policy. No self-registration or email reset is provided. Roles: `ADMIN`, `HR`, `MANAGER`, `EMPLOYEE`; ADMIN has no implicit HR privileges.

`GET /users?page=1&page_size=20&sort=email&role=HR&is_active=true` returns `{"items":[],"total":0,"page":1,"page_size":20}`. Page starts at 1; page size is 1–100; ascending sort permits only `email`, `created_at`, `role`, `is_active`, with UUID tie-breaking. Role/status filters are optional. PATCH rejects empty, unknown-only, or explicitly null updates.

### Cookies and mutation headers

| Cookie | Path | HttpOnly | Lifetime |
| --- | --- | --- | --- |
| `insighthr_access` | `/` | Yes | 15 minutes by default |
| `insighthr_refresh` | `/api/v1/auth/refresh` | Yes | Remaining absolute family lifetime |
| `insighthr_csrf` | `/` | No | Same absolute family lifetime |

All use SameSite=Lax and Secure according to validated configuration. HTTPS production requires Secure. Login/refresh set cookies; logout deletes each with its original attributes/path. Use the same browser origin for web and `/api/v1/*`; Next.js proxies API calls. Origin must match `WEB_ORIGIN` byte-for-byte, including scheme/host/port, with exactly one header and no trailing slash. Missing/null/comma-separated/duplicate origins are rejected.

For mutations, send `Origin: <WEB_ORIGIN>` and `X-CSRF-Token: <insighthr_csrf cookie value>`. Header/cookie must match and their SHA-256 must match the session family. Login requires Origin but no CSRF. Reads need neither Origin nor CSRF. Refresh preserves family CSRF and absolute expiry; a consumed token presented with valid family CSRF revokes its whole family. Authorization always checks the current DB user and an active family, so replay/logout/deactivation immediately invalidate existing signed access tokens.

### Stable errors

| Status/code | Meaning |
| --- | --- |
| `401 invalid_credentials` | Wrong, unknown, or inactive login; also wrong old password |
| `401 authentication_required` | Missing/invalid access or inactive/missing user/family on protected reads |
| `401 invalid_session` | Missing/random/expired/revoked refresh; invalid access session for auth mutations |
| `401 refresh_reuse_detected` | Consumed refresh replay; family revocation committed |
| `403 origin_not_allowed` | Exact Origin check failed |
| `403 csrf_failed` | Missing/mismatched/cross-family CSRF |
| `403 forbidden` | Current DB role lacks permission |
| `404 user_not_found` | Target user does not exist |
| `409 email_already_exists` | Normalized duplicate email |
| `409 last_active_admin` | Would remove the final active ADMIN |
| `422 validation_error` / `invalid_password` | Invalid input or replacement policy |
| `500 internal_server_error` | Sanitized internal failure; transaction rolled back |

Errors follow the envelope below. Audit/database failures do not commit partial changes. Client code retries an authenticated request only once after one shared refresh; login and refresh never recursively refresh themselves.

## Base paths

Operational health endpoints are intentionally unversioned:

- `GET /health/live`
- `GET /health/ready`

Implemented authentication and account-management endpoints use `/api/v1`. OpenAPI is available at `/docs`. Health routes remain public.

## Liveness

Successful response (`200`):

```json
{
  "status": "ok",
  "service": "api"
}
```

This endpoint does not contact PostgreSQL or future external providers.

## Readiness

Successful response (`200`):

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "migrations": "current"
  }
}
```

Readiness returns `503` when PostgreSQL is unavailable, the Alembic marker is missing, or the revision is not the single current head.

## Error envelope

Every handled HTTP, validation, dependency, and unexpected error uses this shape:

```json
{
  "error": {
    "code": "service_not_ready",
    "message": "Service dependencies are not ready",
    "details": [
      { "check": "database", "status": "unavailable" },
      { "check": "migrations", "status": "unavailable" }
    ]
  },
  "request_id": "4f4f9bdc9b244467a5299a823448004d"
}
```

The same request ID is returned in the `X-Request-ID` response header. A caller-provided ID is accepted only when it is 8–128 characters and contains alphanumeric characters, hyphens, underscores, or periods. Unexpected exceptions return a generic message and never serialize exception text.

## Future API

The reviewed endpoint map, pagination contract, role scopes, error meanings, and evidence-version concurrency rules are defined in [architecture.md](architecture.md). Documentation will add concrete request/response schemas as each phase implements them.


## Phase 4 settings and KPI definitions (partial implementation)

ADMIN-only `GET/PATCH /api/v1/settings/scoring` returns `{version,policy}`; PATCH requires `{expected_version,policy}` and changes future activation defaults only. HR-only `POST /api/v1/kpis` creates a definition; `PATCH /api/v1/kpis/{id}` requires expected_version and supported changes, including is_active retirement. `GET /api/v1/kpis` is paginated: HR sees all, MANAGER/EMPLOYEE see definitions assigned within their current employee scope, and ADMIN has no implicit HR access. Code/name search is literal; sorting is allowlisted. All mutations use the existing Origin/family-CSRF policy and atomic audit. Conflicts return stale_version or duplicate_code; invalid decimal policy inputs return 422. Cycle/assignment endpoints remain under implementation; see the [contract](phase-4-contract.md).

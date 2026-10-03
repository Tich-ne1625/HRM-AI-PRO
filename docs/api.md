# API contract

## Base paths

Operational health endpoints are intentionally unversioned:

- `GET /health/live`
- `GET /health/ready`

Business endpoints will use `/api/v1` beginning in Phase 2. Phase 1 does not expose placeholder business routes.

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


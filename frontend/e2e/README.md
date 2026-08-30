# Phase 3.3 browser E2E

Playwright runs against an already started frontend/backend pair and an isolated, migrated PostgreSQL test database. It does not start Docker or alter a development database itself.

Set the environment before running from `frontend/`:

```text
E2E_BASE_URL=http://127.0.0.1:8080
E2E_DEPARTMENT_ID=<seeded ICU test department ID>
E2E_YEAR=2026
E2E_MONTH=8
E2E_ADMIN_USERNAME=<admin user>
E2E_ADMIN_PASSWORD=<admin password>
E2E_HEAD_NURSE_USERNAME=<head nurse user>
E2E_HEAD_NURSE_PASSWORD=<head nurse password>
pnpm exec playwright install chromium
pnpm test:e2e
```

Use a fresh fixture for each run: the Head Nurse test deliberately converts and publishes one AI draft. The backend integration suite in `backend/tests/integration/` is the source of the matching ICU data fixture and safety guard for the `_test` database.

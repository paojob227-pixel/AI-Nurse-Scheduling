# AI workflow PostgreSQL integration tests

These tests require a disposable PostgreSQL database that has been migrated to the current Alembic repository head. They are intentionally skipped unless `INTEGRATION_DATABASE_URL` is set and reject any database name not ending in `_integration_test`; this prevents cleanup from targeting a development or production database.

Example from `backend/`:

```text
set INTEGRATION_DATABASE_URL=postgresql+psycopg2://test_user@localhost:55433/nurse_conversion_integration_test
set DATABASE_URL=%INTEGRATION_DATABASE_URL%
python -m alembic upgrade head
python -m unittest discover -s tests/integration -p "test_*.py"
```

The suite truncates only the explicitly named `_integration_test` database between tests. It covers AI preview, preview validation, persisted AI draft lifecycle, Head Nurse approval, filling an empty Manual draft while retaining its schedule ID, Manual validation/publish, and the documented negative cases. Never run fixture seeding concurrently with the tests against the same database.

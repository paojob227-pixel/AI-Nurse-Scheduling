# AI workflow PostgreSQL integration tests

These tests require a disposable PostgreSQL database that has been migrated to Alembic head. They are intentionally skipped unless `INTEGRATION_DATABASE_URL` is set and its database name ends in `_test`; this prevents cleanup from targeting a development or production database.

Example from `backend/`:

```text
set INTEGRATION_DATABASE_URL=postgresql+psycopg2://nurse_app:password@localhost:5432/nurse_schedule_test
python -m alembic upgrade head
python -m unittest discover -s tests/integration -p "test_*.py"
```

The suite truncates only the explicitly named `_test` database between tests. It covers AI preview, preview validation, persisted AI draft lifecycle, Head Nurse approval, conversion to a Manual Schedule draft, Manual validation/publish, and the documented negative cases.

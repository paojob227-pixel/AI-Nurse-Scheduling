# Architecture

```text
React/Vite browser app  ->  FastAPI /api/v1  -> PostgreSQL
                              |
                           Alembic
```

The browser stores the short-lived access token locally and sends it as a Bearer token. FastAPI validates it, enforces role permissions, and uses SQLAlchemy for persistence. Alembic is the only mechanism for changing the database schema.

For local deployment, Docker Compose starts PostgreSQL, applies migrations, seeds reference records, starts FastAPI, and serves the built React application through Nginx.

#!/bin/sh
set -eu

# Start HTTP immediately so Render can serve the frontend and diagnostic
# endpoints while Postgres is unavailable. Initialization is retried safely.
(
  attempt=1
  while [ "$attempt" -le 10 ]; do
    if alembic upgrade head && python -m app.seed; then
      echo "Database migration and seed completed."
      exit 0
    fi
    echo "Database initialization attempt $attempt failed; retrying in 15s." >&2
    attempt=$((attempt + 1))
    sleep 15
  done
  echo "Database initialization did not complete; HTTP service remains available for diagnosis." >&2
) &

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips=*

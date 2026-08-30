# Public deployment

The production image serves the React frontend and FastAPI API from one HTTPS
address. The browser uses `/api/v1`, so phones and computers do not need to be
on the same LAN and no private IP address is embedded in the build.

## Before deploying

- Do not upload `backend/.env`, the local PostgreSQL data directory, exports,
  or real staff data to a source-code repository.
- Use unique passwords of at least 12 characters for
  `ADMIN_INITIAL_PASSWORD` and `STAFF_INITIAL_PASSWORD`.
- Do not reuse the local pilot passwords. Render generates `JWT_SECRET_KEY`.
- The included Blueprint uses free resources for a project demonstration only.
  Render's free PostgreSQL database expires after 30 days and has no backups.
  Choose paid database and web-service plans before storing real operational
  data.

## Deploy with Render Blueprint

1. Put this project in a private GitHub or GitLab repository.
2. In Render, choose **New > Blueprint** and select that repository.
3. Render reads `render.yaml`. Enter new values when prompted for
   `ADMIN_INITIAL_PASSWORD` and `STAFF_INITIAL_PASSWORD`.
4. Confirm the resources and start the deployment.
5. When the deployment is healthy, open the generated `onrender.com` address.
   The same address works from mobile data, home Wi-Fi, or another network.

The container automatically applies Alembic migrations and creates the initial
admin account on first boot. PostgreSQL accepts only Render-internal traffic
because the Blueprint sets an empty public IP allowlist.

## Custom domain

After the generated address works, add a domain from the web service's Render
settings and create the DNS record Render shows. HTTPS is issued and renewed by
the hosting platform.

## Local production-image check

Build the same image that the host will run:

```powershell
docker build -f Dockerfile.production -t ai-nurse-scheduling:production .
```

Local development continues to use `OPEN_ICU_SYSTEM.cmd`; these deployment
files do not change its ports or LAN behavior.

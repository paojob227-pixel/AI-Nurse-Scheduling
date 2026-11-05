import os
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.routes import router
from app.database.config import ENVIRONMENT, FRONTEND_ORIGINS, validate_runtime_config
from app.database.database import engine

app = FastAPI(
    title="AI Nurse Scheduling System",
    version="1.0.0"
)

validate_runtime_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/api")
def api_root():
    return {
        "message": "AI Nurse Scheduling Backend is running!"
    }


@app.get("/health")
def health(response: Response) -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        # Keep liveness healthy while Postgres is restarting; /health/ready
        # reports whether database-backed features can currently operate.
        return {"status": "degraded", "database": "unavailable"}
    return {"status": "ok", "database": "available"}


@app.get("/health/ready")
def readiness(response: Response) -> dict[str, str]:
    """Strict readiness probe that requires a working database connection."""
    result = health(response)
    if result["status"] != "ok":
        response.status_code = 503
    return result


# The production image copies the Vite build here. Mounting it last preserves
# the API, health-check, and OpenAPI routes declared above.
frontend_dist_dir = os.getenv("FRONTEND_DIST_DIR")
if frontend_dist_dir:
    frontend_dist = Path(frontend_dist_dir)
    if not frontend_dist.is_dir():
        raise RuntimeError(f"FRONTEND_DIST_DIR does not exist: {frontend_dist}")
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    # Preserve the original local-development status response at the root.
    app.add_api_route("/", api_root, include_in_schema=False)

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from app.database.config import DATABASE_URL

database_url = make_url(DATABASE_URL)
if database_url.drivername == "postgresql":
    database_url = database_url.set(drivername="postgresql+psycopg2")

engine_options = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
    "pool_timeout": 10,
}
if database_url.get_backend_name() == "postgresql":
    if "sslmode" not in database_url.query and os.getenv("ENVIRONMENT") == "production":
        database_url = database_url.update_query_dict({"sslmode": "require"})
    engine_options.update({"pool_size": 3, "max_overflow": 2})

engine = create_engine(database_url, **engine_options)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

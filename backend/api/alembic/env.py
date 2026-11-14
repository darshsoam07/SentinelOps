from alembic import context
from app.db.database import url
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

engine = (
    create_engine(make_url(url).set(drivername="postgresql+psycopg")) if url else None
)

if engine is None:
    raise RuntimeError("Set SENTINELOPS_DATABASE_URL before running migrations")
with engine.begin() as connection:
    context.configure(connection=connection)
    context.run_migrations()

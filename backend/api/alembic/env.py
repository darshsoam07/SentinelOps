from alembic import context
from app.db import engine

if engine is None:
    raise RuntimeError("Set SENTINELOPS_DATABASE_URL before running migrations")
with engine.begin() as connection:
    context.configure(connection=connection)
    context.run_migrations()

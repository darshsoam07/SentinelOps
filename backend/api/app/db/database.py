import os
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings

url = settings.sentinelops_database_url
engine = None
if url:
    engine = create_async_engine(
        make_url(url).set(drivername="postgresql+asyncpg"),
        connect_args={"server_settings": {"search_path": os.environ["PG_TEST_SCHEMA"]}}
        if os.getenv("PG_TEST_SCHEMA")
        else {},
        pool_pre_ping=True,
    )
sessions = async_sessionmaker(engine, expire_on_commit=False) if engine else None


async def get_db():
    if sessions is None:
        yield None
        return
    async with sessions.begin() as session:
        yield session

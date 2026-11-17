"""Build the fixture ASGI app with a connection pool scoped to its temporary schema."""

import os
from functools import partial
from unittest.mock import patch
from sqlalchemy.ext.asyncio import create_async_engine


def build():
    factory = partial(
        create_async_engine,
        connect_args={"server_settings": {"search_path": os.environ["PG_TEST_SCHEMA"]}},
    )
    with patch("sqlalchemy.ext.asyncio.create_async_engine", factory):
        from app.main import app
    return app

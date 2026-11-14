import os
from sqlalchemy import create_engine

url = os.environ.get("PAYFLOW_DATABASE_URL")
engine = create_engine(url, pool_pre_ping=True) if url else None

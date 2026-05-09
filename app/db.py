import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Docker uses /app/data/gateway.db, local dev uses ./data/gateway.db
# Override with DB_URL env var if needed
_default_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "gateway.db")
DB_URL = os.environ.get("DB_URL", f"sqlite:///{_default_db_path}")

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass
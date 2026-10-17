from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from shared.config import DATABASE_URL

DB_PATH = Path("app/database/printsensei.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    # Test connection creation / driver
    engine.connect()
except Exception:
    engine = create_engine("sqlite:///app/database/printsensei.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    from infrastructure.database_models import Base as ModelsBase

    ModelsBase.metadata.create_all(bind=engine)

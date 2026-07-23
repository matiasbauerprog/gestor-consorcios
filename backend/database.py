from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

_settings = get_settings()

_connect_args = {}
if _settings.DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
elif "pooler.supabase.com" in _settings.DATABASE_URL or ":6543" in _settings.DATABASE_URL:
    _connect_args["options"] = "-c prepare_threshold=0"

engine = create_engine(_settings.DATABASE_URL, connect_args=_connect_args, future=True)


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _):
    if _settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

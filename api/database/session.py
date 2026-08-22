import logging
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from api.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=False,
)


@event.listens_for(Engine, "connect")
def _set_sqlite_wal_mode(dbapi_connection, connection_record):
    """Enable WAL mode for SQLite so multiple processes can read/write concurrently."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from api.database.models import Base
    Base.metadata.create_all(bind=engine)
    _migrate_db()


def _migrate_db():
    """Apply additive schema migrations for columns added after initial creation."""
    with engine.connect() as conn:
        # Add stage_progress column if missing (added after initial schema)
        if "sqlite" in settings.database_url:
            result = conn.execute(
                __import__("sqlalchemy").text("PRAGMA table_info(jobs)")
            )
            columns = {row[1] for row in result}
            if "stage_progress" not in columns:
                conn.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE jobs ADD COLUMN stage_progress INTEGER NOT NULL DEFAULT 0"
                    )
                )
                conn.commit()
                logger.info("Migrated: added stage_progress column to jobs")


def close_db():
    """Dispose the engine connection pool. Call on shutdown."""
    engine.dispose()
    logger.info("Database engine disposed")


"""
Database configuration and session management.

Persistence hardening:
  - Absolute DB path derived from this module location (robust against cwd changes)
  - SQLite WAL journal mode + synchronous=NORMAL for durability under concurrency
  - Pre-migration backup + startup consistency check
"""
import logging
import os
import shutil

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

# ── Resolve an absolute data directory (independent of the process cwd) ───────
# database.py lives in backend/app/, so ../../data → <repo>/data.
DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
)
os.makedirs(DATA_DIR, exist_ok=True)

_DEFAULT_DB_PATH = os.path.join(DATA_DIR, "gather.db")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")

_IS_SQLITE = DATABASE_URL.startswith("sqlite")


def _db_file_path() -> str | None:
    """Return the on-disk path for a sqlite URL, else None."""
    if not _IS_SQLITE:
        return None
    path = DATABASE_URL.replace("sqlite:///", "", 1)
    return os.path.abspath(path)


# Ensure the directory for the configured DB exists
_db_path = _db_file_path()
if _db_path:
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _IS_SQLITE else {},
    echo=False,
)


if _IS_SQLITE:
    @event.listens_for(Engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        """Enable WAL + NORMAL synchronous on every SQLite connection."""
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to set SQLite PRAGMA: %s", exc)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _backup_db():
    """Back up the SQLite DB file before applying schema migrations."""
    path = _db_file_path()
    if not path or not os.path.exists(path):
        return
    try:
        shutil.copy(path, path + ".bak")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("DB backup failed: %s", exc)


def _consistency_check():
    """Warn if the DB file looks suspiciously small (possible data loss)."""
    path = _db_file_path()
    if not path or not os.path.exists(path):
        return
    try:
        size = os.path.getsize(path)
        if size < 1024:
            logger.warning(
                "Database file %s is only %d bytes — it may be empty or corrupted.",
                path, size,
            )
    except OSError:
        pass


def init_db():
    """Create all tables + apply schema migrations (with backup)."""
    _consistency_check()
    _backup_db()
    Base.metadata.create_all(bind=engine)
    # Apply schema additions (new models, column alterations)
    from app.models_additions import migrate_schema
    migrate_schema(engine)
    logger.info("Database ready at %s", _db_file_path() or DATABASE_URL)

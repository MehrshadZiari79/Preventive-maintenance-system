from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

Base = declarative_base()

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        from config import DATABASE_URL
        _engine = create_engine(
            DATABASE_URL,
            connect_args={
                "check_same_thread": False,
                "timeout": 30,
            },
            poolclass=StaticPool,
        )

        @event.listens_for(_engine, "connect")
        def set_pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine()
        )
    return _SessionLocal


def SessionLocal():
    return get_session_factory()()


def init_db():
    from database import models          # existing models
    from database import work_order      # register WorkOrder table
    from config import DB_PATH
    Base.metadata.create_all(bind=get_engine())
    print(f"✅ Database ready at: {DB_PATH}")

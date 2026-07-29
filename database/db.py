# database/db.py
import base64
import hashlib

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from database.models import Base, User, UserRole


# ----- Database connection settings (obfuscated) -----
_server = "192.168.0.1"
_database = "PM_Database"
_username = "pm_app"
_password_b64 = "***REMOVED***="   # base64 of "***REMOVED***"
_port = "1433"


def _get_password():
    return base64.b64decode(_password_b64).decode()


def get_database_url():
    pwd = _get_password()
    return f"mssql+pymssql://{_username}:{pwd}@{_server}:{_port}/{_database}?charset=utf8"


DATABASE_URL = get_database_url()

_engine = None
_SessionFactory = None


def get_engine():
    global _engine

    if _engine is None:
        # SQLAlchemy 1.3.24 compatible – no 'future' argument, no isolation_level directly
        connect_args = {
            "tds_version": "7.0",
        }
        # Do NOT set autocommit in connect_args – it breaks session.commit()
        # Use default autocommit=False (transactions are managed by session.commit/rollback)

        _engine = create_engine(
            DATABASE_URL,
            connect_args=connect_args,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
        )

    return _engine


def get_session_factory():
    global _SessionFactory

    if _SessionFactory is None:
        engine = get_engine()
        _SessionFactory = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,       # essential – transactions are explicit
        )

    return _SessionFactory


SessionLocal = get_session_factory()


def get_session():
    return SessionLocal()


def init_db():
    """Create admin user if none exists."""
    session = get_session()
    try:
        if session.query(User).count() == 0:
            hashed = hashlib.sha256("***REMOVED***".encode()).hexdigest()

            admin = User(
                username="admin",
                password_hash=hashed,
                full_name="مدیر سیستم",
                role=UserRole.ADMIN,
                is_active=True
            )

            session.add(admin)
            session.commit()

        else:
            admin = session.query(User).filter_by(username="admin").first()
            if admin:
                admin.password_hash = hashlib.sha256("***REMOVED***".encode()).hexdigest()
                session.commit()

    except Exception as e:
        session.rollback()
        print(f"⚠️ DB INIT ERROR: {e}")

    finally:
        session.close()
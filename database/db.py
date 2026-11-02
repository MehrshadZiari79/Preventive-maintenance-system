
# database/db.py
"""
PM System - Database Connection
================================

Legacy SQL Server compatibility layer.

Why this file contains a compatibility override:
-----------------------------------------------
The application uses SQLAlchemy + pymssql with an old SQL Server.

Modern SQLAlchemy's MSSQL dialect performs connection initialization using:

    SELECT schema_name()

Very old SQL Server versions do not support that function.

For this application the database tables are under the normal SQL Server
schema "dbo", so we explicitly tell SQLAlchemy the default schema instead
of making it execute schema_name().

Important:
- Does NOT modify the database.
- Does NOT recreate tables.
- Does NOT delete data.
- Does NOT migrate existing data.
- Keeps the existing pymssql connection.
- Keeps normal SQLAlchemy ORM/session behavior.
"""

from __future__ import annotations

import hashlib
import types

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from database.models import User, UserRole


# ============================================================================
# DATABASE CONNECTION SETTINGS
# ============================================================================
#
# The server address, login and password are NOT stored in the source code.
# They live in database/db_secrets.py, a small file that exists only on the
# build PC (git-ignored) and is bundled into the program by PyInstaller.
# Copy database/db_secrets.example.py to database/db_secrets.py and fill it in.
#
# PM_DATABASE_URL (environment variable) overrides everything - for test
# databases only.
# ============================================================================

try:
    from database import db_secrets as _secrets
except ImportError:          # not configured on this PC
    _secrets = None

_server = getattr(_secrets, "DB_SERVER", "")
_database = getattr(_secrets, "DB_NAME", "PM_Database")
_username = getattr(_secrets, "DB_USER", "")
_port = str(getattr(_secrets, "DB_PORT", "1433"))


# ============================================================================
# LEGACY SQL SERVER SETTINGS
# ============================================================================

# Normal SQL Server object schema.
#
# Your existing application tables are expected to be under dbo.
# This avoids the unsupported SQLAlchemy startup query:
#
#     SELECT schema_name()
#
_DEFAULT_SCHEMA = "dbo"

# Legacy TDS protocol used by the existing application.
#
# The old application already used 7.0, so keep it.
_TDS_VERSION = "7.0"


# ============================================================================
# PASSWORD / DATABASE URL
# ============================================================================

def _get_password() -> str:
    return str(getattr(_secrets, "DB_PASSWORD", "") or "")


def get_database_url() -> str:
    """Build the SQLAlchemy connection URL from database/db_secrets.py."""
    if not (_server and _username):
        return ""
    from urllib.parse import quote_plus
    return (
        f"mssql+pymssql://"
        f"{quote_plus(_username)}:"
        f"{quote_plus(_get_password())}@"
        f"{_server}:"
        f"{_port}/"
        f"{_database}"
        f"?charset=utf8"
    )


import os as _os

# Developer/testing override only. Production never sets this variable, so
# clients keep connecting to PM_Database exactly as before.
_URL_OVERRIDE = _os.environ.get("PM_DATABASE_URL", "").strip()

DATABASE_URL = _URL_OVERRIDE or get_database_url()


# ============================================================================
# GLOBAL ENGINE / SESSION FACTORY
# ============================================================================

_engine = None
_SessionFactory = None


# ============================================================================
# LEGACY MSSQL COMPATIBILITY
# ============================================================================

def _install_legacy_mssql_compatibility(engine) -> None:
    """
    Install compatibility overrides on the SQLAlchemy MSSQL dialect.

    The critical problem with the legacy SQL Server is SQLAlchemy's default
    implementation of:

        _get_default_schema_name()

    which executes:

        SELECT schema_name()

    That function is unavailable on very old SQL Server versions.

    We therefore override only that dialect initialization method and return
    the application's known default schema, "dbo".

    This affects SQLAlchemy's internal initialization only. It does NOT run
    any SQL statement and does NOT alter the database.
    """

    dialect = engine.dialect

    def _legacy_default_schema(
        self,
        connection,
    ):
        """
        Return the known SQL Server default schema without querying
        schema_name().
        """
        return _DEFAULT_SCHEMA

    dialect._get_default_schema_name = types.MethodType(
        _legacy_default_schema,
        dialect,
    )


# ============================================================================
# ENGINE
# ============================================================================

def get_engine():
    """
    Return the application SQLAlchemy engine.

    The engine is created once and reused.

    Legacy SQL Server compatibility is installed immediately after creating
    the engine, BEFORE the first actual database connection is opened.
    """
    global _engine

    if _engine is None:

        if not DATABASE_URL:
            raise RuntimeError(
                "تنظیمات اتصال به پایگاه داده پیدا نشد.\n"
                "Database settings missing: create database/db_secrets.py "
                "from database/db_secrets.example.py and build again."
            )

        if _URL_OVERRIDE:
            _engine = create_engine(DATABASE_URL, echo=False)
            return _engine

        connect_args = {
            # Keep the same legacy TDS configuration used by the original
            # application.
            "tds_version": _TDS_VERSION,
        }

        _engine = create_engine(
            DATABASE_URL,

            connect_args=connect_args,

            poolclass=QueuePool,

            pool_size=10,

            max_overflow=20,

            # Check connections before reuse.
            pool_pre_ping=True,

            echo=False,
        )

        # ---------------------------------------------------------------
        # CRITICAL:
        #
        # Patch the MSSQL dialect BEFORE the first connection is opened.
        #
        # Without this, SQLAlchemy 2.x attempts:
        #
        #     SELECT schema_name()
        #
        # and old SQL Server rejects it.
        # ---------------------------------------------------------------

        _install_legacy_mssql_compatibility(
            _engine
        )

    return _engine


# ============================================================================
# SESSION FACTORY
# ============================================================================

def get_session_factory():
    """
    Return the global SQLAlchemy Session factory.
    """
    global _SessionFactory

    if _SessionFactory is None:

        engine = get_engine()

        _SessionFactory = sessionmaker(
            bind=engine,

            # Preserve the application's existing behavior.
            autoflush=False,

            # Explicit transactions:
            #
            # session.commit()
            # session.rollback()
            #
            autocommit=False,
        )

    return _SessionFactory


# ============================================================================
# PUBLIC SESSION OBJECT
# ============================================================================

SessionLocal = get_session_factory()


def get_session():
    """
    Return a new SQLAlchemy session.
    """
    return SessionLocal()


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_db():
    """
    First start on an EMPTY database: create the «admin» account with the
    password from database/db_secrets.py (INITIAL_ADMIN_PASSWORD).

    Nothing else happens.  Earlier versions also reset the admin password to a
    value written in the code on every login, which undid any password change
    and put the password in the source; both are gone.
    IMPORTANT: this function does NOT create or change tables.
    """
    session = get_session()
    try:
        if session.query(User).count() > 0:
            return
        initial = str(getattr(_secrets, "INITIAL_ADMIN_PASSWORD", "") or "")
        if not initial:
            print("init_db: no users and no INITIAL_ADMIN_PASSWORD in db_secrets.py")
            return
        session.add(User(
            username="admin",
            password_hash=hashlib.sha256(initial.encode("utf-8")).hexdigest(),
            full_name="مدیر سیستم",
            role=UserRole.ADMIN,
            is_active=True,
        ))
        session.commit()
    except Exception as exc:
        session.rollback()
        print(f"⚠️ DB INIT ERROR: {exc}")
    finally:
        session.close()

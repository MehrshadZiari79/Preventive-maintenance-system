"""
Gela PM System - add the machine-hours tables from your own PC
==============================================================

    db_setup.bat            (double-click)

Runs deploy\\add_machine_shift_tables.sql against PM_Database on the server.
It only ADDS two new tables (nothing existing is changed) and is safe to run
again: if the tables already exist it does nothing.

It first tries the application's own login.  If that login is not allowed to
create tables, it asks for an SQL admin login (for example sa); the password
is typed in and never saved.
"""

import getpass
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
SQL_FILE = ROOT / "deploy" / "add_machine_shift_tables.sql"
TABLES = ("machine_shift_logs", "machine_downtime_events")


def connect_like_app():
    """Exactly the connection the application uses (database/db.py)."""
    from database import db as appdb
    raw = appdb.get_engine().raw_connection()
    driver = getattr(raw, "driver_connection", None) or getattr(raw, "connection", raw)
    driver.autocommit(True)
    return driver


def connect(user, password):
    import pymssql
    from database import db as appdb
    return pymssql.connect(server=appdb._server, port=str(appdb._port), user=user,
                           password=password, database=appdb._database,
                           tds_version=appdb._TDS_VERSION, charset="UTF-8",
                           login_timeout=15, autocommit=True)


def tables_exist(cur):
    for name in TABLES:
        cur.execute("SELECT OBJECT_ID(%s)", (name,))
        if cur.fetchone()[0] is None:
            return False
    return True


def run_script(cur):
    sql = SQL_FILE.read_text(encoding="utf-8-sig")
    # split on lines that contain only GO (as SSMS does)
    for batch in re.split(r"(?im)^\s*GO\s*$", sql):
        if batch.strip():
            cur.execute(batch)
            while cur.nextset():
                pass


def main():
    from database import db as appdb
    print("=" * 60)
    print(" PM System - machine-hours tables")
    print(f" server {appdb._server}, database {appdb._database}")
    print("=" * 60)

    for attempt in range(1):   # always as the app login: the tables must sit next to its tables
        if attempt == 0:
            user, password = appdb._username, None
        else:
            print("\nUse an SQL admin login (the app login could not do it).")
            user = input("SQL login [sa]: ").strip() or "sa"
            password = getpass.getpass(f"Password for {user}: ")
        try:
            conn = connect_like_app() if attempt == 0 else connect(user, password)
        except Exception as exc:
            print(f"  Cannot connect as {user}: {exc}")
            continue
        cur = conn.cursor()
        if tables_exist(cur):
            print("\nThe tables already exist - nothing to do.")
            conn.close()
            return 0
        print(f"\nCreating tables as {user} ...")
        try:
            run_script(cur)
        except Exception as exc:
            print(f"  Not allowed / failed: {exc}")
            conn.close()
            continue
        ok = tables_exist(cur)
        conn.close()
        if ok:
            print("\nDone: machine_shift_logs and machine_downtime_events created.")
            print("Machine hours now saves shifts and stop reasons.")
            return 0
        print("  The tables are still missing - see the messages above.")
        return 1
    print("\nNot done. Send the message above to the developer.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

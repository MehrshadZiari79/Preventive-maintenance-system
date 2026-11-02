# database/db_secrets.example.py
"""
Connection settings for the production database - TEMPLATE.

1. Copy this file to  database/db_secrets.py  (same folder).
2. Fill in the real values.
3. Never commit db_secrets.py: it is listed in .gitignore.

PyInstaller bundles db_secrets.py into the program when it is present on the
build PC; release.py and build_release.bat refuse to build without it, so a
release can never ship without database settings.
"""

DB_SERVER = "192.168.0.1"      # SQL Server address on the LAN
DB_PORT = "1433"
DB_NAME = "PM_Database"
DB_USER = "pm_app"             # application login (read/write on PM_Database)
DB_PASSWORD = "change-me"

# Used ONCE, only when the users table is completely empty, to create the
# «admin» account. Change the admin password in the program afterwards.
INITIAL_ADMIN_PASSWORD = "change-me"

# migrate_role_permissions.py
from database.db import get_engine
from sqlalchemy import text

def migrate():
    engine = get_engine()
    with engine.connect() as conn:
        try:
            # Ensure the table is under dbo schema
            conn.execute(text("""
                IF OBJECT_ID('dbo.role_permissions', 'U') IS NOT NULL
                    DROP TABLE dbo.role_permissions
            """))
            conn.execute(text("""
                CREATE TABLE dbo.role_permissions (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    role_name NVARCHAR(50) NOT NULL UNIQUE,
                    permissions_json NTEXT NULL
                )
            """))
            print("✅ dbo.role_permissions table is ready")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    migrate()
import hashlib
from database.db import SessionLocal
from database.models import User, UserRole
from config import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def seed_admin():
    db = SessionLocal()
    try:
        existing_admin = db.query(User).filter(
            User.username == DEFAULT_ADMIN_USERNAME
        ).first()

        if not existing_admin:
            admin = User(
                username=DEFAULT_ADMIN_USERNAME,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                full_name="مدیر سیستم",
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print("✅ Admin user created.")
        else:
            print("ℹ️  Admin already exists, skipping seed.")

        existing_tech = db.query(User).filter(
            User.username == "technician"
        ).first()

        if not existing_tech:
            technician = User(
                username="technician",
                password_hash=hash_password("tech123"),
                full_name="تکنسین پیش‌فرض",
                role=UserRole.TECHNICIAN.value,
                is_active=True,
            )
            db.add(technician)
            db.commit()
            print("✅ Default technician created (username: technician, password: tech123).")
        else:
            print("ℹ️  Technician already exists, skipping seed.")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed error: {e}")
    finally:
        db.close()

import hashlib
from datetime import datetime
from database.db import SessionLocal
from database.models import User, UserRole


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class AuthManager:
    _current_user: User = None

    @classmethod
    def login(cls, username: str, password: str) -> tuple:
        db = SessionLocal()
        try:
            user = db.query(User).filter(
                User.username == username,
                User.is_active == True
            ).first()

            if not user:
                return False, "نام کاربری یافت نشد."

            if user.password_hash != hash_password(password):
                return False, "رمز عبور اشتباه است."

            user.last_login = datetime.utcnow()
            db.commit()

            cls._current_user = User(
                id=user.id,
                username=user.username,
                password_hash=user.password_hash,
                full_name=user.full_name,
                role=user.role,
                is_active=user.is_active,
                last_login=user.last_login,
            )
            return True, "ورود موفق"

        except Exception as e:
            return False, f"خطا: {e}"
        finally:
            db.close()

    @classmethod
    def logout(cls):
        cls._current_user = None

    @classmethod
    def get_current_user(cls) -> User:
        return cls._current_user

    @classmethod
    def has_permission(cls, min_role: str) -> bool:
        if not cls._current_user:
            return False
        role_rank = {
            UserRole.ADMIN.value: 3,
            UserRole.MANAGER.value: 2,
            UserRole.TECHNICIAN.value: 1,
        }
        user_rank = role_rank.get(cls._current_user.role, 0)
        required_rank = role_rank.get(min_role, 99)
        return user_rank >= required_rank

"""
User Repository - Data Access Layer for User Management
"""
import hashlib
from typing import Optional
from database.db import SessionLocal
from database.models import User


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class UserRepository:
    def __init__(self):
        pass

    def _session(self):
        return SessionLocal()

    # ─────────────────────────── READ ───────────────────────────

    def get_all_users(self) -> list[dict]:
        with self._session() as session:
            users = session.query(User).order_by(User.created_at.desc()).all()
            return [self._to_dict(u) for u in users]

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        with self._session() as session:
            u = session.query(User).filter(User.id == user_id).first()
            return self._to_dict(u) if u else None

    def get_user_by_username(self, username: str) -> Optional[dict]:
        with self._session() as session:
            u = session.query(User).filter(User.username == username).first()
            return self._to_dict(u) if u else None

    def search_users(self, keyword: str) -> list[dict]:
        with self._session() as session:
            pattern = f"%{keyword}%"
            users = session.query(User).filter(
                (User.username.like(pattern)) | (User.full_name.like(pattern))
            ).order_by(User.created_at.desc()).all()
            return [self._to_dict(u) for u in users]

    def username_exists(self, username: str, exclude_id: Optional[int] = None) -> bool:
        with self._session() as session:
            q = session.query(User).filter(User.username == username)
            if exclude_id:
                q = q.filter(User.id != exclude_id)
            return q.first() is not None

    # ─────────────────────────── WRITE ──────────────────────────

    def create_user(self, username: str, password: str,
                    full_name: str, role: str) -> tuple[bool, str]:
        if self.username_exists(username):
            return False, "این نام کاربری قبلاً ثبت شده است."
        try:
            with self._session() as session:
                user = User(
                    username=username,
                    password_hash=_hash_password(password),
                    full_name=full_name,
                    role=role,
                    is_active=True
                )
                session.add(user)
                session.commit()
            return True, "کاربر با موفقیت ایجاد شد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    def update_user(self, user_id: int, username: str,
                    full_name: str, role: str) -> tuple[bool, str]:
        if self.username_exists(username, exclude_id=user_id):
            return False, "این نام کاربری قبلاً ثبت شده است."
        try:
            with self._session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return False, "کاربر یافت نشد."
                user.username = username
                user.full_name = full_name
                user.role = role
                session.commit()
            return True, "اطلاعات کاربر بروزرسانی شد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    def change_password(self, user_id: int, new_password: str) -> tuple[bool, str]:
        try:
            with self._session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return False, "کاربر یافت نشد."
                user.password_hash = _hash_password(new_password)
                session.commit()
            return True, "رمز عبور با موفقیت تغییر کرد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    def toggle_active(self, user_id: int) -> tuple[bool, str]:
        try:
            with self._session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return False, "کاربر یافت نشد."
                user.is_active = not user.is_active
                session.commit()
            return True, "وضعیت کاربر تغییر کرد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    def delete_user(self, user_id: int) -> tuple[bool, str]:
        try:
            with self._session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return False, "کاربر یافت نشد."
                session.delete(user)
                session.commit()
            return True, "کاربر حذف شد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    # ─────────────────────────── HELPER ─────────────────────────

    @staticmethod
    def _to_dict(u: User) -> dict:
        return {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": str(u.created_at) if u.created_at else "",
        }

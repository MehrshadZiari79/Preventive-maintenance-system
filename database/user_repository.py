# database/user_repository.py
import hashlib
from typing import Optional
from database.models import User, Inspection, ActivityLog, PMSchedule, work_order_technicians
from database.work_order import WorkOrder
from utils.logger import log_action


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class UserRepository:
    def __init__(self, session_factory):
        self.Session = session_factory

    def get_all_users(self) -> list[dict]:
        session = self.Session()
        try:
            users = session.query(User).order_by(User.created_at.desc()).all()
            return [self._to_dict(u) for u in users]
        finally:
            session.close()

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        session = self.Session()
        try:
            u = session.query(User).filter(User.id == user_id).first()
            return self._to_dict(u) if u else None
        finally:
            session.close()

    def get_user_by_username(self, username: str) -> Optional[dict]:
        session = self.Session()
        try:
            u = session.query(User).filter(User.username == username).first()
            return self._to_dict(u) if u else None
        finally:
            session.close()

    def search_users(self, keyword: str) -> list[dict]:
        session = self.Session()
        try:
            pattern = f"%{keyword}%"
            users = session.query(User).filter(
                (User.username.like(pattern)) | (User.full_name.like(pattern))
            ).order_by(User.created_at.desc()).all()
            return [self._to_dict(u) for u in users]
        finally:
            session.close()

    def username_exists(self, username: str, exclude_id: Optional[int] = None) -> bool:
        session = self.Session()
        try:
            q = session.query(User).filter(User.username == username)
            if exclude_id:
                q = q.filter(User.id != exclude_id)
            return q.first() is not None
        finally:
            session.close()

    def create_user(self, username: str, password: str,
                    full_name: str, role: str,
                    personnel_code: str = None,
                    service_unit: str = None) -> tuple[bool, str]:
        if self.username_exists(username):
            return False, "این نام کاربری قبلاً ثبت شده است."
        session = self.Session()
        try:
            user = User(
                username=username,
                password_hash=_hash_password(password),
                full_name=full_name,
                role=role,
                is_active=True,
                personnel_code=personnel_code,
                service_unit=service_unit,
            )
            session.add(user)
            session.commit()
            log_action("CREATE", "user", user.id, f"نام کاربری: {username}, نقش: {role}")
            return True, "کاربر با موفقیت ایجاد شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def update_user(self, user_id: int, username: str,
                    full_name: str, role: str,
                    personnel_code: str = None,
                    service_unit: str = None) -> tuple[bool, str]:
        if self.username_exists(username, exclude_id=user_id):
            return False, "این نام کاربری قبلاً ثبت شده است."
        session = self.Session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "کاربر یافت نشد."
            user.username = username
            user.full_name = full_name
            user.role = role
            user.personnel_code = personnel_code
            user.service_unit = service_unit
            session.commit()
            log_action("UPDATE", "user", user_id, f"نام کاربری جدید: {username}, نقش: {role}")
            return True, "اطلاعات کاربر بروزرسانی شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def change_password(self, user_id: int, new_password: str) -> tuple[bool, str]:
        session = self.Session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "کاربر یافت نشد."
            user.password_hash = _hash_password(new_password)
            session.commit()
            log_action("CHANGE_PASSWORD", "user", user_id, "رمز عبور تغییر کرد")
            return True, "رمز عبور با موفقیت تغییر کرد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def toggle_active(self, user_id: int) -> tuple[bool, str]:
        session = self.Session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "کاربر یافت نشد."
            user.is_active = not user.is_active
            session.commit()
            log_action("TOGGLE_ACTIVE", "user", user_id, f"فعال: {user.is_active}")
            return True, "وضعیت کاربر تغییر کرد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def get_history_counts(self, user_id: int) -> dict:
        """Records that reference this user (work history / audit trail)."""
        from sqlalchemy import or_, func
        from database.models import RepairRequestDocument, RepairRequestCompletion
        session = self.Session()
        try:
            counts = {
                "work_orders": session.query(func.count(WorkOrder.id)).filter(or_(
                    WorkOrder.technician_id == user_id,
                    WorkOrder.supervisor_id == user_id,
                    WorkOrder.operator_id == user_id,
                )).scalar() or 0,
                "work_order_assignments": session.query(func.count()).select_from(
                    work_order_technicians).filter(
                    work_order_technicians.c.user_id == user_id).scalar() or 0,
                "inspections": session.query(func.count(Inspection.id)).filter(
                    Inspection.inspector_id == user_id).scalar() or 0,
                "repair_requests": session.query(func.count(RepairRequestDocument.id)).filter(
                    RepairRequestDocument.created_by_user_id == user_id).scalar() or 0,
                "repair_completions": session.query(func.count(RepairRequestCompletion.id)).filter(
                    RepairRequestCompletion.completed_by_user_id == user_id).scalar() or 0,
                "activity_logs": session.query(func.count(ActivityLog.id)).filter(
                    ActivityLog.user_id == user_id).scalar() or 0,
            }
            return counts
        finally:
            session.close()

    def delete_user(self, user_id: int) -> tuple[bool, str]:
        """
        Delete a user only when nothing in the system refers to them.

        A user with work history (work orders, inspections, repair requests,
        activity log) is kept so that reports and the audit trail stay
        complete; such users should be deactivated instead.
        """
        try:
            counts = self.get_history_counts(user_id)
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

        labels = {
            "work_orders": "دستور کار",
            "work_order_assignments": "تخصیص دستور کار",
            "inspections": "بازرسی",
            "repair_requests": "درخواست تعمیر",
            "repair_completions": "اتمام درخواست تعمیر",
            "activity_logs": "رکورد لاگ فعالیت",
        }
        used = [f"{n} {labels[k]}" for k, n in counts.items() if n]
        if used:
            return False, (
                "این کاربر در سوابق سیستم ثبت شده است ("
                + "، ".join(used)
                + ") و برای حفظ سوابق قابل حذف نیست.\n"
                "به‌جای حذف، کاربر را «غیرفعال» کنید تا دیگر نتواند وارد شود."
            )

        session = self.Session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "کاربر یافت نشد."
            # legacy PM technician assignment is not history - just detach it
            session.query(PMSchedule).filter(PMSchedule.technician_id == user_id).update(
                {PMSchedule.technician_id: None}, synchronize_session=False)
            username = user.username
            session.delete(user)
            session.commit()
            log_action("DELETE", "user", user_id, f"نام کاربری: {username}")
            return True, "کاربر حذف شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    @staticmethod
    def _to_dict(u: User) -> dict:
        return {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "personnel_code": u.personnel_code or "",
            "service_unit": u.service_unit or "",
            "created_at": str(u.created_at) if u.created_at else "",
        }
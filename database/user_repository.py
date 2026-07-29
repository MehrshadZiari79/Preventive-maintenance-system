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

    def delete_user(self, user_id: int) -> tuple[bool, str]:
        session = self.Session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "کاربر یافت نشد."

            # 1. Remove from many-to-many work_order_technicians
            session.execute(work_order_technicians.delete().where(work_order_technicians.c.user_id == user_id))

            # 2. Delete activity logs
            session.query(ActivityLog).filter(ActivityLog.user_id == user_id).delete(synchronize_session=False)

            # 3. Delete inspections
            session.query(Inspection).filter(Inspection.inspector_id == user_id).delete(synchronize_session=False)

            # 4. Nullify references in WorkOrders
            session.query(WorkOrder).filter(WorkOrder.technician_id == user_id).update(
                {WorkOrder.technician_id: None}, synchronize_session=False)
            session.query(WorkOrder).filter(WorkOrder.supervisor_id == user_id).update(
                {WorkOrder.supervisor_id: None}, synchronize_session=False)
            session.query(WorkOrder).filter(WorkOrder.operator_id == user_id).update(
                {WorkOrder.operator_id: None}, synchronize_session=False)

            # 5. Nullify technician_id in PM Schedules
            session.query(PMSchedule).filter(PMSchedule.technician_id == user_id).update(
                {PMSchedule.technician_id: None}, synchronize_session=False)

            # 6. Delete the user
            session.delete(user)
            session.commit()
            log_action("DELETE", "user", user_id, "")
            return True, "کاربر و تمام اطلاعات مرتبط با موفقیت حذف شد."
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
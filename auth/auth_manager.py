# auth/auth_manager.py
import hashlib, json
from datetime import datetime
from database.models import User, UserRole, RolePermissions

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

class AuthManager:
    _current_user: User = None

    @classmethod
    def login(cls, username: str, password: str) -> tuple:
        from database.db import SessionLocal
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

    # Built‑in rank‑based permission (for original roles)
    @classmethod
    def has_permission(cls, min_role: str) -> bool:
        if not cls._current_user:
            return False
        builtin_roles = {r.value for r in UserRole}
        if cls._current_user.role in builtin_roles:
            role_rank = {
                UserRole.ADMIN.value: 4,
                UserRole.MANAGER.value: 3,
                UserRole.PRODUCTION_EXPERT.value: 2,
                UserRole.TECHNICIAN.value: 1,
            }
            user_rank = role_rank.get(cls._current_user.role, 0)
            required_rank = role_rank.get(min_role, 99)
            return user_rank >= required_rank
        # Custom role – fall back to granular read permission
        return cls._check_custom_permission(min_role, "read")

    # Check granular permission for custom roles
    @classmethod
    def _check_custom_permission(cls, module: str, action: str) -> bool:
        if not cls._current_user:
            return False
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            perm = db.query(RolePermissions).filter(
                RolePermissions.role_name == cls._current_user.role
            ).first()
            if not perm or not perm.permissions_json:
                return False
            perms = json.loads(perm.permissions_json)
            module_perms = perms.get(module, {})
            return module_perms.get(action, False)
        except:
            return False
        finally:
            db.close()

    # ── Public method for views to check any action ─────────────────
    @classmethod
    def can_access(cls, module: str, action: str = "read") -> bool:
        """
        Returns True if the current user has the given action (read/write/delete)
        on a module. Built‑in admin/manager can everything.
        """
        if not cls._current_user:
            return False
        builtin_roles = {r.value for r in UserRole}
        if cls._current_user.role in builtin_roles:
            # Admin & manager can do everything
            if cls._current_user.role in [UserRole.ADMIN.value, UserRole.MANAGER.value]:
                return True
            # Technician & production expert are limited to their existing permissions
            # For write/delete actions, we still fall back to rank logic
            if action == "read":
                return cls.has_permission(UserRole.TECHNICIAN.value)
            # For write/delete, we return False unless the role already has that power
            # (technicians can now write equipment, work orders, etc. – those views already
            #  have their own checks; this method is a gate for custom roles only)
            return False
        # Custom role
        return cls._check_custom_permission(module, action)

    # ── Role management helpers ──────────────────────────────────────
    @classmethod
    def get_role_list(cls):
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            builtins = [{"name": r.value, "is_builtin": True} for r in UserRole]
            customs = db.query(RolePermissions).all()
            result = builtins + [{"name": c.role_name, "is_builtin": False} for c in customs]
            return result
        finally:
            db.close()

    @classmethod
    def get_role_permissions(cls, role_name: str):
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            perm = db.query(RolePermissions).filter(RolePermissions.role_name == role_name).first()
            if perm and perm.permissions_json:
                return json.loads(perm.permissions_json)
            modules = ["dashboard", "equipment", "pm_schedule", "work_orders",
                       "inspection", "spare_parts", "reports", "users",
                       "activity_log", "machine_hours"]
            return {m: {"read": False, "write": False, "delete": False} for m in modules}
        finally:
            db.close()

    @classmethod
    def save_role_permissions(cls, role_name: str, permissions: dict):
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            perm = db.query(RolePermissions).filter(RolePermissions.role_name == role_name).first()
            if perm:
                perm.permissions_json = json.dumps(permissions, ensure_ascii=False)
            else:
                db.add(RolePermissions(role_name=role_name, permissions_json=json.dumps(permissions, ensure_ascii=False)))
            db.commit()
            return True, "ذخیره شد."
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    @classmethod
    def delete_role(cls, role_name: str):
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            db.query(RolePermissions).filter(RolePermissions.role_name == role_name).delete()
            db.query(User).filter(User.role == role_name).update({User.role: UserRole.TECHNICIAN.value})
            db.commit()
            return True, "نقش حذف شد و کاربران آن به نقش تکنسین بازگردانده شدند."
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()
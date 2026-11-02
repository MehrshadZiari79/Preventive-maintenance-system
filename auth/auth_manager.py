# auth/auth_manager.py
import hashlib, json
from database.models import User, UserRole, RolePermissions
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock

# Every page that can appear in the sidebar. Custom-role permissions are stored
# per key in role_permissions.permissions_json. (v2.3 was missing
# "repair_request" and "personnel_management", so custom roles could never be
# given those pages.)
PERMISSION_MODULES = [
    ("dashboard",            "داشبورد"),
    ("equipment",            "تجهیزات"),
    ("pm_schedule",          "برنامه PM"),
    ("work_orders",          "دستور کارها"),
    ("repair_request",       "حکم درخواست تعمیرات"),
    ("personnel_management", "پرسنل و دپارتمان‌ها"),
    ("inspection",           "بازرسی‌ها"),
    ("spare_parts",          "قطعات یدکی"),
    ("reports",              "تحلیل و گزارشات"),
    ("users",                "مدیریت کاربران"),
    ("activity_log",         "لاگ فعالیت"),
    ("machine_hours",        "ساعت کار ماشین"),
]

# users.role is NVARCHAR(20) in the database.
ROLE_NAME_MAX_LEN = 20

# Persian names of the built-in roles (shown everywhere instead of the codes).
BUILTIN_ROLE_FA = {
    "admin": "مدیر سیستم",
    "manager": "مدیر",
    "technician": "تکنسین",
    "production_expert": "کارشناس تولید",
}

# Actions of the permission matrix, in display order.
PERMISSION_ACTIONS = (
    ("read",    "مشاهده"),
    ("write",   "ایجاد / ویرایش"),
    ("approve", "تأیید"),
    ("delete",  "حذف"),
)
ALL_ACTIONS = tuple(a for a, _ in PERMISSION_ACTIONS)

# Which actions mean something on each page (the others are shown as «—»).
#   approve (work orders): approve creation, final approval, reject a finish
#           request, generate PM work orders.  Editing a work order and moving
#           it back to an earlier stage are open to every role that can see
#           the work-orders page.
#   delete  (equipment):  also manage the category and location lists
MODULE_ACTIONS = {
    "dashboard":            ("read",),
    "equipment":            ("read", "write", "delete"),
    "pm_schedule":          ("read", "write", "delete"),
    "work_orders":          ("read", "write", "approve", "delete"),
    "repair_request":       ("read", "write", "delete"),
    "personnel_management": ("read", "write", "delete"),
    "inspection":           ("read", "write", "delete"),
    "spare_parts":          ("read", "write", "delete"),
    "reports":              ("read",),
    "users":                ("read", "write", "delete"),
    "activity_log":         ("read",),
    "machine_hours":        ("read", "write", "delete"),
}

# Never given to a custom role: whoever manages users could make himself admin.
ADMIN_ONLY_MODULES = frozenset({"users"})

PARTIAL = "partial"      # built-in roles only: part of the action is allowed

# What the BUILT-IN roles can really do in the program (read-only display in
# «مدیریت نقش‌ها»; their behaviour itself is coded in the pages).
def _builtin(spec):
    out = {}
    for module, _label in PERMISSION_MODULES:
        given = spec.get(module, "")
        out[module] = {
            action: (PARTIAL if action == "approve" and given.endswith("~") and "a" in given
                     else action[0] in given.rstrip("~"))
            for action in ALL_ACTIONS
        }
    return out

BUILTIN_PERMISSIONS = {
    "admin": _builtin({m: "rwad" for m, _ in PERMISSION_MODULES}),
    "manager": _builtin({
        "dashboard": "r", "equipment": "rwd", "pm_schedule": "rwd", "work_orders": "rwad",
        "repair_request": "rwd", "personnel_management": "rwd", "inspection": "rwd",
        "spare_parts": "rwd", "reports": "r", "machine_hours": "rwd",
    }),
    "technician": _builtin({
        "dashboard": "r", "equipment": "rw", "work_orders": "rw", "repair_request": "rw",
        "inspection": "r", "spare_parts": "rwd", "reports": "r", "machine_hours": "rw",
    }),
    "production_expert": _builtin({
        "dashboard": "r", "equipment": "r", "work_orders": "rwa~", "repair_request": "rw",
    }),
}
BUILTIN_PARTIAL_NOTES = {
    "production_expert": "تأیید دستور کار: فقط «تأیید ایجاد»؛ تأیید نهایی و رد اتمام با مدیر است.",
}


def normalize_permissions(permissions: dict) -> dict:
    """
    Clean a custom role's matrix: only known pages, only the actions that
    mean something on that page, admin-only pages off, and «مشاهده» switched
    on whenever any other action is on (and everything off without it).
    """
    clean = {}
    for module, _label in PERMISSION_MODULES:
        given = (permissions or {}).get(module) or {}
        allowed = MODULE_ACTIONS.get(module, ("read",))
        row = {a: bool(given.get(a, False)) and a in allowed for a in ALL_ACTIONS}
        if module in ADMIN_ONLY_MODULES:
            row = {a: False for a in ALL_ACTIONS}
        if any(row[a] for a in ALL_ACTIONS if a != "read"):
            row["read"] = True
        clean[module] = row
    return clean


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
            user.last_login = tehran_now()
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
            perms = normalize_permissions(json.loads(perm.permissions_json))
            return bool(perms.get(module, {}).get(action, False))
        except Exception:
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

    @staticmethod
    def is_builtin_role(role_name: str) -> bool:
        return role_name in {r.value for r in UserRole}

    @classmethod
    def allows(cls, builtin_roles, module: str, action: str = "read") -> bool:
        """
        One rule for every page:
          * built-in roles: allowed when the role is in `builtin_roles`
            (exactly the behaviour each page had before);
          * custom roles: what «مدیریت نقش‌ها» says for (module, action).
        """
        user = cls._current_user
        if not user:
            return False
        if cls.is_builtin_role(user.role):
            return user.role in set(builtin_roles or ())
        return cls._check_custom_permission(module, action)

    # ── Role management helpers ──────────────────────────────────────
    @classmethod
    def get_role_list(cls):
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            builtin_names = [r.value for r in UserRole]
            builtins = [{"name": n, "is_builtin": True} for n in builtin_names]
            customs = (
                db.query(RolePermissions)
                .order_by(RolePermissions.role_name)
                .all()
            )
            result = builtins + [
                {"name": c.role_name, "is_builtin": False}
                for c in customs
                if c.role_name and c.role_name not in builtin_names
            ]
            return result
        finally:
            db.close()

    @classmethod
    def get_role_permissions(cls, role_name: str):
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            if cls.is_builtin_role(role_name):
                return {m: dict(a) for m, a in BUILTIN_PERMISSIONS.get(role_name, {}).items()}
            perm = db.query(RolePermissions).filter(RolePermissions.role_name == role_name).first()
            stored = {}
            if perm and perm.permissions_json:
                try:
                    stored = json.loads(perm.permissions_json) or {}
                except ValueError:
                    stored = {}
            return normalize_permissions(stored if isinstance(stored, dict) else {})
        finally:
            db.close()

    @classmethod
    def save_role_permissions(cls, role_name: str, permissions: dict):
        from database.db import SessionLocal
        if cls.is_builtin_role(role_name):
            return False, "مجوزهای نقش‌های پیش‌فرض قابل تغییر نیست."
        clean = normalize_permissions(permissions)
        db = SessionLocal()
        try:
            perm = db.query(RolePermissions).filter(RolePermissions.role_name == role_name).first()
            created = perm is None
            if perm:
                perm.permissions_json = json.dumps(clean, ensure_ascii=False)
            else:
                db.add(RolePermissions(role_name=role_name, permissions_json=json.dumps(clean, ensure_ascii=False)))
            db.commit()
            cls._log("CREATE" if created else "UPDATE", role_name, cls.describe_permissions(clean))
            return True, "ذخیره شد."
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    @classmethod
    def validate_role_name(cls, name: str, existing=None):
        """Return an error message, or None when the name can be used."""
        name = (name or "").strip()
        if not name:
            return "نام نقش را وارد کنید."
        if len(name) > ROLE_NAME_MAX_LEN:
            return f"نام نقش حداکثر {ROLE_NAME_MAX_LEN} کاراکتر می‌تواند باشد."
        if name in {r.value for r in UserRole} or name in BUILTIN_ROLE_FA.values():
            return "این نام متعلق به نقش‌های پیش‌فرض است."
        names = existing if existing is not None else [r["name"] for r in cls.get_role_list()]
        if name in names:
            return "نقشی با این نام وجود دارد."
        return None

    @classmethod
    def rename_role(cls, old_name: str, new_name: str):
        """Rename a custom role and move its users to the new name (one transaction)."""
        from database.db import SessionLocal
        new_name = (new_name or "").strip()
        error = cls.validate_role_name(new_name)
        if error:
            return False, error
        db = SessionLocal()
        try:
            perm = db.query(RolePermissions).filter(RolePermissions.role_name == old_name).first()
            if not perm:
                return False, "نقش یافت نشد."
            perm.role_name = new_name
            db.query(User).filter(User.role == old_name).update(
                {User.role: new_name}, synchronize_session=False)
            db.commit()
            if cls._current_user is not None and cls._current_user.role == old_name:
                cls._current_user.role = new_name
            cls._log("RENAME", new_name, f"{old_name} → {new_name}")
            return True, "نام نقش تغییر کرد."
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    @classmethod
    def count_role_users(cls, role_name: str) -> int:
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            return db.query(User).filter(User.role == role_name).count()
        except Exception:
            return 0
        finally:
            db.close()

    @classmethod
    def get_role_users(cls, role_name: str) -> list:
        """«full name (username)» of the users that have this role."""
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            users = db.query(User).filter(User.role == role_name).order_by(User.full_name).all()
            return [f"{u.full_name or u.username} ({u.username})" for u in users]
        except Exception:
            return []
        finally:
            db.close()

    @classmethod
    def delete_role(cls, role_name: str, move_users_to: str = None):
        """
        Delete a custom role.  Its users move to `move_users_to`, which must be
        given when the role still has users (they were silently moved to
        «تکنسین» before, which could give them MORE rights than they had).
        """
        from database.db import SessionLocal
        if cls.is_builtin_role(role_name):
            return False, "نقش‌های پیش‌فرض قابل حذف نیستند."
        db = SessionLocal()
        try:
            n_users = db.query(User).filter(User.role == role_name).count()
            if n_users:
                if not move_users_to or move_users_to == role_name:
                    return False, "برای کاربران این نقش، نقش جایگزین را انتخاب کنید."
                known = {r["name"] for r in cls.get_role_list()}
                if move_users_to not in known:
                    return False, f"نقش جایگزین «{move_users_to}» وجود ندارد."
                db.query(User).filter(User.role == role_name).update(
                    {User.role: move_users_to}, synchronize_session=False)
            db.query(RolePermissions).filter(RolePermissions.role_name == role_name).delete()
            db.commit()
            detail = f"{n_users} کاربر به نقش «{move_users_to}» منتقل شدند." if n_users else "بدون کاربر"
            cls._log("DELETE", role_name, detail)
            if n_users:
                return True, f"نقش حذف شد و {n_users} کاربر آن به نقش «{move_users_to}» منتقل شدند."
            return True, "نقش حذف شد."
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    # ── activity log / text helpers ─────────────────────────────────────
    @classmethod
    def describe_permissions(cls, permissions: dict) -> str:
        """Short text: «تجهیزات: مشاهده، ایجاد / ویرایش؛ …» (for the activity log)."""
        labels = dict(PERMISSION_ACTIONS)
        parts = []
        for module, label in PERMISSION_MODULES:
            acts = [labels[a] for a in ALL_ACTIONS if (permissions.get(module) or {}).get(a)]
            if acts:
                parts.append(f"{label}: {'، '.join(acts)}")
        return "؛ ".join(parts) or "بدون دسترسی"

    @staticmethod
    def _log(action: str, role_name: str, details: str = ""):
        try:
            from utils.logger import log_action
            log_action(action, "role", 0, f"{role_name}: {details}"[:1000])
        except Exception as exc:
            print("role log:", exc)

# utils/logger.py
from database.activity_log_repository import ActivityLogRepository
from database.db import SessionLocal
from auth.auth_manager import AuthManager

_repo = None

def _get_repo():
    global _repo
    if _repo is None:
        _repo = ActivityLogRepository(SessionLocal)
    return _repo

def log_action(action: str, entity_type: str, entity_id: int = None, details: str = None, user_id: int = None, username: str = None):
    """Log an action to the database. If user_id/username not provided, take from current logged-in user."""
    try:
        if user_id is None or username is None:
            current_user = AuthManager.get_current_user()
            if current_user:
                user_id = current_user.id
                username = current_user.username
            else:
                # Fallback to system if no user logged in (e.g., during initial setup)
                user_id = 0
                username = "system"
        repo = _get_repo()
        repo.log(
            user_id=user_id,
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=None
        )
    except Exception as e:
        print(f"Logging error: {e}")
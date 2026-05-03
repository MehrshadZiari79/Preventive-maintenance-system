# utils/logger.py
from database.activity_log_repository import ActivityLogRepository
from auth.auth_manager import AuthManager
import socket

_repo = ActivityLogRepository()

def log_action(action: str, entity_type: str, entity_id: int = None, details: str = None):
    user = AuthManager.get_current_user()
    if not user:
        return
    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
    except:
        ip_address = None
    _repo.log(
        user_id=user.id,
        username=user.username,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address
    )
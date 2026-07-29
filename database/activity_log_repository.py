# database/activity_log_repository.py
from database.models import ActivityLog


class ActivityLogRepository:
    def __init__(self, session_factory):
        self.Session = session_factory

    def log(self, user_id: int, username: str, action: str, entity_type: str,
            entity_id: int = None, details: str = None, ip_address: str = None):
        session = self.Session()
        try:
            log = ActivityLog(
                user_id=user_id,
                username=username,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
                ip_address=ip_address
            )
            session.add(log)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Activity log error: {e}")
        finally:
            session.close()

    def get_logs(self, limit=100, offset=0, user_id=None, entity_type=None):
        session = self.Session()
        try:
            query = session.query(ActivityLog).order_by(ActivityLog.created_at.desc())
            if user_id:
                query = query.filter(ActivityLog.user_id == user_id)
            if entity_type:
                query = query.filter(ActivityLog.entity_type == entity_type)
            return query.offset(offset).limit(limit).all()
        finally:
            session.close()
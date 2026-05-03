# database/activity_log_repository.py
from database.db import SessionLocal
from database.models import ActivityLog


class ActivityLogRepository:
    def log(self, user_id: int, username: str, action: str, entity_type: str,
            entity_id: int = None, details: str = None, ip_address: str = None):
        db = SessionLocal()
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
            db.add(log)
            db.commit()
        except Exception as e:
            print(f"Activity log error: {e}")
            db.rollback()
        finally:
            db.close()

    def get_logs(self, limit=100, offset=0, user_id=None, entity_type=None):
        db = SessionLocal()
        try:
            query = db.query(ActivityLog).order_by(ActivityLog.created_at.desc())
            if user_id:
                query = query.filter(ActivityLog.user_id == user_id)
            if entity_type:
                query = query.filter(ActivityLog.entity_type == entity_type)
            return query.offset(offset).limit(limit).all()
        finally:
            db.close()
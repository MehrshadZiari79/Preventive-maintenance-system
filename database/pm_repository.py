"""
PM Schedule Repository - Data Access Layer for Preventive Maintenance Scheduling
"""
from typing import Optional
from datetime import datetime, timedelta
from database.db import SessionLocal
from database.models import PMSchedule, Equipment, User, PMFrequency


FREQUENCY_DAYS = {
    PMFrequency.DAILY.value: 1,
    PMFrequency.WEEKLY.value: 7,
    PMFrequency.MONTHLY.value: 30,
    PMFrequency.QUARTERLY.value: 90,
    PMFrequency.BIANNUAL.value: 180,
    PMFrequency.ANNUAL.value: 365,
    PMFrequency.CUSTOM.value: None,
}


class PMRepository:
    def __init__(self):
        pass

    def _session(self):
        return SessionLocal()

    # ─────────────────────────── READ ───────────────────────────

    def get_all(self) -> list[dict]:
        with self._session() as session:
            schedules = (
                session.query(PMSchedule)
                .join(Equipment, PMSchedule.equipment_id == Equipment.id)
                .order_by(PMSchedule.next_due)
                .all()
            )
            return [self._to_dict(s) for s in schedules]

    def get_by_id(self, schedule_id: int) -> Optional[dict]:
        with self._session() as session:
            s = session.query(PMSchedule).filter(PMSchedule.id == schedule_id).first()
            return self._to_dict(s) if s else None

    def get_by_equipment(self, equipment_id: int) -> list[dict]:
        with self._session() as session:
            schedules = session.query(PMSchedule).filter(
                PMSchedule.equipment_id == equipment_id
            ).order_by(PMSchedule.next_due).all()
            return [self._to_dict(s) for s in schedules]

    def get_overdue(self) -> list[dict]:
        with self._session() as session:
            now = datetime.utcnow()
            schedules = session.query(PMSchedule).filter(
                PMSchedule.next_due <= now,
                PMSchedule.is_active == True
            ).order_by(PMSchedule.next_due).all()
            return [self._to_dict(s) for s in schedules]

    def get_upcoming(self, days: int = 7) -> list[dict]:
        with self._session() as session:
            now = datetime.utcnow()
            future = now + timedelta(days=days)
            schedules = session.query(PMSchedule).filter(
                PMSchedule.next_due >= now,
                PMSchedule.next_due <= future,
                PMSchedule.is_active == True
            ).order_by(PMSchedule.next_due).all()
            return [self._to_dict(s) for s in schedules]

    def get_stats(self) -> dict:
        with self._session() as session:
            now = datetime.utcnow()
            total = session.query(PMSchedule).filter(PMSchedule.is_active == True).count()
            overdue = session.query(PMSchedule).filter(
                PMSchedule.next_due <= now,
                PMSchedule.is_active == True
            ).count()
            upcoming = session.query(PMSchedule).filter(
                PMSchedule.next_due > now,
                PMSchedule.next_due <= now + timedelta(days=7),
                PMSchedule.is_active == True
            ).count()
            return {"total": total, "overdue": overdue, "upcoming": upcoming}

    # ─────────────────────────── WRITE ──────────────────────────

    def create(self, title: str, equipment_id: int, technician_id: Optional[int],
               frequency: str, interval_days: int, start_date: datetime,
               checklist: str, estimated_duration: Optional[int],
               notes: str) -> tuple[bool, str]:
        try:
            next_due = start_date + timedelta(days=interval_days)
            with self._session() as session:
                schedule = PMSchedule(
                    title=title,
                    equipment_id=equipment_id,
                    technician_id=technician_id or None,
                    frequency=frequency,
                    interval_days=interval_days,
                    last_done=None,
                    next_due=next_due,
                    checklist=checklist or None,
                    estimated_duration=estimated_duration or None,
                    is_active=True,
                    notes=notes or None,
                )
                session.add(schedule)
                session.commit()
            return True, "برنامه PM با موفقیت ثبت شد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    def update(self, schedule_id: int, title: str, equipment_id: int,
               technician_id: Optional[int], frequency: str, interval_days: int,
               next_due: datetime, checklist: str,
               estimated_duration: Optional[int], notes: str) -> tuple[bool, str]:
        try:
            with self._session() as session:
                s = session.query(PMSchedule).filter(PMSchedule.id == schedule_id).first()
                if not s:
                    return False, "برنامه یافت نشد."
                s.title = title
                s.equipment_id = equipment_id
                s.technician_id = technician_id or None
                s.frequency = frequency
                s.interval_days = interval_days
                s.next_due = next_due
                s.checklist = checklist or None
                s.estimated_duration = estimated_duration or None
                s.notes = notes or None
                s.updated_at = datetime.utcnow()
                session.commit()
            return True, "برنامه PM بروزرسانی شد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    def mark_done(self, schedule_id: int, done_date: datetime) -> tuple[bool, str]:
        """ثبت انجام PM و محاسبه تاریخ بعدی"""
        try:
            with self._session() as session:
                s = session.query(PMSchedule).filter(PMSchedule.id == schedule_id).first()
                if not s:
                    return False, "برنامه یافت نشد."
                s.last_done = done_date
                s.next_due = done_date + timedelta(days=s.interval_days)
                s.updated_at = datetime.utcnow()
                session.commit()
            return True, "PM انجام شده ثبت شد و تاریخ بعدی محاسبه گردید."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    def toggle_active(self, schedule_id: int) -> tuple[bool, str]:
        try:
            with self._session() as session:
                s = session.query(PMSchedule).filter(PMSchedule.id == schedule_id).first()
                if not s:
                    return False, "برنامه یافت نشد."
                s.is_active = not s.is_active
                s.updated_at = datetime.utcnow()
                session.commit()
                state = "فعال" if s.is_active else "غیرفعال"
            return True, f"برنامه {state} شد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    def delete(self, schedule_id: int) -> tuple[bool, str]:
        try:
            with self._session() as session:
                s = session.query(PMSchedule).filter(PMSchedule.id == schedule_id).first()
                if not s:
                    return False, "برنامه یافت نشد."
                session.delete(s)
                session.commit()
            return True, "برنامه PM حذف شد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    # ─────────────────────────── HELPER ─────────────────────────

    @staticmethod
    def _to_dict(s: PMSchedule) -> dict:
        now = datetime.utcnow()
        is_overdue = (
            s.next_due is not None and
            s.next_due <= now and
            s.is_active
        )
        days_until = None
        if s.next_due:
            delta = (s.next_due - now).days
            days_until = delta

        return {
            "id": s.id,
            "title": s.title,
            "equipment_id": s.equipment_id,
            "equipment_name": s.equipment.name if s.equipment else "",
            "equipment_code": s.equipment.code if s.equipment else "",
            "technician_id": s.technician_id,
            "technician_name": s.technician.full_name if s.technician else "تعیین نشده",
            "frequency": s.frequency,
            "interval_days": s.interval_days,
            "last_done": s.last_done.strftime("%Y-%m-%d") if s.last_done else "انجام نشده",
            "next_due": s.next_due.strftime("%Y-%m-%d") if s.next_due else "",
            "next_due_dt": s.next_due,
            "checklist": s.checklist or "",
            "estimated_duration": s.estimated_duration or 0,
            "is_active": s.is_active,
            "is_overdue": is_overdue,
            "days_until": days_until,
            "notes": s.notes or "",
            "created_at": s.created_at.strftime("%Y-%m-%d") if s.created_at else "",
        }

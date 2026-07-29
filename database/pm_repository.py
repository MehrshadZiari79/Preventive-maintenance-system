# database/pm_repository.py
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case, and_
from database.models import PMSchedule, PMFrequency
from database.work_order import WorkOrder
from utils.logger import log_action


class PMRepository:
    def __init__(self, session_factory):
        self.Session = session_factory

    def update_after_completion(self, schedule_id: int, completion_date: datetime):
        session = self.Session()
        try:
            schedule = session.query(PMSchedule).filter(PMSchedule.id == schedule_id).first()
            if not schedule:
                raise ValueError(f"PM Schedule {schedule_id} not found")
            schedule.last_done = completion_date
            schedule.next_due = completion_date + timedelta(days=schedule.interval_days)
            session.commit()
            return self._to_dict(schedule)
        finally:
            session.close()

    def get_all(self) -> list[dict]:
        session = self.Session()
        try:
            schedules = (
                session.query(PMSchedule)
                .options(
                    joinedload(PMSchedule.equipment),
                    joinedload(PMSchedule.technician),
                )
                .order_by(PMSchedule.next_due)
                .all()
            )
            return [self._to_dict(s) for s in schedules]
        finally:
            session.close()

    def get_by_id(self, schedule_id: int) -> Optional[dict]:
        session = self.Session()
        try:
            s = (
                session.query(PMSchedule)
                .options(
                    joinedload(PMSchedule.equipment),
                    joinedload(PMSchedule.technician),
                )
                .filter(PMSchedule.id == schedule_id)
                .first()
            )
            return self._to_dict(s) if s else None
        finally:
            session.close()

    def get_by_equipment(self, equipment_id: int) -> list[dict]:
        session = self.Session()
        try:
            schedules = (
                session.query(PMSchedule)
                .options(
                    joinedload(PMSchedule.equipment),
                    joinedload(PMSchedule.technician),
                )
                .filter(PMSchedule.equipment_id == equipment_id)
                .order_by(PMSchedule.next_due)
                .all()
            )
            return [self._to_dict(s) for s in schedules]
        finally:
            session.close()

    def get_overdue(self) -> list[dict]:
        session = self.Session()
        try:
            now = datetime.utcnow()
            schedules = (
                session.query(PMSchedule)
                .options(
                    joinedload(PMSchedule.equipment),
                    joinedload(PMSchedule.technician),
                )
                .filter(
                    PMSchedule.next_due <= now,
                    PMSchedule.is_active == True,
                )
                .order_by(PMSchedule.next_due)
                .all()
            )
            return [self._to_dict(s) for s in schedules]
        finally:
            session.close()

    def get_upcoming(self, days: int = 7) -> list[dict]:
        session = self.Session()
        try:
            now = datetime.utcnow()
            future = now + timedelta(days=days)
            schedules = (
                session.query(PMSchedule)
                .options(
                    joinedload(PMSchedule.equipment),
                    joinedload(PMSchedule.technician),
                )
                .filter(
                    PMSchedule.next_due >= now,
                    PMSchedule.next_due <= future,
                    PMSchedule.is_active == True,
                )
                .order_by(PMSchedule.next_due)
                .all()
            )
            return [self._to_dict(s) for s in schedules]
        finally:
            session.close()

    def get_stats(self) -> dict:
        session = self.Session()
        try:
            now = datetime.utcnow()
            row = session.query(
                func.sum(case([(PMSchedule.is_active == True, 1)], else_=0)).label("total"),
                func.sum(case([
                    (and_(
                        PMSchedule.is_active == True,
                        PMSchedule.next_due <= now
                    ), 1)
                ], else_=0)).label("overdue"),
                func.sum(case([
                    (and_(
                        PMSchedule.is_active == True,
                        PMSchedule.next_due > now,
                        PMSchedule.next_due <= now + timedelta(days=7)
                    ), 1)
                ], else_=0)).label("upcoming"),
            ).one()
            return {
                "total":    row.total    or 0,
                "overdue":  row.overdue  or 0,
                "upcoming": row.upcoming or 0,
            }
        finally:
            session.close()

    def create(self, title: str, equipment_id: int, technician_id: Optional[int],
               frequency: str, interval_days: int, start_date: datetime,
               checklist: str, estimated_duration: Optional[int],
               notes: str, parts_required: Optional[str] = None) -> tuple[bool, str]:
        if self.duplicate_pm_exists(equipment_id, title, frequency):
            return False, "یک برنامه PM مشابه برای این تجهیز و دوره تناوب وجود دارد."
        session = self.Session()
        try:
            # The start date IS the first due date
            next_due = start_date
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
                parts_required=parts_required or None,
            )
            session.add(schedule)
            session.commit()
            log_action("CREATE", "pm_schedule", schedule.id, f"عنوان: {title}")
            return True, "برنامه PM با موفقیت ثبت شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def update(self, schedule_id: int, title: str, equipment_id: int,
               technician_id: Optional[int], frequency: str, interval_days: int,
               next_due: datetime, checklist: str,
               estimated_duration: Optional[int], notes: str,
               parts_required: Optional[str] = None) -> tuple[bool, str]:
        if self.duplicate_pm_exists(equipment_id, title, frequency, exclude_id=schedule_id):
            return False, "یک برنامه PM دیگر با همین عنوان و دوره برای این تجهیز وجود دارد."
        session = self.Session()
        try:
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
            s.parts_required = parts_required or None
            s.updated_at = datetime.utcnow()
            session.commit()
            log_action("UPDATE", "pm_schedule", schedule_id, f"عنوان: {title}")
            return True, "برنامه PM بروزرسانی شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def mark_done(self, schedule_id: int, done_date: datetime) -> tuple[bool, str]:
        session = self.Session()
        try:
            s = session.query(PMSchedule).filter(PMSchedule.id == schedule_id).first()
            if not s:
                return False, "برنامه یافت نشد."
            s.last_done = done_date
            s.next_due = done_date + timedelta(days=s.interval_days)
            s.updated_at = datetime.utcnow()
            session.commit()
            log_action("MARK_DONE", "pm_schedule", schedule_id, f"done date: {done_date}")
            return True, "PM انجام شده ثبت شد و تاریخ بعدی محاسبه گردید."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def toggle_active(self, schedule_id: int) -> tuple[bool, str]:
        session = self.Session()
        try:
            s = session.query(PMSchedule).filter(PMSchedule.id == schedule_id).first()
            if not s:
                return False, "برنامه یافت نشد."
            s.is_active = not s.is_active
            s.updated_at = datetime.utcnow()
            session.commit()
            state = "فعال" if s.is_active else "غیرفعال"
            log_action("TOGGLE", "pm_schedule", schedule_id, f"active: {s.is_active}")
            return True, f"برنامه {state} شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def delete(self, schedule_id: int) -> tuple[bool, str]:
        """
        Delete a PM schedule safely:
          - Set schedule_id to NULL in any related WorkOrders
          - Then delete the schedule
        """
        session = self.Session()
        try:
            s = session.query(PMSchedule).filter(PMSchedule.id == schedule_id).first()
            if not s:
                return False, "برنامه یافت نشد."

            # Nullify schedule_id in WorkOrders that reference this schedule
            session.query(WorkOrder).filter(
                WorkOrder.schedule_id == schedule_id
            ).update({WorkOrder.schedule_id: None}, synchronize_session=False)

            session.delete(s)
            session.commit()
            log_action("DELETE", "pm_schedule", schedule_id, "")
            return True, "برنامه PM و تمام ارتباطات آن با موفقیت حذف شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def duplicate_pm_exists(self, equipment_id: int, title: str, frequency: str, exclude_id: int = None) -> bool:
        session = self.Session()
        try:
            query = session.query(PMSchedule).filter(
                PMSchedule.equipment_id == equipment_id,
                PMSchedule.title == title,
                PMSchedule.frequency == frequency
            )
            if exclude_id:
                query = query.filter(PMSchedule.id != exclude_id)
            return query.first() is not None
        finally:
            session.close()

    @staticmethod
    def _to_dict(s: PMSchedule) -> dict:
        now = datetime.utcnow()
        is_overdue = s.next_due is not None and s.next_due <= now and s.is_active
        # Use date-only comparison to avoid showing 0 days when the due date
        # is tomorrow but the current time is late today.
        days_until = (s.next_due.date() - now.date()).days if s.next_due else None
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
            "parts_required": s.parts_required or "",
            "created_at": s.created_at.strftime("%Y-%m-%d") if s.created_at else "",
        }

    def get_due_schedules(self, target_date: datetime) -> list:
        session = self.Session()
        try:
            return session.query(PMSchedule).filter(
                PMSchedule.is_active == True,
                PMSchedule.next_due <= target_date
            ).all()
        finally:
            session.close()

    def get_due_schedules_ahead(self, target_date: datetime, days_ahead: int = 1) -> list:
        """Return active schedules where next_due <= target_date + days_ahead."""
        session = self.Session()
        try:
            cutoff = target_date + timedelta(days=days_ahead)
            return session.query(PMSchedule).filter(
                PMSchedule.is_active == True,
                PMSchedule.next_due <= cutoff
            ).all()
        finally:
            session.close()

    def update_next_due_date(self, pm_id: int, completion_date: datetime) -> tuple[bool, str]:
        session = self.Session()
        try:
            s = session.query(PMSchedule).filter(PMSchedule.id == pm_id).first()
            if not s:
                return False, "PM schedule not found."
            s.last_done = completion_date
            s.next_due = completion_date + timedelta(days=s.interval_days)
            session.commit()
            return True, "Next due date updated."
        except Exception as e:
            session.rollback()
            return False, f"Error: {e}"
        finally:
            session.close()

    def get_upcoming_pms(self, days=7):
        session = self.Session()
        try:
            now = datetime.now()
            future = now + timedelta(days=days)
            return session.query(PMSchedule).filter(
                PMSchedule.is_active == True,
                PMSchedule.next_due >= now,
                PMSchedule.next_due <= future
            ).order_by(PMSchedule.next_due).all()
        finally:
            session.close()

    def get_upcoming_pms_dict(self, days=7):
        session = self.Session()
        try:
            now = datetime.now()
            future = now + timedelta(days=days)
            pms = session.query(PMSchedule).options(
                joinedload(PMSchedule.equipment)
            ).filter(
                PMSchedule.is_active == True,
                PMSchedule.next_due >= now,
                PMSchedule.next_due <= future
            ).order_by(PMSchedule.next_due).all()
            return [self._to_dict(pm) for pm in pms]
        finally:
            session.close()

    def get_overdue_count(self) -> int:
        session = self.Session()
        try:
            return session.query(PMSchedule).filter(
                PMSchedule.is_active == True,
                PMSchedule.next_due < datetime.now()
            ).count()
        finally:
            session.close()
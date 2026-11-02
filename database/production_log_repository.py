# database/production_log_repository.py
"""
Machine-hours (production_logs) data access.

Backward compatible: every existing call (add_log / update_log / get_logs /
get_log / delete_log) keeps working with the same positional arguments.
New optional arguments:
    * downtime_hours  - stored in the existing production_logs.downtime_hours
                        column (no schema change)
    * log_date        - update_log can now move a record to another date
No table, column or index is created or altered.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import and_

from database.models import ProductionLog


def _day_start(value):
    """date/datetime -> datetime at 00:00 (production_logs.log_date is DATETIME)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return datetime.combine(value.date(), time())
    if isinstance(value, date):
        return datetime.combine(value, time())
    raise TypeError("log_date must be a date or datetime")


class ProductionLogRepository:
    def __init__(self, session_factory):
        self.Session = session_factory

    # ------------------------------------------------------------------ read

    def get_logs(self, equipment_id=None, start_date=None, end_date=None):
        session = self.Session()
        try:
            query = session.query(ProductionLog)
            if equipment_id:
                query = query.filter(ProductionLog.equipment_id == equipment_id)
            if start_date:
                query = query.filter(ProductionLog.log_date >= _day_start(start_date))
            if end_date:
                # Inclusive end DAY: records stored with a time component on the
                # last day were previously dropped by "<= end_date".
                query = query.filter(
                    ProductionLog.log_date < _day_start(end_date) + timedelta(days=1)
                )
            return query.order_by(ProductionLog.log_date.desc()).all()
        finally:
            session.close()

    def get_log(self, log_id):
        session = self.Session()
        try:
            return session.query(ProductionLog).get(log_id)
        finally:
            session.close()

    def find_log_for_day(self, equipment_id, log_date, exclude_id=None):
        """Return the record of this equipment on that calendar day, if any."""
        session = self.Session()
        try:
            start = _day_start(log_date)
            query = session.query(ProductionLog).filter(
                and_(
                    ProductionLog.equipment_id == equipment_id,
                    ProductionLog.log_date >= start,
                    ProductionLog.log_date < start + timedelta(days=1),
                )
            )
            if exclude_id is not None:
                query = query.filter(ProductionLog.id != exclude_id)
            return query.first()
        finally:
            session.close()

    # ----------------------------------------------------------------- write

    def add_log(self, equipment_id, log_date, planned_hours, operating_hours,
                output_units=0, downtime_hours=None):
        """
        Insert a record; if the equipment already has a record on that day the
        existing record is updated (original behaviour).  The UI now asks the
        user before calling this for an existing day.
        """
        session = self.Session()
        try:
            start = _day_start(log_date)
            existing = session.query(ProductionLog).filter(
                and_(
                    ProductionLog.equipment_id == equipment_id,
                    ProductionLog.log_date >= start,
                    ProductionLog.log_date < start + timedelta(days=1),
                )
            ).first()
            if existing:
                existing.planned_hours = planned_hours
                existing.operating_hours = operating_hours
                existing.output_units = output_units
                if downtime_hours is not None:
                    existing.downtime_hours = downtime_hours
                message = "رکورد این روز بروزرسانی شد."
            else:
                session.add(ProductionLog(
                    equipment_id=equipment_id,
                    log_date=start,
                    planned_hours=planned_hours,
                    operating_hours=operating_hours,
                    downtime_hours=downtime_hours or 0,
                    output_units=output_units,
                ))
                message = "ثبت شد."
            session.commit()
            return True, message
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def update_log(self, log_id, planned_hours, operating_hours, output_units,
                   downtime_hours=None, log_date=None):
        session = self.Session()
        try:
            log = session.query(ProductionLog).get(log_id)
            if not log:
                return False, "رکورد یافت نشد."

            if log_date is not None:
                start = _day_start(log_date)
                clash = session.query(ProductionLog).filter(
                    and_(
                        ProductionLog.equipment_id == log.equipment_id,
                        ProductionLog.log_date >= start,
                        ProductionLog.log_date < start + timedelta(days=1),
                        ProductionLog.id != log.id,
                    )
                ).first()
                if clash:
                    return False, "برای این تجهیز در تاریخ انتخاب‌شده رکورد دیگری وجود دارد."
                log.log_date = start

            log.planned_hours = planned_hours
            log.operating_hours = operating_hours
            log.output_units = output_units
            if downtime_hours is not None:
                log.downtime_hours = downtime_hours
            session.commit()
            return True, "بروزرسانی شد."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def delete_log(self, log_id):
        session = self.Session()
        try:
            log = session.query(ProductionLog).get(log_id)
            if not log:
                return False, "رکورد یافت نشد."
            session.delete(log)
            session.commit()
            return True, "حذف شد."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

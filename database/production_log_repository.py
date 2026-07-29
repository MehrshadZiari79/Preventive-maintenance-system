# database/production_log_repository.py
from sqlalchemy import and_
from database.models import ProductionLog
from datetime import datetime

class ProductionLogRepository:
    def __init__(self, session_factory):
        self.Session = session_factory

    def get_logs(self, equipment_id=None, start_date=None, end_date=None):
        session = self.Session()
        try:
            query = session.query(ProductionLog)
            if equipment_id:
                query = query.filter(ProductionLog.equipment_id == equipment_id)
            if start_date:
                query = query.filter(ProductionLog.log_date >= start_date)
            if end_date:
                query = query.filter(ProductionLog.log_date <= end_date)
            return query.order_by(ProductionLog.log_date.desc()).all()
        finally:
            session.close()

    def get_log(self, log_id):
        session = self.Session()
        try:
            return session.query(ProductionLog).get(log_id)
        finally:
            session.close()

    def add_log(self, equipment_id, log_date, planned_hours, operating_hours, output_units=0):
        session = self.Session()
        try:
            # Check for existing log on this date and equipment
            existing = session.query(ProductionLog).filter(
                and_(ProductionLog.equipment_id == equipment_id,
                     ProductionLog.log_date == log_date)
            ).first()
            if existing:
                # Update existing
                existing.planned_hours = planned_hours
                existing.operating_hours = operating_hours
                existing.output_units = output_units
            else:
                log = ProductionLog(
                    equipment_id=equipment_id,
                    log_date=log_date,
                    planned_hours=planned_hours,
                    operating_hours=operating_hours,
                    output_units=output_units
                )
                session.add(log)
            session.commit()
            return True, "ثبت شد."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def update_log(self, log_id, planned_hours, operating_hours, output_units):
        session = self.Session()
        try:
            log = session.query(ProductionLog).get(log_id)
            if not log:
                return False, "رکورد یافت نشد."
            log.planned_hours = planned_hours
            log.operating_hours = operating_hours
            log.output_units = output_units
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
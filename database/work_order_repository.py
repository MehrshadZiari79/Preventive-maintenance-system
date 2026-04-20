from sqlalchemy.orm import joinedload
from datetime import datetime
from typing import List, Optional
from database.db import SessionLocal
from database.work_order import WorkOrder, WorkOrderStatus, WorkOrderType, WorkOrderPriority


class WorkOrderRepository:

    def create_work_order(self, title, equipment_id, type_str, priority,
                          technician_id=None, scheduled_date=None,
                          description=None, parts_used=None, schedule_id=None):
        db = SessionLocal()
        try:
            wo_type = (WorkOrderType[type_str.upper()]
                       if type_str.upper() in WorkOrderType.__members__
                       else WorkOrderType.CORRECTIVE)

            wo_priority = (WorkOrderPriority[priority.upper()]
                           if priority and priority.upper() in WorkOrderPriority.__members__
                           else WorkOrderPriority.MEDIUM)

            wo = WorkOrder(
                equipment_id=equipment_id,
                schedule_id=schedule_id,
                type=wo_type,
                priority=wo_priority,
                technician_id=technician_id,
                title=title,
                description=description or None,
                parts_used=parts_used or None,
                scheduled_date=scheduled_date,
                status=WorkOrderStatus.PENDING,
            )
            db.add(wo)
            db.commit()
            return True, "کار با موفقیت ثبت شد."
        except Exception as e:
            db.rollback()
            return False, f"خطا: {str(e)}"
        finally:
            db.close()

    def update_work_order(self, work_order_id, title, equipment_id, type_str,
                          priority, technician_id=None, scheduled_date=None,
                          description=None, parts_used=None):
        db = SessionLocal()
        try:
            wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "دستور کار یافت نشد."

            wo_type = (WorkOrderType[type_str.upper()]
                       if type_str.upper() in WorkOrderType.__members__
                       else WorkOrderType.CORRECTIVE)

            wo_priority = (WorkOrderPriority[priority.upper()]
                           if priority and priority.upper() in WorkOrderPriority.__members__
                           else WorkOrderPriority.MEDIUM)

            wo.title = title
            wo.equipment_id = equipment_id
            wo.type = wo_type
            wo.priority = wo_priority
            wo.technician_id = technician_id
            wo.scheduled_date = scheduled_date
            wo.description = description or None
            wo.parts_used = parts_used or None
            db.commit()
            return True, "دستور کار ویرایش شد."
        except Exception as e:
            db.rollback()
            return False, f"خطا: {str(e)}"
        finally:
            db.close()

    def get_all(self, status_filter=None, type_filter=None):
        db = SessionLocal()
        try:
            query = db.query(WorkOrder).options(
                joinedload(WorkOrder.equipment),
                joinedload(WorkOrder.technician),
                joinedload(WorkOrder.supervisor)
            )
            if status_filter:
                query = query.filter(WorkOrder.status == status_filter)
            if type_filter:
                query = query.filter(WorkOrder.type == type_filter)

            results = query.order_by(WorkOrder.created_at.desc()).all()
            db.expunge_all()
            return results
        finally:
            db.close()

    def get_by_id(self, work_order_id):
        db = SessionLocal()
        try:
            wo = db.query(WorkOrder).options(
                joinedload(WorkOrder.equipment),
                joinedload(WorkOrder.technician),
                joinedload(WorkOrder.supervisor)
            ).filter(WorkOrder.id == work_order_id).first()
            if wo:
                db.expunge(wo)
            return wo
        finally:
            db.close()

    def start_work(self, work_order_id):
        db = SessionLocal()
        try:
            wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."
            wo.status = WorkOrderStatus.IN_PROGRESS
            wo.start_time = datetime.utcnow()
            db.commit()
            return True, "کار شروع شد."
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    def complete_work(self, work_order_id, description=None, parts_used=None):
        db = SessionLocal()
        try:
            wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."

            wo.status = WorkOrderStatus.COMPLETED
            wo.completed_at = datetime.now()
            wo.completion_notes = description
            wo.parts_used = parts_used

            # Update PM schedule if this is a preventive work order
            if wo.schedule_id:
                from database.pm_repository import PMRepository
                pm_repo = PMRepository()
                pm_repo.update_after_completion(wo.schedule_id, wo.completed_at)

            db.commit()
            return True, "کار تکمیل شد."
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    def approve(self, work_order_id, supervisor_id, notes=None):
        db = SessionLocal()
        try:
            wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."
            wo.status = WorkOrderStatus.APPROVED
            wo.supervisor_id = supervisor_id
            wo.supervisor_notes = notes
            db.commit()
            return True, "کار تایید شد."
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    def reject(self, work_order_id, supervisor_id, notes):
        db = SessionLocal()
        try:
            wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."
            wo.status = WorkOrderStatus.REJECTED
            wo.supervisor_id = supervisor_id
            wo.supervisor_notes = notes
            db.commit()
            return True, "کار رد شد."
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    def delete(self, work_order_id):
        db = SessionLocal()
        try:
            wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."
            db.delete(wo)
            db.commit()
            return True, "کار حذف شد."
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    def find_by_schedule_and_date(self, pm_schedule_id: int, scheduled_date: datetime) -> Optional[dict]:
        """Check if work order already exists for this PM schedule and date."""
        db = SessionLocal()
        try:
            wo = db.query(WorkOrder).filter(
                WorkOrder.schedule_id == pm_schedule_id,
                WorkOrder.scheduled_date == scheduled_date
            ).first()

            if wo:
                return {
                    'id': wo.id,
                    'title': wo.title,
                    'status': wo.status.value
                }
            return None
        finally:
            db.close()

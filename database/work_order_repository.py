# database/work_order_repository.py
from sqlalchemy.orm import joinedload
from datetime import datetime
from typing import List, Optional
from database.db import SessionLocal
from database.work_order import WorkOrder, WorkOrderStatus, WorkOrderType, WorkOrderPriority


class WorkOrderRepository:

    def create_work_order(self, title, equipment_id, type_str, priority,
                          technician_id=None, scheduled_date=None,
                          description=None, parts_used=None, schedule_id=None,
                          operator_id=None, failure_report_time=None,
                          operator_notes=None, operator_signature=None,
                          manual_cost=0.0, cost_description=None):
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
                operator_id=operator_id,
                failure_report_time=failure_report_time,
                operator_notes=operator_notes,
                operator_signature=operator_signature,
                title=title,
                description=description or None,
                parts_used=parts_used or None,
                scheduled_date=scheduled_date,
                status=WorkOrderStatus.PENDING,
                manual_cost=manual_cost,
                cost_description=cost_description,
            )
            db.add(wo)
            db.commit()
            db.refresh(wo)
            return True, "کار با موفقیت ثبت شد."
        except Exception as e:
            db.rollback()
            return False, f"خطا: {str(e)}"
        finally:
            db.close()

    def update_work_order(self, work_order_id, title, equipment_id, type_str,
                          priority, technician_id=None, scheduled_date=None,
                          description=None, parts_used=None,
                          operator_id=None, failure_report_time=None,
                          operator_notes=None, operator_signature=None,
                          manual_cost=None, cost_description=None):
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
            wo.operator_id = operator_id
            wo.failure_report_time = failure_report_time
            wo.operator_notes = operator_notes
            wo.operator_signature = operator_signature
            wo.scheduled_date = scheduled_date
            wo.description = description or None
            wo.parts_used = parts_used or None
            if manual_cost is not None:
                wo.manual_cost = manual_cost
            if cost_description is not None:
                wo.cost_description = cost_description
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
                joinedload(WorkOrder.supervisor),
                joinedload(WorkOrder.operator)
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
                joinedload(WorkOrder.supervisor),
                joinedload(WorkOrder.operator)
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

    def deduct_spare_parts(self, work_order_id: int, parts_list: list) -> tuple[bool, str, list]:
        from database.spare_parts_repository import SparePartsRepository
        db = SessionLocal()
        low_stock_parts = []
        try:
            for item in parts_list:
                part_id = item['part_id']
                qty = item['quantity']
                sp_repo = SparePartsRepository(db)
                part = sp_repo.get_by_id(part_id)
                if not part:
                    return False, f"قطعه با ID {part_id} یافت نشد.", []
                if part.current_stock < qty:
                    return False, f"موجودی قطعه {part.part_number} کافی نیست. موجودی: {part.current_stock}", []
                part.current_stock -= qty
                sp_repo.add_transaction({
                    'part_id': part_id,
                    'transaction_type': 'OUT',
                    'quantity': qty,
                    'reference': f"WO-{work_order_id}",
                    'notes': f"مصرف در دستور کار {work_order_id}"
                })
                if part.current_stock <= part.min_stock:
                    low_stock_parts.append(part.part_number)
            db.commit()
            return True, "قطعات با موفقیت کسر شدند.", low_stock_parts
        except Exception as e:
            db.rollback()
            return False, f"خطا در کسر قطعات: {str(e)}", []
        finally:
            db.close()

    def complete_work(self, work_order_id, description=None, parts_used=None, used_parts_list=None,
                      manual_cost=None, cost_description=None):
        db = SessionLocal()
        try:
            wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."

            low_stock = []
            if used_parts_list:
                success, msg, low_stock = self.deduct_spare_parts(work_order_id, used_parts_list)
                if not success:
                    return False, msg

            wo.status = WorkOrderStatus.COMPLETED
            wo.end_time = datetime.now()
            wo.description = description or wo.description
            if parts_used:
                wo.parts_used = parts_used

            # Update manual cost fields if provided
            if manual_cost is not None:
                wo.manual_cost = manual_cost
            if cost_description is not None:
                wo.cost_description = cost_description

            if wo.schedule_id:
                from database.pm_repository import PMRepository
                pm_repo = PMRepository()
                pm_repo.update_after_completion(wo.schedule_id, wo.end_time)

            db.commit()
            msg = "کار تکمیل شد."
            if low_stock:
                msg += f"\n⚠️ هشدار: قطعات {', '.join(low_stock)} به حداقل موجودی رسیده‌اند."
            return True, msg
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    def approve(self, work_order_id, supervisor_id):
        db = SessionLocal()
        try:
            wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."
            wo.status = WorkOrderStatus.APPROVED
            wo.supervisor_id = supervisor_id
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
        db = SessionLocal()
        try:
            wo = db.query(WorkOrder).filter(
                WorkOrder.schedule_id == pm_schedule_id,
                WorkOrder.scheduled_date == scheduled_date
            ).first()
            if wo:
                return {'id': wo.id, 'title': wo.title, 'status': wo.status.value}
            return None
        finally:
            db.close()

    def create_from_pm(self, pm_schedule, due_date: datetime, created_by_user_id: int = None) -> tuple[bool, str]:
        db = SessionLocal()
        try:
            technician_id = pm_schedule.technician_id if pm_schedule.technician_id else None
            wo = WorkOrder(
                equipment_id=pm_schedule.equipment_id,
                schedule_id=pm_schedule.id,
                type=WorkOrderType.PREVENTIVE,
                status=WorkOrderStatus.PENDING,
                priority=WorkOrderPriority.MEDIUM,
                technician_id=technician_id,
                title=f"[PM] {pm_schedule.title}",
                description=f"کار پیشگیرانه خودکار بر اساس برنامه PM: {pm_schedule.title}\n"
                            f"چک‌لیست: {pm_schedule.checklist or 'ندارد'}\n"
                            f"قطعات مورد نیاز: {pm_schedule.parts_required or 'ندارد'}",
                parts_used=None,
                scheduled_date=due_date,
                created_at=datetime.utcnow(),
                manual_cost=0.0,
                cost_description=None
            )
            db.add(wo)
            db.commit()
            db.refresh(wo)
            return True, "Work order created from PM schedule."
        except Exception as e:
            db.rollback()
            return False, f"Error: {e}"
        finally:
            db.close()
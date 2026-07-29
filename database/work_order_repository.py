# database/work_order_repository.py
import json
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import joinedload
from database.work_order import WorkOrder, WorkOrderStatus, WorkOrderType, WorkOrderPriority
from database.models import work_order_technicians
from utils.logger import log_action


class WorkOrderRepository:
    def __init__(self, session_factory):
        self.Session = session_factory

    def duplicate_exists(self, equipment_id: int, title: str, scheduled_date: datetime, exclude_id: int = None) -> bool:
        session = self.Session()
        try:
            query = session.query(WorkOrder).filter(
                WorkOrder.equipment_id == equipment_id,
                WorkOrder.title == title,
                WorkOrder.scheduled_date == scheduled_date
            )
            if exclude_id:
                query = query.filter(WorkOrder.id != exclude_id)
            return query.first() is not None
        finally:
            session.close()

    def create_work_order(self, title, equipment_id, type_str, priority,
                          technician_id=None, scheduled_date=None,
                          description=None, parts_used=None, schedule_id=None,
                          operator_id=None, failure_report_time=None,
                          operator_notes=None, operator_signature=None,
                          manual_cost=0.0, cost_description=None,
                          deadline=None, additional_technician_ids=None):
        session = self.Session()
        try:
            if scheduled_date and self.duplicate_exists(equipment_id, title, scheduled_date):
                return False, "یک دستور کار با همین عنوان و تاریخ برای این تجهیز قبلاً ثبت شده است."

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
                deadline=deadline,
                status=WorkOrderStatus.PENDING,
                manual_cost=manual_cost,
                cost_description=cost_description,
            )
            session.add(wo)
            session.flush()

            if additional_technician_ids:
                for uid in additional_technician_ids:
                    if uid != technician_id:
                        session.execute(work_order_technicians.insert().values(
                            work_order_id=wo.id, user_id=uid))

            session.commit()
            session.refresh(wo)
            log_action("CREATE", "work_order", wo.id, f"عنوان: {title}, تجهیز: {equipment_id}")
            return True, "کار با موفقیت ثبت شد."
        except Exception as e:
            session.rollback()
            return False, f"خطا: {str(e)}"
        finally:
            session.close()

    def create_from_pm(self, pm_schedule, due_date: datetime, created_by_user_id: int = None) -> tuple[bool, str]:
        session = self.Session()
        try:
            technician_id = pm_schedule.technician_id if pm_schedule.technician_id else None
            deadline = due_date
            if pm_schedule.estimated_duration and pm_schedule.estimated_duration > 0:
                deadline = due_date + timedelta(days=pm_schedule.estimated_duration)
            title = f"[A-PM] {pm_schedule.title} {due_date.strftime('%Y-%m-%d')}"
            wo = WorkOrder(
                equipment_id=pm_schedule.equipment_id,
                schedule_id=pm_schedule.id,
                type=WorkOrderType.PREVENTIVE,
                status=WorkOrderStatus.PENDING_APPROVAL,
                priority=WorkOrderPriority.MEDIUM,
                technician_id=technician_id,
                title=title,
                description=f"کار پیشگیرانه خودکار بر اساس برنامه PM: {pm_schedule.title}\n"
                            f"چک‌لیست: {pm_schedule.checklist or 'ندارد'}\n"
                            f"قطعات مورد نیاز: {pm_schedule.parts_required or 'ندارد'}",
                scheduled_date=due_date,
                deadline=deadline,
                created_at=datetime.now(),
                manual_cost=0.0,
            )
            session.add(wo)
            session.commit()
            session.refresh(wo)
            return True, "Work order created from PM schedule (pending manager approval)."
        except Exception as e:
            session.rollback()
            return False, f"Error: {e}"
        finally:
            session.close()

    def update_work_order(self, work_order_id, title, equipment_id, type_str,
                          priority, technician_id=None, scheduled_date=None,
                          description=None, parts_used=None,
                          operator_id=None, failure_report_time=None,
                          operator_notes=None, operator_signature=None,
                          manual_cost=None, cost_description=None,
                          deadline=None, additional_technician_ids=None):
        session = self.Session()
        try:
            wo = session.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "دستور کار یافت نشد."

            if (title != wo.title or scheduled_date != wo.scheduled_date) and scheduled_date:
                if self.duplicate_exists(equipment_id, title, scheduled_date, exclude_id=work_order_id):
                    return False, "یک دستور کار دیگر با همین عنوان و تاریخ برای این تجهیز وجود دارد."

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
            if deadline is not None:
                wo.deadline = deadline
            wo.description = description or None
            wo.parts_used = parts_used or None
            if manual_cost is not None:
                wo.manual_cost = manual_cost
            if cost_description is not None:
                wo.cost_description = cost_description

            if additional_technician_ids is not None:
                session.execute(work_order_technicians.delete().where(
                    work_order_technicians.c.work_order_id == work_order_id))
                for uid in additional_technician_ids:
                    if uid != technician_id:
                        session.execute(work_order_technicians.insert().values(
                            work_order_id=work_order_id, user_id=uid))

            session.commit()
            log_action("UPDATE", "work_order", work_order_id, f"عنوان: {title}")
            return True, "دستور کار ویرایش شد."
        except Exception as e:
            session.rollback()
            return False, f"خطا: {str(e)}"
        finally:
            session.close()

    def get_all(self, status_filter=None, type_filter=None, technician_id=None):
        session = self.Session()
        try:
            query = session.query(WorkOrder).options(
                joinedload(WorkOrder.equipment),
                joinedload(WorkOrder.technician),
                joinedload(WorkOrder.supervisor),
                joinedload(WorkOrder.operator),
                joinedload(WorkOrder.technicians)
            )
            if status_filter:
                query = query.filter(WorkOrder.status == status_filter)
            if type_filter:
                query = query.filter(WorkOrder.type == type_filter)
            if technician_id is not None:
                query = query.filter(
                    (WorkOrder.technician_id == technician_id) |
                    (WorkOrder.technician_id.is_(None))
                )
            results = query.order_by(WorkOrder.created_at.desc()).all()
            session.expunge_all()
            return results
        finally:
            session.close()

    def get_by_id(self, work_order_id):
        session = self.Session()
        try:
            wo = session.query(WorkOrder).options(
                joinedload(WorkOrder.equipment),
                joinedload(WorkOrder.technician),
                joinedload(WorkOrder.supervisor),
                joinedload(WorkOrder.operator),
                joinedload(WorkOrder.technicians)
            ).filter(WorkOrder.id == work_order_id).first()
            if wo:
                session.expunge(wo)
            return wo
        finally:
            session.close()

    def approve_creation(self, work_order_id, supervisor_id):
        session = self.Session()
        try:
            wo = session.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."
            if wo.status != WorkOrderStatus.PENDING_APPROVAL:
                return False, "فقط دستورکارهای در انتظار تأیید قابل تأیید هستند."
            wo.status = WorkOrderStatus.PENDING
            wo.supervisor_id = supervisor_id
            session.commit()
            log_action("APPROVE_CREATION", "work_order", work_order_id, "")
            return True, "دستور کار تأیید و آماده شروع شد."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def start_work(self, work_order_id):
        session = self.Session()
        try:
            wo = session.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."
            if wo.status != WorkOrderStatus.PENDING:
                return False, "فقط دستورکارهای در وضعیت «در انتظار» قابل شروع هستند."
            wo.status = WorkOrderStatus.IN_PROGRESS
            wo.start_time = datetime.now()
            session.commit()
            log_action("START", "work_order", work_order_id, "")
            return True, "کار شروع شد."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def deduct_spare_parts(self, work_order_id: int, parts_list: list) -> tuple[bool, str, list]:
        from database.spare_parts_repository import SparePartsRepository
        session = self.Session()
        try:
            low_stock_parts = []
            for item in parts_list:
                part_id = item['part_id']
                qty = item['quantity']
                sp_repo = SparePartsRepository(self.Session)
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
                    'reference': str(work_order_id),
                    'notes': f"مصرف در دستور کار {work_order_id}"
                })
                if part.current_stock <= part.min_stock:
                    low_stock_parts.append(part.part_number)
            session.commit()
            return True, "قطعات با موفقیت کسر شدند.", low_stock_parts
        except Exception as e:
            session.rollback()
            return False, f"خطا در کسر قطعات: {str(e)}", []
        finally:
            session.close()

    def request_finish(self, work_order_id, technician_notes=None, used_parts_list=None,
                       manual_cost=None, cost_description=None, end_time: datetime = None,
                       delay_minutes=None, delay_reason=None):
        session = self.Session()
        try:
            low_stock = []
            wo = session.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "دستور کار یافت نشد."
            if wo.status != WorkOrderStatus.IN_PROGRESS:
                return False, "فقط دستورکارهای در حال انجام قابل ارسال هستند."

            if used_parts_list:
                success, msg, low_stock = self.deduct_spare_parts(work_order_id, used_parts_list)
                if not success:
                    return False, msg
                wo.parts_used = json.dumps(used_parts_list)

            if manual_cost is not None:
                wo.manual_cost = manual_cost
            if cost_description:
                wo.cost_description = cost_description
            if technician_notes:
                wo.description = technician_notes

            if end_time:
                wo.end_time = end_time
            else:
                wo.end_time = datetime.now()

            # Store delay information
            wo.delay_minutes = delay_minutes
            wo.delay_reason = delay_reason

            wo.status = WorkOrderStatus.FINISH_REQUESTED
            session.commit()
            log_action("REQUEST_FINISH", "work_order", work_order_id, f"parts: {used_parts_list}, end_time: {wo.end_time}, delay: {delay_minutes} min")
            msg = "درخواست اتمام کار ارسال شد. منتظر تأیید مدیر باشید."
            if low_stock:
                msg += f"\n⚠️ هشدار: قطعات {', '.join(low_stock)} به حداقل موجودی رسیده‌اند."
            return True, msg
        except Exception as e:
            session.rollback()
            return False, f"خطا: {e}"
        finally:
            session.close()

    def approve(self, work_order_id, supervisor_id):
        session = self.Session()
        try:
            wo = session.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."
            if wo.status != WorkOrderStatus.FINISH_REQUESTED:
                return False, "فقط دستورکارهایی که درخواست اتمام دارند قابل تأیید نهایی هستند."
            wo.status = WorkOrderStatus.APPROVED
            wo.supervisor_id = supervisor_id
            session.commit()
            if wo.schedule_id:
                from database.pm_repository import PMRepository
                pm_repo = PMRepository(self.Session)
                pm_repo.update_after_completion(wo.schedule_id, wo.end_time)
            log_action("APPROVE", "work_order", work_order_id, f"end_time was {wo.end_time}")
            return True, "کار تأیید نهایی شد."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def reject_finish(self, work_order_id, supervisor_id, notes):
        session = self.Session()
        try:
            wo = session.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."
            if wo.status != WorkOrderStatus.FINISH_REQUESTED:
                return False, "فقط دستورکارهایی که درخواست اتمام دارند قابل رد هستند."
            wo.status = WorkOrderStatus.REJECTED
            wo.supervisor_id = supervisor_id
            wo.supervisor_notes = notes
            session.commit()
            success, new_id = self._create_work_order_copy(wo, notes)
            if not success:
                return False, "خطا در ایجاد دستور کار جایگزین."
            log_action("REJECT_FINISH", "work_order", work_order_id,
                       f"نظر: {notes} – دستور کار جدید #{new_id} ایجاد شد.")
            return True, f"درخواست اتمام رد شد. دستور کار جدید با شماره {new_id} ایجاد شد. تکنسین می‌تواند کار را ادامه دهد."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def _create_work_order_copy(self, original_wo, supervisor_notes):
        session = self.Session()
        try:
            if original_wo.root_parent_id:
                root_id = original_wo.root_parent_id
            else:
                root_id = original_wo.id
            new_title = f"{original_wo.title} (اصلاحی)"
            new_description = f"کار اصلاحی پس از رد درخواست اتمام:\n{supervisor_notes}\n\nشرح اصلی:\n{original_wo.description or 'ندارد'}"
            new_wo = WorkOrder(
                equipment_id=original_wo.equipment_id,
                schedule_id=original_wo.schedule_id,
                parent_work_order_id=original_wo.id,
                root_parent_id=root_id,
                type=original_wo.type,
                status=WorkOrderStatus.PENDING,
                priority=original_wo.priority,
                technician_id=original_wo.technician_id,
                title=new_title,
                description=new_description,
                scheduled_date=datetime.now() + timedelta(days=1),
                deadline=original_wo.deadline,
                created_at=datetime.now()
            )
            session.add(new_wo)
            session.commit()
            session.refresh(new_wo)
            return True, new_wo.id
        except Exception as e:
            session.rollback()
            return False, None
        finally:
            session.close()

    def delete(self, work_order_id):
        session = self.Session()
        try:
            wo = session.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
            if not wo:
                return False, "کار یافت نشد."
            session.delete(wo)
            session.commit()
            log_action("DELETE", "work_order", work_order_id, "")
            return True, "کار حذف شد."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def find_by_schedule_and_date(self, pm_schedule_id: int, scheduled_date: datetime) -> Optional[dict]:
        session = self.Session()
        try:
            wo = session.query(WorkOrder).filter(
                WorkOrder.schedule_id == pm_schedule_id,
                WorkOrder.scheduled_date == scheduled_date
            ).first()
            if wo:
                return {'id': wo.id, 'title': wo.title, 'status': wo.status.value}
            return None
        finally:
            session.close()
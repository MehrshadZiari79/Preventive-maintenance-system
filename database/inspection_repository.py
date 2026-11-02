# database/inspection_repository.py
"""
Inspection Repository - Data Access Layer for Inspection Management
"""
from typing import Optional, List
from sqlalchemy import func, case, and_
from sqlalchemy.orm import joinedload
from database.models import (
    InspectionTemplate, InspectionCheckpoint,
    Inspection, InspectionResult
)
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


class InspectionRepository:
    def __init__(self, session_factory):
        self.Session = session_factory

    def get_all_templates(self) -> List[dict]:
        session = self.Session()
        try:
            templates = session.query(InspectionTemplate).order_by(
                InspectionTemplate.name
            ).all()
            return [self._template_to_dict(t) for t in templates]
        finally:
            session.close()

    def get_active_templates(self) -> List[dict]:
        session = self.Session()
        try:
            templates = session.query(InspectionTemplate).filter(
                InspectionTemplate.is_active == True
            ).order_by(InspectionTemplate.name).all()
            return [self._template_to_dict(t) for t in templates]
        finally:
            session.close()

    def get_template_by_id(self, template_id: int) -> Optional[dict]:
        session = self.Session()
        try:
            t = session.query(InspectionTemplate).filter(
                InspectionTemplate.id == template_id
            ).first()
            return self._template_to_dict(t) if t else None
        finally:
            session.close()

    def get_templates_by_equipment(self, equipment_id: int) -> List[dict]:
        session = self.Session()
        try:
            templates = session.query(InspectionTemplate).filter(
                InspectionTemplate.equipment_id == equipment_id,
                InspectionTemplate.is_active == True
            ).order_by(InspectionTemplate.name).all()
            return [self._template_to_dict(t) for t in templates]
        finally:
            session.close()

    def create_template(self, name: str, description: str, equipment_id: Optional[int],
                        frequency: str, estimated_duration_minutes: Optional[int]) -> tuple[bool, str, Optional[int]]:
        session = self.Session()
        try:
            template = InspectionTemplate(
                name=name,
                description=description or None,
                equipment_id=equipment_id,
                frequency=frequency,
                estimated_duration_minutes=estimated_duration_minutes,
                is_active=True
            )
            session.add(template)
            session.commit()
            session.refresh(template)
            return True, "الگوی بازرسی ایجاد شد.", template.id
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}", None
        finally:
            session.close()

    def update_template(self, template_id: int, name: str, description: str,
                        equipment_id: Optional[int], frequency: str,
                        estimated_duration_minutes: Optional[int]) -> tuple[bool, str]:
        session = self.Session()
        try:
            template = session.query(InspectionTemplate).filter(
                InspectionTemplate.id == template_id
            ).first()
            if not template:
                return False, "الگو یافت نشد."
            template.name = name
            template.description = description or None
            template.equipment_id = equipment_id
            template.frequency = frequency
            template.estimated_duration_minutes = estimated_duration_minutes
            template.updated_at = tehran_now()
            session.commit()
            return True, "الگو بروزرسانی شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def toggle_template_status(self, template_id: int) -> tuple[bool, str]:
        session = self.Session()
        try:
            template = session.query(InspectionTemplate).filter(
                InspectionTemplate.id == template_id
            ).first()
            if not template:
                return False, "الگو یافت نشد."
            template.is_active = not template.is_active
            template.updated_at = tehran_now()
            session.commit()
            status = "فعال" if template.is_active else "غیرفعال"
            return True, f"الگو {status} شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def delete_template(self, template_id: int) -> tuple[bool, str]:
        session = self.Session()
        try:
            template = session.query(InspectionTemplate).filter(
                InspectionTemplate.id == template_id
            ).first()
            if not template:
                return False, "الگو یافت نشد."
            session.delete(template)
            session.commit()
            return True, "الگو حذف شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def get_checkpoints_by_template(self, template_id: int) -> List[dict]:
        session = self.Session()
        try:
            checkpoints = session.query(InspectionCheckpoint).filter(
                InspectionCheckpoint.template_id == template_id
            ).order_by(InspectionCheckpoint.order_number).all()
            return [self._checkpoint_to_dict(c) for c in checkpoints]
        finally:
            session.close()

    def create_checkpoint(self, template_id: int, title: str, description: str,
                          checkpoint_type: str, order_number: int) -> tuple[bool, str]:
        session = self.Session()
        try:
            checkpoint = InspectionCheckpoint(
                template_id=template_id,
                title=title,
                description=description or None,
                checkpoint_type=checkpoint_type,
                order_number=order_number
            )
            session.add(checkpoint)
            session.commit()
            return True, "نقطه بازرسی اضافه شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def update_checkpoint(self, checkpoint_id: int, title: str, description: str,
                          checkpoint_type: str, order_number: int) -> tuple[bool, str]:
        session = self.Session()
        try:
            checkpoint = session.query(InspectionCheckpoint).filter(
                InspectionCheckpoint.id == checkpoint_id
            ).first()
            if not checkpoint:
                return False, "نقطه بازرسی یافت نشد."
            checkpoint.title = title
            checkpoint.description = description or None
            checkpoint.checkpoint_type = checkpoint_type
            checkpoint.order_number = order_number
            session.commit()
            return True, "نقطه بازرسی بروزرسانی شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def delete_checkpoint(self, checkpoint_id: int) -> tuple[bool, str]:
        session = self.Session()
        try:
            checkpoint = session.query(InspectionCheckpoint).filter(
                InspectionCheckpoint.id == checkpoint_id
            ).first()
            if not checkpoint:
                return False, "نقطه بازرسی یافت نشد."
            session.delete(checkpoint)
            session.commit()
            return True, "نقطه بازرسی حذف شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def get_all_inspections(self, limit=None) -> List[Inspection]:
        session = self.Session()
        try:
            query = session.query(Inspection).options(
                joinedload(Inspection.template),
                joinedload(Inspection.equipment),
                joinedload(Inspection.inspector)
            ).order_by(Inspection.started_at.desc())
            if limit:
                query = query.limit(int(limit))
            inspections = query.all()
            return inspections if inspections else []
        except Exception as e:
            print(f"Error loading inspections: {e}")
            return []
        finally:
            session.close()

    def get_inspection_by_id(self, inspection_id: int) -> Optional[dict]:
        session = self.Session()
        try:
            i = session.query(Inspection).filter(
                Inspection.id == inspection_id
            ).first()
            return self._inspection_to_dict(i) if i else None
        finally:
            session.close()

    def get_inspections_by_status(self, status: str) -> List[dict]:
        session = self.Session()
        try:
            inspections = session.query(Inspection).filter(
                Inspection.status == status
            ).order_by(Inspection.started_at.desc()).all()
            return [self._inspection_to_dict(i) for i in inspections]
        finally:
            session.close()

    def get_inspections_by_equipment(self, equipment_id: int) -> List[dict]:
        session = self.Session()
        try:
            inspections = session.query(Inspection).filter(
                Inspection.equipment_id == equipment_id
            ).order_by(Inspection.started_at.desc()).all()
            return [self._inspection_to_dict(i) for i in inspections]
        finally:
            session.close()

    def create_inspection(self, template_id: int, equipment_id: int,
                          inspector_id: int) -> tuple[bool, str, Optional[int]]:
        session = self.Session()
        try:
            inspection = Inspection(
                template_id=template_id,
                equipment_id=equipment_id,
                inspector_id=inspector_id,
                started_at=tehran_now(),
                status="in_progress"
            )
            session.add(inspection)
            session.commit()
            session.refresh(inspection)
            return True, "بازرسی شروع شد.", inspection.id
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}", None
        finally:
            session.close()

    def complete_inspection(self, inspection_id: int, overall_result: str,
                            notes: str) -> tuple[bool, str]:
        session = self.Session()
        try:
            inspection = session.query(Inspection).filter(
                Inspection.id == inspection_id
            ).first()
            if not inspection:
                return False, "بازرسی یافت نشد."
            inspection.completed_at = tehran_now()
            inspection.status = "completed"
            inspection.overall_result = overall_result
            inspection.notes = notes or None
            session.commit()
            return True, "بازرسی تکمیل شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def cancel_inspection(self, inspection_id: int) -> tuple[bool, str]:
        session = self.Session()
        try:
            inspection = session.query(Inspection).filter(
                Inspection.id == inspection_id
            ).first()
            if not inspection:
                return False, "بازرسی یافت نشد."
            inspection.status = "cancelled"
            session.commit()
            return True, "بازرسی لغو شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def get_results_by_inspection(self, inspection_id: int) -> List[dict]:
        session = self.Session()
        try:
            results = session.query(InspectionResult).filter(
                InspectionResult.inspection_id == inspection_id
            ).order_by(InspectionResult.recorded_at).all()
            return [self._result_to_dict(r) for r in results]
        finally:
            session.close()

    def save_result(self, inspection_id: int, checkpoint_id: int,
                    result: str, comment: str) -> tuple[bool, str]:
        session = self.Session()
        try:
            existing = session.query(InspectionResult).filter(
                and_(
                    InspectionResult.inspection_id == inspection_id,
                    InspectionResult.checkpoint_id == checkpoint_id
                )
            ).first()
            if existing:
                existing.result = result
                existing.comment = comment or None
                existing.recorded_at = tehran_now()
            else:
                new_result = InspectionResult(
                    inspection_id=inspection_id,
                    checkpoint_id=checkpoint_id,
                    result=result,
                    comment=comment or None
                )
                session.add(new_result)
            session.commit()
            return True, "نتیجه ذخیره شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {e}"
        finally:
            session.close()

    def get_inspection_stats(self) -> dict:
        session = self.Session()
        try:
            row = session.query(
                func.count(Inspection.id).label("total"),
                func.sum(case((Inspection.status == "in_progress", 1), else_=0)).label("in_progress"),
                func.sum(case((Inspection.status == "completed", 1), else_=0)).label("completed"),
                func.sum(case((Inspection.status == "cancelled", 1), else_=0)).label("cancelled"),
            ).one()
            return {
                "total": row.total or 0,
                "in_progress": row.in_progress or 0,
                "completed": row.completed or 0,
                "cancelled": row.cancelled or 0,
            }
        finally:
            session.close()

    # --- Helper methods (unchanged) ---
    @staticmethod
    def _template_to_dict(t: InspectionTemplate) -> dict:
        return {
            "id": t.id,
            "name": t.name,
            "description": t.description or "",
            "equipment_id": t.equipment_id,
            "equipment_name": t.equipment.name if t.equipment else "عمومی",
            "frequency": t.frequency,
            "estimated_duration_minutes": t.estimated_duration_minutes or 0,
            "is_active": t.is_active,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
            "updated_at": t.updated_at.strftime("%Y-%m-%d %H:%M") if t.updated_at else "",
        }

    @staticmethod
    def _checkpoint_to_dict(c: InspectionCheckpoint) -> dict:
        return {
            "id": c.id,
            "template_id": c.template_id,
            "title": c.title,
            "description": c.description or "",
            "checkpoint_type": c.checkpoint_type,
            "order_number": c.order_number,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "",
        }

    @staticmethod
    def _inspection_to_dict(i: Inspection) -> dict:
        return {
            "id": i.id,
            "template_id": i.template_id,
            "template_name": i.template.name if i.template else "",
            "equipment_id": i.equipment_id,
            "equipment_name": i.equipment.name if i.equipment else "",
            "equipment_code": i.equipment.code if i.equipment else "",
            "inspector_id": i.inspector_id,
            "inspector_name": i.inspector.full_name if i.inspector else "",
            "started_at": i.started_at.strftime("%Y-%m-%d %H:%M") if i.started_at else "",
            "completed_at": i.completed_at.strftime("%Y-%m-%d %H:%M") if i.completed_at else "",
            "status": i.status,
            "overall_result": i.overall_result or "",
            "notes": i.notes or "",
            "created_at": i.created_at.strftime("%Y-%m-%d %H:%M") if i.created_at else "",
        }

    @staticmethod
    def _result_to_dict(r: InspectionResult) -> dict:
        return {
            "id": r.id,
            "inspection_id": r.inspection_id,
            "checkpoint_id": r.checkpoint_id,
            "checkpoint_title": r.checkpoint.title if r.checkpoint else "",
            "result": r.result,
            "comment": r.comment or "",
            "recorded_at": r.recorded_at.strftime("%Y-%m-%d %H:%M") if r.recorded_at else "",
        }
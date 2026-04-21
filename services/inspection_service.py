# services/inspection_service.py
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Tuple
from datetime import datetime
from database.models import (
    InspectionTemplate,
    InspectionCheckpoint,
    Inspection,
    InspectionResult,
    Equipment,
    User
)
from schemas.inspection import (
    InspectionTemplateCreate,
    InspectionTemplateUpdate,
    InspectionCreate,
    InspectionUpdate,
    InspectionResultCreate
)


class InspectionService:
    def __init__(self, db: Session):
        self.db = db

    def get_stats(self, equipment_id: Optional[int] = None) -> dict:
        """Alias for get_inspection_stats"""
        return self.get_inspection_stats(equipment_id)

    # Template Methods
    def create_template(self, template_data: InspectionTemplateCreate) -> InspectionTemplate:
        """Create new inspection template with checkpoints"""
        try:
            db_template = InspectionTemplate(
                name=template_data.name,
                description=template_data.description,
                equipment_id=template_data.equipment_id,
                frequency=template_data.frequency,
                estimated_duration_minutes=template_data.estimated_duration_minutes,
                is_active=template_data.is_active
            )

            self.db.add(db_template)
            self.db.flush()

            # Add checkpoints
            for cp_data in template_data.checkpoints:
                checkpoint = InspectionCheckpoint(
                    template_id=db_template.id,
                    title=cp_data.title,
                    description=cp_data.description,
                    checkpoint_type=cp_data.checkpoint_type,
                    order_number=cp_data.order_number
                )
                self.db.add(checkpoint)

            self.db.commit()
            self.db.refresh(db_template)
            return db_template
        except Exception as e:
            self.db.rollback()
            raise Exception(f"خطا در ایجاد قالب: {str(e)}")

    def get_template(self, template_id: int) -> Optional[InspectionTemplate]:
        """Get template by ID with relationships loaded"""
        return self.db.query(InspectionTemplate).options(
            joinedload(InspectionTemplate.equipment),
            joinedload(InspectionTemplate.checkpoints)
        ).filter(InspectionTemplate.id == template_id).first()

    def get_all_templates(self, equipment_id: Optional[int] = None) -> List[InspectionTemplate]:
        """Get all templates, optionally filtered by equipment"""
        try:
            query = self.db.query(InspectionTemplate).options(
                joinedload(InspectionTemplate.equipment),
                joinedload(InspectionTemplate.checkpoints)
            )

            if equipment_id:
                query = query.filter(InspectionTemplate.equipment_id == equipment_id)

            return query.all()
        except Exception as e:
            print(f"Error loading templates: {str(e)}")
            return []

    def get_active_templates(self, equipment_id: Optional[int] = None) -> List[InspectionTemplate]:
        """Get only active templates"""
        try:
            query = self.db.query(InspectionTemplate).options(
                joinedload(InspectionTemplate.equipment),
                joinedload(InspectionTemplate.checkpoints)
            ).filter(InspectionTemplate.is_active == True)

            if equipment_id:
                query = query.filter(InspectionTemplate.equipment_id == equipment_id)

            return query.all()
        except Exception as e:
            print(f"Error loading active templates: {str(e)}")
            return []

    def update_template(self, template_id: int, update_data: InspectionTemplateUpdate) -> Optional[InspectionTemplate]:
        """Update template"""
        try:
            template = self.get_template(template_id)

            if not template:
                return None

            update_dict = update_data.model_dump(exclude_unset=True)

            for key, value in update_dict.items():
                setattr(template, key, value)

            template.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(template)
            return template
        except Exception as e:
            self.db.rollback()
            raise Exception(f"خطا در بروزرسانی قالب: {str(e)}")

    def delete_template(self, template_id: int) -> Tuple[bool, str]:
        """Delete template and its checkpoints"""
        try:
            template = self.get_template(template_id)
            if not template:
                return False, "قالب مورد نظر یافت نشد"

            # Check if template has any inspections
            inspection_count = self.db.query(Inspection).filter(
                Inspection.template_id == template_id
            ).count()

            if inspection_count > 0:
                return False, f"این قالب دارای {inspection_count} بازرسی ثبت شده است. ابتدا بازرسی‌ها را حذف کنید."

            # Delete checkpoints first
            self.db.query(InspectionCheckpoint).filter(
                InspectionCheckpoint.template_id == template_id
            ).delete()

            # Delete template
            self.db.delete(template)
            self.db.commit()
            return True, "قالب با موفقیت حذف شد"
        except Exception as e:
            self.db.rollback()
            return False, f"خطا در حذف قالب: {str(e)}"

    def delete_inspection(self, inspection_id: int) -> Tuple[bool, str]:
        """Delete an inspection and its results"""
        try:
            inspection = self.get_inspection(inspection_id)
            if not inspection:
                return False, "بازرسی مورد نظر یافت نشد"

            # Delete related results first
            self.db.query(InspectionResult).filter(
                InspectionResult.inspection_id == inspection_id
            ).delete()

            self.db.delete(inspection)
            self.db.commit()
            return True, "بازرسی با موفقیت حذف شد"
        except Exception as e:
            self.db.rollback()
            return False, f"خطا در حذف بازرسی: {str(e)}"

    def toggle_template_active(self, template_id: int) -> Tuple[bool, str]:
        """Toggle template active status"""
        try:
            template = self.get_template(template_id)
            if not template:
                return False, "قالب مورد نظر یافت نشد"

            template.is_active = not template.is_active
            template.updated_at = datetime.utcnow()
            self.db.commit()
            status = "فعال" if template.is_active else "غیرفعال"
            return True, f"قالب با موفقیت {status} شد"
        except Exception as e:
            self.db.rollback()
            return False, f"خطا در تغییر وضعیت قالب: {str(e)}"

    # Checkpoint Methods
    def add_checkpoint(self, template_id: int, checkpoint_data: dict) -> Optional[InspectionCheckpoint]:
        """Add checkpoint to template"""
        try:
            # Verify template exists
            template = self.get_template(template_id)
            if not template:
                return None

            checkpoint = InspectionCheckpoint(
                template_id=template_id,
                **checkpoint_data
            )

            self.db.add(checkpoint)
            self.db.commit()
            self.db.refresh(checkpoint)
            return checkpoint
        except Exception as e:
            self.db.rollback()
            print(f"Error adding checkpoint: {str(e)}")
            return None

    def update_checkpoint(self, checkpoint_id: int, checkpoint_data: dict) -> Optional[InspectionCheckpoint]:
        """Update checkpoint"""
        try:
            checkpoint = self.db.query(InspectionCheckpoint).filter(
                InspectionCheckpoint.id == checkpoint_id
            ).first()

            if not checkpoint:
                return None

            for key, value in checkpoint_data.items():
                if hasattr(checkpoint, key):
                    setattr(checkpoint, key, value)

            self.db.commit()
            self.db.refresh(checkpoint)
            return checkpoint
        except Exception as e:
            self.db.rollback()
            print(f"Error updating checkpoint: {str(e)}")
            return None

    def delete_checkpoint(self, checkpoint_id: int) -> bool:
        """Delete checkpoint"""
        try:
            checkpoint = self.db.query(InspectionCheckpoint).filter(
                InspectionCheckpoint.id == checkpoint_id
            ).first()

            if not checkpoint:
                return False

            self.db.delete(checkpoint)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            print(f"Error deleting checkpoint: {str(e)}")
            return False

    def get_checkpoints_by_template(self, template_id: int) -> List[InspectionCheckpoint]:
        """Get all checkpoints for a template"""
        try:
            return self.db.query(InspectionCheckpoint).filter(
                InspectionCheckpoint.template_id == template_id
            ).order_by(InspectionCheckpoint.order_number).all()
        except Exception as e:
            print(f"Error loading checkpoints: {str(e)}")
            return []

    # Inspection Methods
    def create_inspection(self, inspection_data: InspectionCreate) -> Optional[Inspection]:
        """Start new inspection"""
        try:
            # Verify template exists and is active
            template = self.get_template(inspection_data.template_id)
            if not template:
                raise ValueError("قالب مورد نظر یافت نشد")
            if not template.is_active:
                raise ValueError("قالب مورد نظر غیرفعال است")

            # Verify equipment exists
            equipment = self.db.query(Equipment).filter(
                Equipment.id == inspection_data.equipment_id
            ).first()
            if not equipment:
                raise ValueError("تجهیز مورد نظر یافت نشد")

            inspection = Inspection(
                template_id=inspection_data.template_id,
                equipment_id=inspection_data.equipment_id,
                inspector_id=inspection_data.inspector_id,
                notes=inspection_data.notes,
                status="in_progress",
                started_at=datetime.utcnow()
            )

            self.db.add(inspection)
            self.db.commit()
            self.db.refresh(inspection)
            return inspection
        except Exception as e:
            self.db.rollback()
            raise Exception(f"خطا در شروع بازرسی: {str(e)}")

    def get_inspection(self, inspection_id: int) -> Optional[Inspection]:
        """Get inspection by ID with all relationships loaded"""
        return self.db.query(Inspection).options(
            joinedload(Inspection.template),
            joinedload(Inspection.equipment),
            joinedload(Inspection.inspector),
            joinedload(Inspection.results).joinedload(InspectionResult.checkpoint)
        ).filter(Inspection.id == inspection_id).first()

    def get_all_inspections(self, equipment_id: Optional[int] = None) -> List[Inspection]:
        """Get all inspections with related data"""
        try:
            query = self.db.query(Inspection).options(
                joinedload(Inspection.template),
                joinedload(Inspection.equipment),
                joinedload(Inspection.inspector)
            )

            if equipment_id:
                query = query.filter(Inspection.equipment_id == equipment_id)

            return query.order_by(Inspection.started_at.desc()).all()
        except Exception as e:
            print(f"Error loading inspections: {str(e)}")
            return []

    def get_inspection_results(self, inspection_id: int) -> List[InspectionResult]:
        """Get all results for an inspection"""
        try:
            return self.db.query(InspectionResult).options(
                joinedload(InspectionResult.checkpoint)
            ).filter(InspectionResult.inspection_id == inspection_id).all()
        except Exception as e:
            print(f"Error loading inspection results: {str(e)}")
            return []

    def save_results(self, inspection_id: int, results: List[InspectionResultCreate]) -> Optional[Inspection]:
        """Save inspection results and complete inspection"""
        try:
            inspection = self.get_inspection(inspection_id)

            if not inspection:
                raise ValueError("Inspection not found")

            if inspection.status != "in_progress":
                raise ValueError("فقط بازرسی‌های در حال انجام قابل تکمیل هستند")

            # Delete existing results if any
            self.db.query(InspectionResult).filter(
                InspectionResult.inspection_id == inspection_id
            ).delete()

            # Save new results
            pass_count = 0
            fail_count = 0

            for result_data in results:
                result = InspectionResult(
                    inspection_id=inspection_id,
                    checkpoint_id=result_data.checkpoint_id,
                    result=result_data.result,
                    comment=result_data.comment
                )

                if result_data.result == "pass":
                    pass_count += 1
                elif result_data.result == "fail":
                    fail_count += 1

                self.db.add(result)

            # Determine overall result
            total_checkpoints = pass_count + fail_count
            if total_checkpoints == 0:
                overall_result = "partial"
            elif fail_count == 0:
                overall_result = "pass"
            elif pass_count == 0:
                overall_result = "fail"
            else:
                overall_result = "partial"

            # Complete inspection
            inspection.status = "completed"
            inspection.completed_at = datetime.utcnow()
            inspection.overall_result = overall_result

            self.db.commit()
            self.db.refresh(inspection)
            return inspection
        except Exception as e:
            self.db.rollback()
            raise Exception(f"خطا در ذخیره نتایج: {str(e)}")

    def cancel_inspection(self, inspection_id: int) -> Optional[Inspection]:
        """Cancel inspection"""
        try:
            inspection = self.get_inspection(inspection_id)

            if not inspection:
                return None

            if inspection.status == "completed":
                raise ValueError("بازرسی تکمیل شده قابل لغو نیست")

            inspection.status = "cancelled"
            inspection.completed_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(inspection)
            return inspection
        except Exception as e:
            self.db.rollback()
            raise Exception(f"خطا در لغو بازرسی: {str(e)}")

    def update_inspection(self, inspection_id: int, update_data: InspectionUpdate) -> Optional[Inspection]:
        """Update inspection"""
        try:
            inspection = self.get_inspection(inspection_id)

            if not inspection:
                return None

            update_dict = update_data.model_dump(exclude_unset=True)

            for key, value in update_dict.items():
                if hasattr(inspection, key):
                    setattr(inspection, key, value)

            self.db.commit()
            self.db.refresh(inspection)
            return inspection
        except Exception as e:
            self.db.rollback()
            raise Exception(f"خطا در بروزرسانی بازرسی: {str(e)}")

    # Statistics
    def get_inspection_stats(self, equipment_id: Optional[int] = None) -> dict:
        """Get inspection statistics"""
        try:
            query = self.db.query(Inspection)

            if equipment_id:
                query = query.filter(Inspection.equipment_id == equipment_id)

            total = query.count()
            completed = query.filter(Inspection.status == "completed").count()
            in_progress = query.filter(Inspection.status == "in_progress").count()
            cancelled = query.filter(Inspection.status == "cancelled").count()
            passed = query.filter(Inspection.overall_result == "pass").count()
            failed = query.filter(Inspection.overall_result == "fail").count()
            partial = query.filter(Inspection.overall_result == "partial").count()

            return {
                "total": total,
                "completed": completed,
                "in_progress": in_progress,
                "cancelled": cancelled,
                "passed": passed,
                "failed": failed,
                "partial": partial,
                "pass_rate": (passed / completed * 100) if completed > 0 else 0
            }
        except Exception as e:
            print(f"Error calculating stats: {str(e)}")
            return {
                "total": 0,
                "completed": 0,
                "in_progress": 0,
                "cancelled": 0,
                "passed": 0,
                "failed": 0,
                "partial": 0,
                "pass_rate": 0
            }

    def get_equipment_inspection_history(self, equipment_id: int, limit: int = 10) -> List[Inspection]:
        """Get inspection history for specific equipment"""
        try:
            return self.db.query(Inspection).options(
                joinedload(Inspection.template),
                joinedload(Inspection.inspector)
            ).filter(
                Inspection.equipment_id == equipment_id
            ).order_by(
                Inspection.started_at.desc()
            ).limit(limit).all()
        except Exception as e:
            print(f"Error loading equipment history: {str(e)}")
            return []
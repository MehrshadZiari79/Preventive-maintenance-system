# services/inspection_service.py
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from database.models import (
    InspectionTemplate,
    InspectionCheckpoint,
    Inspection,
    InspectionResult
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

    # Template Methods
    def create_template(self, template_data: InspectionTemplateCreate) -> InspectionTemplate:
        """Create new inspection template with checkpoints"""
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

    def get_template(self, template_id: int) -> Optional[InspectionTemplate]:
        """Get template by ID"""
        return self.db.query(InspectionTemplate).filter(
            InspectionTemplate.id == template_id
        ).first()

    def get_all_templates(self, equipment_id: Optional[int] = None) -> List[InspectionTemplate]:
        """Get all templates, optionally filtered by equipment"""
        query = self.db.query(InspectionTemplate)

        if equipment_id:
            query = query.filter(InspectionTemplate.equipment_id == equipment_id)

        return query.all()

    def get_active_templates(self, equipment_id: Optional[int] = None) -> List[InspectionTemplate]:
        """Get only active templates"""
        query = self.db.query(InspectionTemplate).filter(
            InspectionTemplate.is_active == True
        )

        if equipment_id:
            query = query.filter(InspectionTemplate.equipment_id == equipment_id)

        return query.all()

    def update_template(self, template_id: int, update_data: InspectionTemplateUpdate) -> Optional[InspectionTemplate]:
        """Update template"""
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

    def delete_template(self, template_id: int) -> bool:
        """Delete template"""
        template = self.get_template(template_id)

        if not template:
            return False

        self.db.delete(template)
        self.db.commit()
        return True

    # Checkpoint Methods
    def add_checkpoint(self, template_id: int, checkpoint_data: dict) -> InspectionCheckpoint:
        """Add checkpoint to template"""
        checkpoint = InspectionCheckpoint(
            template_id=template_id,
            **checkpoint_data
        )

        self.db.add(checkpoint)
        self.db.commit()
        self.db.refresh(checkpoint)
        return checkpoint

    def delete_checkpoint(self, checkpoint_id: int) -> bool:
        """Delete checkpoint"""
        checkpoint = self.db.query(InspectionCheckpoint).filter(
            InspectionCheckpoint.id == checkpoint_id
        ).first()

        if not checkpoint:
            return False

        self.db.delete(checkpoint)
        self.db.commit()
        return True

    # Inspection Methods
    def create_inspection(self, inspection_data: InspectionCreate) -> Inspection:
        """Start new inspection"""
        inspection = Inspection(
            template_id=inspection_data.template_id,
            equipment_id=inspection_data.equipment_id,
            inspector_id=inspection_data.inspector_id,
            notes=inspection_data.notes,
            status="in_progress"
        )

        self.db.add(inspection)
        self.db.commit()
        self.db.refresh(inspection)
        return inspection

    def get_inspection(self, inspection_id: int) -> Optional[Inspection]:
        """Get inspection by ID"""
        return self.db.query(Inspection).filter(
            Inspection.id == inspection_id
        ).first()

    def get_all_inspections(self, equipment_id: Optional[int] = None) -> List[Inspection]:
        """Get all inspections"""
        query = self.db.query(Inspection)

        if equipment_id:
            query = query.filter(Inspection.equipment_id == equipment_id)

        return query.order_by(Inspection.started_at.desc()).all()

    def save_results(self, inspection_id: int, results: List[InspectionResultCreate]) -> Inspection:
        """Save inspection results and complete inspection"""
        inspection = self.get_inspection(inspection_id)

        if not inspection:
            raise ValueError("Inspection not found")

        # Save results
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
        if fail_count == 0:
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

    def cancel_inspection(self, inspection_id: int) -> Optional[Inspection]:
        """Cancel inspection"""
        inspection = self.get_inspection(inspection_id)

        if not inspection:
            return None

        inspection.status = "cancelled"
        inspection.completed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(inspection)
        return inspection

    # Statistics
    def get_inspection_stats(self, equipment_id: Optional[int] = None) -> dict:
        """Get inspection statistics"""
        query = self.db.query(Inspection)

        if equipment_id:
            query = query.filter(Inspection.equipment_id == equipment_id)

        total = query.count()
        completed = query.filter(Inspection.status == "completed").count()
        passed = query.filter(Inspection.overall_result == "pass").count()
        failed = query.filter(Inspection.overall_result == "fail").count()

        return {
            "total": total,
            "completed": completed,
            "in_progress": total - completed,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / completed * 100) if completed > 0 else 0
        }

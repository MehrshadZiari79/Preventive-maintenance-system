from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
from database.db import Base

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index, Numeric
class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    TECHNICIAN = "technician"


class EquipmentStatus(str, Enum):
    OPERATIONAL = "operational"
    MAINTENANCE = "maintenance"
    BREAKDOWN = "breakdown"
    INACTIVE = "inactive"


class EquipmentCriticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PMFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    BIANNUAL = "biannual"
    ANNUAL = "annual"
    CUSTOM = "custom"


class PMStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OVERDUE = "overdue"


class InspectionFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class CheckpointType(str, Enum):
    VISUAL = "visual"
    MEASUREMENT = "measurement"
    FUNCTIONAL = "functional"
    SAFETY = "safety"


class InspectionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InspectionResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NA = "na"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), default=UserRole.TECHNICIAN.value, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    pm_schedules = relationship("PMSchedule", back_populates="technician", foreign_keys="PMSchedule.technician_id")
    inspections = relationship("Inspection", back_populates="inspector")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    serial_number = Column(String(100), nullable=True)
    location = Column(String(100), nullable=False, index=True)
    installation_date = Column(DateTime, nullable=True)
    status = Column(String(20), default=EquipmentStatus.OPERATIONAL.value, nullable=False, index=True)
    criticality_level = Column(String(20), default=EquipmentCriticality.MEDIUM.value, nullable=False, index=True)
    specifications = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pm_schedules = relationship("PMSchedule", back_populates="equipment")
    inspection_templates = relationship("InspectionTemplate", back_populates="equipment")
    inspections = relationship("Inspection", back_populates="equipment")

    def __repr__(self):
        return f"<Equipment {self.code} - {self.name}>"


class PMSchedule(Base):
    __tablename__ = "pm_schedules"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False, index=True)
    technician_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    frequency = Column(String(20), nullable=False, default=PMFrequency.MONTHLY.value)
    interval_days = Column(Integer, nullable=False, default=30)
    last_done = Column(DateTime, nullable=True)
    next_due = Column(DateTime, nullable=True, index=True)
    checklist = Column(Text, nullable=True)
    estimated_duration = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="pm_schedules")
    technician = relationship("User", back_populates="pm_schedules", foreign_keys=[technician_id])

    __table_args__ = (
        Index("ix_pm_schedules_active_due", "is_active", "next_due"),
    )

    def __repr__(self):
        return f"<PMSchedule {self.title} - {self.frequency}>"


class InspectionTemplate(Base):
    __tablename__ = "inspection_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=True, index=True)
    frequency = Column(String(50), nullable=False, default=InspectionFrequency.MONTHLY.value, index=True)
    estimated_duration_minutes = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="inspection_templates")
    checkpoints = relationship("InspectionCheckpoint", back_populates="template", cascade="all, delete-orphan")
    inspections = relationship("Inspection", back_populates="template")

    __table_args__ = (
        Index("ix_inspection_templates_active_equipment", "is_active", "equipment_id"),
    )

    def __repr__(self):
        return f"<InspectionTemplate {self.name}>"


class InspectionCheckpoint(Base):
    __tablename__ = "inspection_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("inspection_templates.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    checkpoint_type = Column(String(50), nullable=False, default=CheckpointType.VISUAL.value)
    order_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    template = relationship("InspectionTemplate", back_populates="checkpoints")
    results = relationship("InspectionResult", back_populates="checkpoint")

    __table_args__ = (
        Index("ix_inspection_checkpoints_template_order", "template_id", "order_number"),
    )

    def __repr__(self):
        return f"<InspectionCheckpoint {self.title}>"


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("inspection_templates.id"), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False, index=True)
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), default=InspectionStatus.IN_PROGRESS.value, nullable=False, index=True)
    overall_result = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    template = relationship("InspectionTemplate", back_populates="inspections")
    equipment = relationship("Equipment", back_populates="inspections")
    inspector = relationship("User", back_populates="inspections")
    results = relationship("InspectionResult", back_populates="inspection", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_inspections_status_started", "status", "started_at"),
        Index("ix_inspections_equipment_status", "equipment_id", "status"),
    )

    def __repr__(self):
        return f"<Inspection {self.id} - {self.status}>"


class InspectionResult(Base):
    __tablename__ = "inspection_results"

    id = Column(Integer, primary_key=True, index=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"), nullable=False, index=True)
    checkpoint_id = Column(Integer, ForeignKey("inspection_checkpoints.id"), nullable=False, index=True)
    result = Column(String(50), nullable=False)
    comment = Column(Text, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    inspection = relationship("Inspection", back_populates="results")
    checkpoint = relationship("InspectionCheckpoint", back_populates="results")

    __table_args__ = (
        Index("ix_inspection_results_inspection_checkpoint", "inspection_id", "checkpoint_id"),
    )

    def __repr__(self):
        return f"<InspectionResult {self.result}>"


# Add to database/models.py

class SparePart(Base):
    __tablename__ = "spare_parts"

    id = Column(Integer, primary_key=True, index=True)
    part_number = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    unit = Column(String(20), nullable=True)
    min_stock = Column(Integer, default=0, nullable=False)
    current_stock = Column(Integer, default=0, nullable=False)
    unit_price = Column(Numeric(10, 2), default=0.0, nullable=False)
    location = Column(String(100), nullable=True)
    supplier = Column(String(200), nullable=True)
    equipment_codes = Column(Text, nullable=True)  # comma-separated
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship("SparePartTransaction", back_populates="part", cascade="all, delete-orphan")


class SparePartTransaction(Base):
    __tablename__ = "spare_part_transactions"

    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, ForeignKey("spare_parts.id"), nullable=False, index=True)
    transaction_type = Column(String(10), nullable=False)  # 'IN' or 'OUT'
    quantity = Column(Integer, nullable=False)
    reference = Column(String(100), nullable=True)  # e.g., PO number, WO number
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    part = relationship("SparePart", back_populates="transactions")
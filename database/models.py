# database/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index, Numeric, Float, Table
from sqlalchemy import Unicode, UnicodeText
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from enum import Enum

Base = declarative_base()


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    TECHNICIAN = "technician"
    PRODUCTION_EXPERT = "production_expert"   # <-- new role


class ProductionLog(Base):
    __tablename__ = "production_logs"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False, index=True)
    log_date = Column(DateTime, nullable=False, index=True)
    operating_hours = Column(Numeric(10, 2), default=0.0, nullable=False)
    planned_hours = Column(Numeric(10, 2), default=0.0, nullable=False)
    downtime_hours = Column(Numeric(10, 2), default=0.0, nullable=False)
    output_units = Column(Integer, default=0, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    equipment = relationship("Equipment", backref="production_logs")


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


# ---------- Association table for WorkOrder <-> User (multiple technicians) ----------
work_order_technicians = Table(
    "work_order_technicians",
    Base.metadata,
    Column("work_order_id", Integer, ForeignKey("work_orders.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(Unicode(50), unique=True, nullable=False, index=True)
    password_hash = Column(Unicode(256), nullable=False)
    full_name = Column(Unicode(100), nullable=False)
    role = Column(Unicode(20), default=UserRole.TECHNICIAN.value, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # --- New fields ---
    personnel_code = Column(Unicode(50), nullable=True)   # شماره پرسنلی
    service_unit = Column(Unicode(100), nullable=True)    # واحد خدمت

    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    pm_schedules = relationship("PMSchedule", back_populates="technician", foreign_keys="PMSchedule.technician_id")
    inspections = relationship("Inspection", back_populates="inspector")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(Unicode(50), unique=True, nullable=False, index=True)
    name = Column(Unicode(100), nullable=False)
    category = Column(Unicode(50), nullable=False, index=True)
    manufacturer = Column(Unicode(100), nullable=True)
    model = Column(Unicode(100), nullable=True)
    serial_number = Column(Unicode(100), nullable=True)
    location = Column(Unicode(100), nullable=False, index=True)
    installation_date = Column(DateTime, nullable=True)
    status = Column(Unicode(20), default=EquipmentStatus.OPERATIONAL.value, nullable=False, index=True)
    criticality_level = Column(Unicode(20), default=EquipmentCriticality.MEDIUM.value, nullable=False, index=True)
    specifications = Column(UnicodeText, nullable=True)
    notes = Column(UnicodeText, nullable=True)

    length = Column(Float, nullable=True)
    width = Column(Float, nullable=True)
    diameter = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)

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
    title = Column(Unicode(150), nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False, index=True)
    technician_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    frequency = Column(Unicode(20), nullable=False, default=PMFrequency.MONTHLY.value)
    interval_days = Column(Integer, nullable=False, default=30)
    last_done = Column(DateTime, nullable=True)
    next_due = Column(DateTime, nullable=True, index=True)
    checklist = Column(UnicodeText, nullable=True)
    estimated_duration = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    notes = Column(UnicodeText, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    parts_required = Column(UnicodeText, nullable=True)

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
    name = Column(Unicode(200), nullable=False)
    description = Column(UnicodeText, nullable=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=True, index=True)
    frequency = Column(Unicode(50), nullable=False, default=InspectionFrequency.MONTHLY.value, index=True)
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
    title = Column(Unicode(200), nullable=False)
    description = Column(UnicodeText, nullable=True)
    checkpoint_type = Column(Unicode(50), nullable=False, default=CheckpointType.VISUAL.value)
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
    status = Column(Unicode(50), default=InspectionStatus.IN_PROGRESS.value, nullable=False, index=True)
    overall_result = Column(Unicode(50), nullable=True)
    notes = Column(UnicodeText, nullable=True)
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
    result = Column(Unicode(50), nullable=False)
    comment = Column(UnicodeText, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    inspection = relationship("Inspection", back_populates="results")
    checkpoint = relationship("InspectionCheckpoint", back_populates="results")

    __table_args__ = (
        Index("ix_inspection_results_inspection_checkpoint", "inspection_id", "checkpoint_id"),
    )

    def __repr__(self):
        return f"<InspectionResult {self.result}>"


class SparePart(Base):
    __tablename__ = "spare_parts"

    id = Column(Integer, primary_key=True, index=True)
    part_number = Column(Unicode(100), unique=True, nullable=False, index=True)
    name = Column(Unicode(200), nullable=False)
    description = Column(UnicodeText, nullable=True)
    category = Column(Unicode(100), nullable=True, index=True)
    unit = Column(Unicode(20), nullable=True)
    min_stock = Column(Integer, default=0, nullable=False)
    current_stock = Column(Integer, default=0, nullable=False)
    unit_price = Column(Numeric(10, 2), default=0.0, nullable=False)
    location = Column(Unicode(100), nullable=True)
    supplier = Column(Unicode(200), nullable=True)
    equipment_codes = Column(UnicodeText, nullable=True)
    notes = Column(UnicodeText, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship("SparePartTransaction", back_populates="part", cascade="all, delete-orphan")


class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(Unicode(100), unique=True, nullable=False)
    value = Column(UnicodeText, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    username = Column(Unicode(50), nullable=False)
    action = Column(Unicode(50), nullable=False)
    entity_type = Column(Unicode(50), nullable=False)
    entity_id = Column(Integer, nullable=True)
    details = Column(UnicodeText, nullable=True)
    ip_address = Column(Unicode(45), nullable=True)
    created_at = Column(DateTime, default=datetime.now, index=True)

    user = relationship("User", backref="activity_logs")


class SparePartTransaction(Base):
    __tablename__ = "spare_part_transactions"

    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, ForeignKey("spare_parts.id"), nullable=False, index=True)
    transaction_type = Column(Unicode(10), nullable=False)
    quantity = Column(Integer, nullable=False)
    reference = Column(Unicode(100), nullable=True)
    notes = Column(UnicodeText, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    batch_price = Column(Numeric(10, 2), nullable=True, default=0.0)

    part = relationship("SparePart", back_populates="transactions")

class RolePermissions(Base):
    __tablename__ = "role_permissions"
    __table_args__ = {'schema': 'dbo'}          # <-- force dbo

    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(Unicode(50), unique=True, nullable=False, index=True)
    permissions_json = Column(UnicodeText, nullable=True)

    def __repr__(self):
        return f"<RolePermissions {self.role_name}>"
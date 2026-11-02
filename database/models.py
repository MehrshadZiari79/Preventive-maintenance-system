# database/models.py
from sqlalchemy import (
    Column,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Float,
    Table,
)
from sqlalchemy import Unicode, UnicodeText
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from enum import Enum
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


# ============================================================================
# BASE
# ============================================================================

Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    TECHNICIAN = "technician"
    PRODUCTION_EXPERT = "production_expert"


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


class InspectionResultEnum(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NA = "na"


# ============================================================================
# LEGACY WORK ORDER <-> USER ASSOCIATION
# ============================================================================
#
# KEEP THIS TABLE.
#
# Historical Work Orders may contain multiple User technician assignments.
# It is intentionally preserved for compatibility.
#

work_order_technicians = Table(
    "work_order_technicians",
    Base.metadata,

    Column(
        "work_order_id",
        Integer,
        ForeignKey("work_orders.id"),
        primary_key=True,
    ),

    Column(
        "user_id",
        Integer,
        ForeignKey("users.id"),
        primary_key=True,
    ),
)


# ============================================================================
# WORK ORDER <-> PERSONNEL COMPLETION ASSOCIATION
# ============================================================================
#
# Required by:
#   - database/work_order.py       (WorkOrder.completers, secondary=...)
#   - database/personnel_repository.py (imports this Table directly)
#
# This table was referenced everywhere but never actually defined, which
# broke imports (ImportError on `from database.models import
# work_order_completers`) and mapper configuration (unresolvable
# `secondary="work_order_completers"` string).
#

work_order_completers = Table(
    "work_order_completers",
    Base.metadata,

    Column(
        "work_order_id",
        Integer,
        ForeignKey("work_orders.id"),
        primary_key=True,
    ),

    Column(
        "personnel_id",
        Integer,
        ForeignKey("personnel.id"),
        primary_key=True,
    ),
)


# ============================================================================
# REPAIR REQUEST <-> PERSONNEL COMPLETION ASSOCIATION
# ============================================================================

repair_request_completers = Table(
    "repair_request_completers",
    Base.metadata,

    Column("completion_id", Integer, ForeignKey("repair_request_completions.id"), primary_key=True),
    Column("personnel_id", Integer, ForeignKey("personnel.id"), primary_key=True),
)


# ============================================================================
# USER
# ============================================================================

class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    username = Column(
        Unicode(50),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash = Column(
        Unicode(256),
        nullable=False,
    )

    full_name = Column(
        Unicode(100),
        nullable=False,
    )

    role = Column(
        Unicode(20),
        default=UserRole.TECHNICIAN.value,
        nullable=False,
        index=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------------
    # Existing fields
    # ------------------------------------------------------------------------

    personnel_code = Column(
        Unicode(50),
        nullable=True,
    )

    service_unit = Column(
        Unicode(100),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=tehran_now,
    )

    last_login = Column(
        DateTime,
        nullable=True,
    )

    # ------------------------------------------------------------------------
    # Existing PM relationship
    #
    # There is only one FK from PMSchedule to User:
    #
    #     PMSchedule.technician_id
    #
    # Therefore no foreign_keys argument is needed.
    # ------------------------------------------------------------------------

    pm_schedules = relationship(
        "PMSchedule",
        back_populates="technician",
    )

    # ------------------------------------------------------------------------
    # Existing inspection relationship
    # ------------------------------------------------------------------------

    inspections = relationship(
        "Inspection",
        back_populates="inspector",
    )

    # ------------------------------------------------------------------------
    # IMPORTANT
    #
    # No WorkOrder relationships are defined here.
    #
    # database/work_order.py already defines:
    #
    #     technician
    #     supervisor
    #     operator
    #     technicians
    #
    # using backref.
    #
    # Duplicating them here can break mapper configuration.
    # ------------------------------------------------------------------------

    def __repr__(self):
        return (
            f"<User "
            f"{self.username} "
            f"({self.role})>"
        )


# ============================================================================
# DEPARTMENT
# ============================================================================

class Department(Base):
    """
    Responsible department.

    Business fields:

        id
        name
    """

    __tablename__ = "departments"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        Unicode(150),
        nullable=False,
        unique=True,
        index=True,
    )

    # ------------------------------------------------------------------------
    # Personnel
    # ------------------------------------------------------------------------

    personnel = relationship(
        "Personnel",
        back_populates="department",
    )

    # ------------------------------------------------------------------------
    # PM
    #
    # PMSchedule.department_id is the FK.
    # No explicit foreign_keys argument is necessary.
    # ------------------------------------------------------------------------

    pm_schedules = relationship(
        "PMSchedule",
        back_populates="department",
    )

    # ------------------------------------------------------------------------
    # Work Orders
    #
    # WorkOrder.department_id is the FK.
    # ------------------------------------------------------------------------

    work_orders = relationship(
        "WorkOrder",
        back_populates="department",
    )

    def __repr__(self):
        return (
            f"<Department "
            f"{self.id} - "
            f"{self.name}>"
        )


# ============================================================================
# PERSONNEL
# ============================================================================

class Personnel(Base):
    """
    Actual maintenance personnel.

    This is NOT the same as an application User.

    User:
        login / permissions / application account

    Personnel:
        actual employee who performs maintenance

    Fields:

        id
        personnel_code
        full_name
        department_id
    """

    __tablename__ = "personnel"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    personnel_code = Column(
        Unicode(50),
        nullable=True,
        unique=True,
        index=True,
    )

    full_name = Column(
        Unicode(150),
        nullable=False,
        index=True,
    )

    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=False,
        index=True,
    )

    department = relationship(
        "Department",
        back_populates="personnel",
    )

    # Repair requests assigned to this personnel when the request is issued.
    # This is separate from completion personnel.
    assigned_repair_requests = relationship(
        "RepairRequestDocument",
        foreign_keys="RepairRequestDocument.assigned_personnel_id",
        back_populates="assigned_personnel",
    )

    # ------------------------------------------------------------------------
    # Work Orders actually completed by this personnel.
    #
    # WorkOrder.completed_by_personnel_id is the FK.
    #
    # No foreign_keys argument is needed.
    # ------------------------------------------------------------------------

    completed_work_orders = relationship(
        "WorkOrder",
        secondary="work_order_completers",
        back_populates="completers",
    )

    # Repair Request completion history.
    completed_repair_completions = relationship(
        "RepairRequestCompletion",
        secondary="repair_request_completers",
        back_populates="personnel",
    )

    def __repr__(self):
        return (
            f"<Personnel "
            f"{self.id} - "
            f"{self.full_name}>"
        )


# ============================================================================
# PRODUCTION LOG
# ============================================================================

class ProductionLog(Base):

    __tablename__ = "production_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    equipment_id = Column(
        Integer,
        ForeignKey("equipment.id"),
        nullable=False,
        index=True,
    )

    log_date = Column(
        DateTime,
        nullable=False,
        index=True,
    )

    operating_hours = Column(
        Numeric(10, 2),
        default=0.0,
        nullable=False,
    )

    planned_hours = Column(
        Numeric(10, 2),
        default=0.0,
        nullable=False,
    )

    downtime_hours = Column(
        Numeric(10, 2),
        default=0.0,
        nullable=False,
    )

    output_units = Column(
        Integer,
        default=0,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=tehran_now,
    )

    updated_at = Column(
        DateTime,
        default=tehran_now,
        onupdate=tehran_now,
    )

    equipment = relationship(
        "Equipment",
        backref="production_logs",
    )


# ============================================================================
# EQUIPMENT
# ============================================================================

class Equipment(Base):

    __tablename__ = "equipment"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    code = Column(
        Unicode(50),
        unique=True,
        nullable=False,
        index=True,
    )

    name = Column(
        Unicode(100),
        nullable=False,
    )

    category = Column(
        Unicode(50),
        nullable=False,
        index=True,
    )

    manufacturer = Column(
        Unicode(100),
        nullable=True,
    )

    model = Column(
        Unicode(100),
        nullable=True,
    )

    serial_number = Column(
        Unicode(100),
        nullable=True,
    )

    location = Column(
        Unicode(100),
        nullable=False,
        index=True,
    )

    installation_date = Column(
        DateTime,
        nullable=True,
    )

    status = Column(
        Unicode(20),
        default=EquipmentStatus.OPERATIONAL.value,
        nullable=False,
        index=True,
    )

    criticality_level = Column(
        Unicode(20),
        default=EquipmentCriticality.MEDIUM.value,
        nullable=False,
        index=True,
    )

    specifications = Column(
        UnicodeText,
        nullable=True,
    )

    notes = Column(
        UnicodeText,
        nullable=True,
    )

    length = Column(
        Float,
        nullable=True,
    )

    width = Column(
        Float,
        nullable=True,
    )

    diameter = Column(
        Float,
        nullable=True,
    )

    height = Column(
        Float,
        nullable=True,
    )

    volume = Column(
        Float,
        nullable=True,
    )

    weight = Column(
        Float,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=tehran_now,
    )

    updated_at = Column(
        DateTime,
        default=tehran_now,
        onupdate=tehran_now,
    )

    pm_schedules = relationship(
        "PMSchedule",
        back_populates="equipment",
    )

    inspection_templates = relationship(
        "InspectionTemplate",
        back_populates="equipment",
    )

    inspections = relationship(
        "Inspection",
        back_populates="equipment",
    )

    def __repr__(self):
        return (
            f"<Equipment "
            f"{self.code} - "
            f"{self.name}>"
        )


# ============================================================================
# PM SCHEDULE
# ============================================================================

class PMSchedule(Base):

    __tablename__ = "pm_schedules"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    title = Column(
        Unicode(150),
        nullable=False,
    )

    equipment_id = Column(
        Integer,
        ForeignKey("equipment.id"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------------
    # LEGACY USER TECHNICIAN
    #
    # Existing historical data remains valid.
    # ------------------------------------------------------------------------

    technician_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    # ------------------------------------------------------------------------
    # NEW DEPARTMENT
    #
    # Nullable so all six existing PM records remain valid.
    # ------------------------------------------------------------------------

    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=True,
        index=True,
    )

    frequency = Column(
        Unicode(20),
        nullable=False,
        default=PMFrequency.MONTHLY.value,
    )

    interval_days = Column(
        Integer,
        nullable=False,
        default=30,
    )

    last_done = Column(
        DateTime,
        nullable=True,
    )

    next_due = Column(
        DateTime,
        nullable=True,
        index=True,
    )

    checklist = Column(
        UnicodeText,
        nullable=True,
    )

    estimated_duration = Column(
        Integer,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    notes = Column(
        UnicodeText,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=tehran_now,
    )

    updated_at = Column(
        DateTime,
        default=tehran_now,
        onupdate=tehran_now,
    )

    parts_required = Column(
        UnicodeText,
        nullable=True,
    )

    # ------------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------------

    equipment = relationship(
        "Equipment",
        back_populates="pm_schedules",
    )

    technician = relationship(
        "User",
        back_populates="pm_schedules",
    )

    department = relationship(
        "Department",
        back_populates="pm_schedules",
    )

    __table_args__ = (
        Index(
            "ix_pm_schedules_active_due",
            "is_active",
            "next_due",
        ),
    )

    def __repr__(self):
        return (
            f"<PMSchedule "
            f"{self.title} - "
            f"{self.frequency}>"
        )


# ============================================================================
# INSPECTION TEMPLATE
# ============================================================================

class InspectionTemplate(Base):

    __tablename__ = "inspection_templates"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        Unicode(200),
        nullable=False,
    )

    description = Column(
        UnicodeText,
        nullable=True,
    )

    equipment_id = Column(
        Integer,
        ForeignKey("equipment.id"),
        nullable=True,
        index=True,
    )

    frequency = Column(
        Unicode(50),
        nullable=False,
        default=InspectionFrequency.MONTHLY.value,
        index=True,
    )

    estimated_duration_minutes = Column(
        Integer,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=tehran_now,
    )

    updated_at = Column(
        DateTime,
        default=tehran_now,
        onupdate=tehran_now,
    )

    equipment = relationship(
        "Equipment",
        back_populates="inspection_templates",
    )

    checkpoints = relationship(
        "InspectionCheckpoint",
        back_populates="template",
        cascade="all, delete-orphan",
    )

    inspections = relationship(
        "Inspection",
        back_populates="template",
    )

    __table_args__ = (
        Index(
            "ix_inspection_templates_active_equipment",
            "is_active",
            "equipment_id",
        ),
    )

    def __repr__(self):
        return (
            f"<InspectionTemplate "
            f"{self.name}>"
        )


# ============================================================================
# INSPECTION CHECKPOINT
# ============================================================================

class InspectionCheckpoint(Base):

    __tablename__ = "inspection_checkpoints"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    template_id = Column(
        Integer,
        ForeignKey("inspection_templates.id"),
        nullable=False,
        index=True,
    )

    title = Column(
        Unicode(200),
        nullable=False,
    )

    description = Column(
        UnicodeText,
        nullable=True,
    )

    checkpoint_type = Column(
        Unicode(50),
        nullable=False,
        default=CheckpointType.VISUAL.value,
    )

    order_number = Column(
        Integer,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=tehran_now,
    )

    template = relationship(
        "InspectionTemplate",
        back_populates="checkpoints",
    )

    results = relationship(
        "InspectionResult",
        back_populates="checkpoint",
    )

    __table_args__ = (
        Index(
            "ix_inspection_checkpoints_template_order",
            "template_id",
            "order_number",
        ),
    )

    def __repr__(self):
        return (
            f"<InspectionCheckpoint "
            f"{self.title}>"
        )


# ============================================================================
# INSPECTION
# ============================================================================

class Inspection(Base):

    __tablename__ = "inspections"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    template_id = Column(
        Integer,
        ForeignKey("inspection_templates.id"),
        nullable=False,
        index=True,
    )

    equipment_id = Column(
        Integer,
        ForeignKey("equipment.id"),
        nullable=False,
        index=True,
    )

    inspector_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    started_at = Column(
        DateTime,
        default=tehran_now,
        index=True,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    status = Column(
        Unicode(50),
        default=InspectionStatus.IN_PROGRESS.value,
        nullable=False,
        index=True,
    )

    overall_result = Column(
        Unicode(50),
        nullable=True,
    )

    notes = Column(
        UnicodeText,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=tehran_now,
    )

    template = relationship(
        "InspectionTemplate",
        back_populates="inspections",
    )

    equipment = relationship(
        "Equipment",
        back_populates="inspections",
    )

    inspector = relationship(
        "User",
        back_populates="inspections",
    )

    results = relationship(
        "InspectionResult",
        back_populates="inspection",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_inspections_status_started",
            "status",
            "started_at",
        ),

        Index(
            "ix_inspections_equipment_status",
            "equipment_id",
            "status",
        ),
    )

    def __repr__(self):
        return (
            f"<Inspection "
            f"{self.id} - "
            f"{self.status}>"
        )


# ============================================================================
# INSPECTION RESULT
# ============================================================================

class InspectionResult(Base):

    __tablename__ = "inspection_results"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    inspection_id = Column(
        Integer,
        ForeignKey("inspections.id"),
        nullable=False,
        index=True,
    )

    checkpoint_id = Column(
        Integer,
        ForeignKey("inspection_checkpoints.id"),
        nullable=False,
        index=True,
    )

    result = Column(
        Unicode(50),
        nullable=False,
    )

    comment = Column(
        UnicodeText,
        nullable=True,
    )

    recorded_at = Column(
        DateTime,
        default=tehran_now,
    )

    inspection = relationship(
        "Inspection",
        back_populates="results",
    )

    checkpoint = relationship(
        "InspectionCheckpoint",
        back_populates="results",
    )

    __table_args__ = (
        Index(
            "ix_inspection_results_inspection_checkpoint",
            "inspection_id",
            "checkpoint_id",
        ),
    )

    def __repr__(self):
        return (
            f"<InspectionResult "
            f"{self.result}>"
        )


# ============================================================================
# SPARE PART
# ============================================================================

class SparePart(Base):

    __tablename__ = "spare_parts"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    part_number = Column(
        Unicode(100),
        unique=True,
        nullable=False,
        index=True,
    )

    name = Column(
        Unicode(200),
        nullable=False,
    )

    description = Column(
        UnicodeText,
        nullable=True,
    )

    category = Column(
        Unicode(100),
        nullable=True,
        index=True,
    )

    unit = Column(
        Unicode(20),
        nullable=True,
    )

    min_stock = Column(
        Integer,
        default=0,
        nullable=False,
    )

    current_stock = Column(
        Integer,
        default=0,
        nullable=False,
    )

    unit_price = Column(
        Numeric(10, 2),
        default=0.0,
        nullable=False,
    )

    location = Column(
        Unicode(100),
        nullable=True,
    )

    supplier = Column(
        Unicode(200),
        nullable=True,
    )

    equipment_codes = Column(
        UnicodeText,
        nullable=True,
    )

    notes = Column(
        UnicodeText,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=tehran_now,
    )

    updated_at = Column(
        DateTime,
        default=tehran_now,
        onupdate=tehran_now,
    )

    transactions = relationship(
        "SparePartTransaction",
        back_populates="part",
        cascade="all, delete-orphan",
    )


# ============================================================================
# SETTINGS
# ============================================================================

class Settings(Base):

    __tablename__ = "settings"

    id = Column(
        Integer,
        primary_key=True,
    )

    key = Column(
        Unicode(100),
        unique=True,
        nullable=False,
    )

    value = Column(
        UnicodeText,
        nullable=True,
    )

    updated_at = Column(
        DateTime,
        default=tehran_now,
        onupdate=tehran_now,
    )


# ============================================================================
# ACTIVITY LOG
# ============================================================================

class ActivityLog(Base):

    __tablename__ = "activity_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    username = Column(
        Unicode(50),
        nullable=False,
    )

    action = Column(
        Unicode(50),
        nullable=False,
    )

    entity_type = Column(
        Unicode(50),
        nullable=False,
    )

    entity_id = Column(
        Integer,
        nullable=True,
    )

    details = Column(
        UnicodeText,
        nullable=True,
    )

    ip_address = Column(
        Unicode(45),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=tehran_now,
        index=True,
    )

    user = relationship(
        "User",
        backref="activity_logs",
    )


# ============================================================================
# SPARE PART TRANSACTION
# ============================================================================

class SparePartTransaction(Base):

    __tablename__ = "spare_part_transactions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    part_id = Column(
        Integer,
        ForeignKey("spare_parts.id"),
        nullable=False,
        index=True,
    )

    transaction_type = Column(
        Unicode(10),
        nullable=False,
    )

    quantity = Column(
        Integer,
        nullable=False,
    )

    reference = Column(
        Unicode(100),
        nullable=True,
    )

    notes = Column(
        UnicodeText,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=tehran_now,
        index=True,
    )

    batch_price = Column(
        Numeric(10, 2),
        nullable=True,
        default=0.0,
    )

    part = relationship(
        "SparePart",
        back_populates="transactions",
    )


# ============================================================================
# REPAIR REQUEST DOCUMENT
# ============================================================================
#
# Backs the existing "repair_request_documents" table used by
# database/repair_request_repository.py. The table already exists in the
# database — this ORM class was simply missing from models.py, which broke
# `from database.models import RepairRequestDocument`.
#

class RepairRequestDocument(Base):

    __tablename__ = "repair_request_documents"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    requesting_unit = Column(
        Unicode(200),
        nullable=False,
    )

    equipment_name = Column(
        Unicode(200),
        nullable=False,
    )

    breakdown_datetime = Column(
        DateTime,
        nullable=False,
        index=True,
    )

    operator_name = Column(
        Unicode(150),
        nullable=True,
    )

    requester_name = Column(
        Unicode(150),
        nullable=False,
    )

    request_description = Column(
        UnicodeText,
        nullable=True,
    )

    # ------------------------------------------------------------------------
    # EXECUTING DEPARTMENT
    #
    # The department that will perform the repair is selected when the
    # repair-request document is created. It remains separate from the
    # actual Personnel selection, which happens only at completion.
    # Nullable keeps historical rows valid until they are edited.
    # ------------------------------------------------------------------------

    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=True,
        index=True,
    )

    department = relationship(
        "Department",
        foreign_keys=[department_id],
        backref="repair_request_documents",
    )

    # ------------------------------------------------------------------------
    # LEGACY ASSIGNED PERSONNEL
    #
    # This is the person selected when the repair request is created.
    # It is intentionally separate from RepairRequestCompletion.personnel,
    # which records the person(s) who actually completed the repair later.
    # Nullable keeps all existing repair-request rows valid.
    # ------------------------------------------------------------------------

    assigned_personnel_id = Column(
        Integer,
        ForeignKey("personnel.id"),
        nullable=True,
        index=True,
    )

    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=tehran_now,
    )

    updated_at = Column(
        DateTime,
        nullable=True,
    )

    created_by = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        backref="repair_request_documents",
    )

    assigned_personnel = relationship(
        "Personnel",
        foreign_keys=[assigned_personnel_id],
        back_populates="assigned_repair_requests",
    )

    completion = relationship(
        "RepairRequestCompletion",
        back_populates="request",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<RepairRequestDocument "
            f"{self.id} - "
            f"{self.equipment_name}>"
        )


# ============================================================================
# REPAIR REQUEST COMPLETION
# ============================================================================

class RepairRequestCompletion(Base):
    __tablename__ = "repair_request_completions"

    id = Column(Integer, primary_key=True, index=True)

    repair_request_id = Column(
        Integer,
        ForeignKey("repair_request_documents.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    completion_datetime = Column(
        DateTime,
        nullable=False,
        index=True,
    )

    finish_notes = Column(UnicodeText, nullable=True)
    manual_cost = Column(Numeric(18, 2), default=0.0, nullable=False)
    cost_description = Column(UnicodeText, nullable=True)
    delay_minutes = Column(Integer, nullable=True)
    delay_reason = Column(UnicodeText, nullable=True)

    completed_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime, default=tehran_now)

    request = relationship(
        "RepairRequestDocument",
        back_populates="completion",
    )

    personnel = relationship(
        "Personnel",
        secondary="repair_request_completers",
        back_populates="completed_repair_completions",
    )

    completed_by_user = relationship(
        "User",
        foreign_keys=[completed_by_user_id],
    )

    def __repr__(self):
        return (
            f"<RepairRequestCompletion "
            f"{self.id} - request={self.repair_request_id}>"
        )


# ============================================================================
# ROLE PERMISSIONS
# ============================================================================

class RolePermissions(Base):

    __tablename__ = "role_permissions"

    __table_args__ = {
        "schema": "dbo"
    }

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    role_name = Column(
        Unicode(50),
        unique=True,
        nullable=False,
        index=True,
    )

    permissions_json = Column(
        UnicodeText,
        nullable=True,
    )

    def __repr__(self):
        return (
            f"<RolePermissions "
            f"{self.role_name}>"
        )


# ============================================================================
# WORK ORDER MODEL
# ============================================================================
#
# IMPORTANT:
#
# WorkOrder lives in database/work_order.py.
#
# We import it ONLY after every model in this file has been declared.
#
# database/work_order.py imports Base and work_order_technicians from this
# module, so this ordering avoids the circular-import problem.
#


from database.work_order import WorkOrder  # noqa: E402,F401  (registers the mapper; must stay last)
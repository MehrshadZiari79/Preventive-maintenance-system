# database/work_order.py
"""
PM System - Work Order ORM Model
================================

FINAL WORKFLOW
--------------

WORK ORDER CREATION
-------------------
When a Work Order is created:

    - Equipment is selected.
    - Department is selected.
    - Personnel is NOT selected.

The existing application User fields remain available because they are
part of the historical/legacy workflow.

WORK ORDER COMPLETION
---------------------
When the actual work is finished:

    Work Order Department
            ↓
    Personnel belonging to that Department
            ↓
    Personnel selected as completer(s)

The current models.py uses the association table:

    work_order_completers

This keeps Personnel separate from application Users and preserves the
existing User-based technician relationships.

LEGACY COMPATIBILITY
--------------------
The following existing fields are intentionally preserved:

    technician_id
    supervisor_id
    operator_id
    technicians

Existing Work Orders and their historical User assignments therefore remain
readable after the migration.

IMPORTANT
---------
This file defines the ORM model only.

It does NOT:
    - create tables
    - alter tables
    - migrate data
    - delete anything
"""

import enum

from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    Index,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy import (
    Unicode,
    UnicodeText,
)
from sqlalchemy.orm import relationship

from database.models import (
    Base,
    work_order_technicians,
)
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


# ============================================================================
# ENUMS
# ============================================================================

class WorkOrderType(enum.Enum):
    PREVENTIVE = "preventive"
    CORRECTIVE = "corrective"
    EMERGENCY = "emergency"
    INSPECTION = "inspection"
    PM = "pm"


class WorkOrderStatus(enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    FINISH_REQUESTED = "finish_requested"
    COMPLETED = "completed"
    APPROVED = "approved"
    REJECTED = "rejected"


class WorkOrderPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ============================================================================
# WORK ORDER
# ============================================================================

class WorkOrder(Base):
    __tablename__ = "work_orders"

    # =========================================================================
    # IDENTITY
    # =========================================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # =========================================================================
    # EQUIPMENT / PM
    # =========================================================================

    equipment_id = Column(
        Integer,
        ForeignKey("equipment.id"),
        nullable=False,
        index=True,
    )

    schedule_id = Column(
        Integer,
        ForeignKey("pm_schedules.id"),
        nullable=True,
        index=True,
    )

    # =========================================================================
    # PARENT / CHILD WORK ORDERS
    # =========================================================================

    parent_work_order_id = Column(
        Integer,
        ForeignKey("work_orders.id"),
        nullable=True,
    )

    root_parent_id = Column(
        Integer,
        ForeignKey("work_orders.id"),
        nullable=True,
    )

    # =========================================================================
    # CLASSIFICATION
    # =========================================================================

    type = Column(
        SAEnum(WorkOrderType),
        nullable=False,
        default=WorkOrderType.CORRECTIVE,
    )

    status = Column(
        SAEnum(WorkOrderStatus),
        nullable=False,
        default=WorkOrderStatus.PENDING,
        index=True,
    )

    priority = Column(
        SAEnum(WorkOrderPriority),
        nullable=False,
        default=WorkOrderPriority.MEDIUM,
    )

    # =========================================================================
    # LEGACY / EXISTING USER-BASED ASSIGNMENTS
    # =========================================================================
    #
    # IMPORTANT:
    # These are preserved exactly for existing application behavior and
    # historical data.
    #
    # User != Personnel.
    #
    # User:
    #     Application/login account.
    #
    # Personnel:
    #     Actual maintenance worker.
    #
    # New workflow does NOT replace or delete these columns.
    #

    technician_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    supervisor_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    operator_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    # =========================================================================
    # NEW DEPARTMENT
    # =========================================================================
    #
    # Selected when the Work Order is created.
    #
    # NULL is intentional because old Work Orders were created before the
    # Department workflow existed.
    #

    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=True,
        index=True,
    )

    # =========================================================================
    # EMERGENCY / FAILURE INFORMATION
    # =========================================================================

    emergency_reported_by = Column(
        Unicode(100),
        nullable=True,
    )

    failure_report_time = Column(
        DateTime,
        nullable=True,
    )

    operator_notes = Column(
        UnicodeText,
        nullable=True,
    )

    operator_signature = Column(
        UnicodeText,
        nullable=True,
    )

    # =========================================================================
    # MAIN WORK ORDER INFORMATION
    # =========================================================================

    title = Column(
        Unicode(200),
        nullable=False,
    )

    description = Column(
        UnicodeText,
        nullable=True,
    )

    parts_used = Column(
        UnicodeText,
        nullable=True,
    )

    # =========================================================================
    # COST
    # =========================================================================

    manual_cost = Column(
        Numeric(18, 2),
        default=0.0,
        nullable=False,
    )

    cost_description = Column(
        UnicodeText,
        nullable=True,
    )

    # =========================================================================
    # SCHEDULING
    # =========================================================================

    scheduled_date = Column(
        DateTime,
        nullable=True,
        index=True,
    )

    deadline = Column(
        DateTime,
        nullable=True,
        index=True,
    )

    start_time = Column(
        DateTime,
        nullable=True,
    )

    end_time = Column(
        DateTime,
        nullable=True,
    )

    # =========================================================================
    # DELAY
    # =========================================================================

    delay_minutes = Column(
        Integer,
        nullable=True,
    )

    delay_reason = Column(
        UnicodeText,
        nullable=True,
    )

    # =========================================================================
    # SUPERVISOR / ATTACHMENTS
    # =========================================================================

    supervisor_notes = Column(
        UnicodeText,
        nullable=True,
    )

    attachments = Column(
        UnicodeText,
        nullable=True,
    )

    # =========================================================================
    # AUDIT
    # =========================================================================

    created_at = Column(
        DateTime,
        default=tehran_now,
    )

    updated_at = Column(
        DateTime,
        default=tehran_now,
        onupdate=tehran_now,
    )

    # =========================================================================
    # RELATIONSHIPS
    # =========================================================================

    # -------------------------------------------------------------------------
    # Equipment
    # -------------------------------------------------------------------------

    equipment = relationship(
        "Equipment",
        backref="work_orders",
    )

    # -------------------------------------------------------------------------
    # Legacy User relationships
    # -------------------------------------------------------------------------

    technician = relationship(
        "User",
        foreign_keys=[technician_id],
        backref="assigned_work_orders",
    )

    supervisor = relationship(
        "User",
        foreign_keys=[supervisor_id],
        backref="supervised_work_orders",
    )

    operator = relationship(
        "User",
        foreign_keys=[operator_id],
        backref="operator_work_orders",
    )

    # -------------------------------------------------------------------------
    # PM Schedule
    # -------------------------------------------------------------------------

    schedule = relationship(
        "PMSchedule",
        backref="work_orders",
    )

    # -------------------------------------------------------------------------
    # Department
    # -------------------------------------------------------------------------
    #
    # New workflow:
    #
    #       WorkOrder.department
    #                 ↓
    #       Department.personnel
    #

    department = relationship(
        "Department",
        foreign_keys=[department_id],
        back_populates="work_orders",
    )

    # -------------------------------------------------------------------------
    # Personnel completion
    # -------------------------------------------------------------------------
    #
    # IMPORTANT:
    #
    # The latest models.py defines:
    #
    #     work_order_completers
    #
    # Therefore the ORM relationship must use "completers".
    #
    # This preserves the current schema design and allows the application
    # to record the actual Personnel who performed the work.
    #

    completers = relationship(
        "Personnel",
        secondary="work_order_completers",
        back_populates="completed_work_orders",
    )

    # -------------------------------------------------------------------------
    # Parent / child
    # -------------------------------------------------------------------------

    parent = relationship(
        "WorkOrder",
        remote_side=[id],
        foreign_keys=[parent_work_order_id],
        backref="children",
    )

    root_parent = relationship(
        "WorkOrder",
        remote_side=[id],
        foreign_keys=[root_parent_id],
    )

    # -------------------------------------------------------------------------
    # Existing many-to-many User technicians
    # -------------------------------------------------------------------------
    #
    # Kept exactly for old Work Orders and existing application behavior.
    #

    technicians = relationship(
        "User",
        secondary=work_order_technicians,
        backref="additional_work_orders",
    )

    # =========================================================================
    # TABLE INDEXES / CONSTRAINTS
    # =========================================================================

    __table_args__ = (
        # Existing/general indexes
        Index(
            "ix_work_orders_status_scheduled",
            "status",
            "scheduled_date",
        ),

        Index(
            "ix_work_orders_equipment_status",
            "equipment_id",
            "status",
        ),

        # New Department lookup
        Index(
            "ix_work_orders_department",
            "department_id",
        ),

        # Existing PM schedule/date uniqueness
        UniqueConstraint(
            "schedule_id",
            "scheduled_date",
            name="uq_wo_schedule_date",
        ),
    )

    # =========================================================================
    # COMPATIBILITY HELPERS
    # =========================================================================

    @property
    def completed_by_personnel(self):
        """
        Compatibility helper for code that expects a single Personnel.

        New storage uses `completers`, because the latest database model uses
        the `work_order_completers` association table.

        For the current application workflow, normally zero or one Personnel
        will be selected.

        Returns:
            Personnel | None
        """

        try:

            if not self.completers:
                return None

            return self.completers[0]

        except Exception:
            return None

    @property
    def completed_personnel(self):
        """
        Return all Personnel who completed this Work Order.

        This is the canonical compatibility-friendly collection for the
        many-to-many work_order_completers association.
        """
        try:
            return list(self.completers or [])
        except Exception:
            return []

    @property
    def completed_by_personnel_id(self):
        """
        Compatibility read helper.

        This does NOT create a database column.

        It returns the first Personnel ID from the current completers
        relationship so older read/display code can continue working while
        repositories are being finalized around the new association-table
        workflow.

        Returns:
            int | None
        """

        personnel = self.completed_by_personnel

        if personnel is None:
            return None

        return getattr(
            personnel,
            "id",
            None,
        )

    # =========================================================================
    # REPRESENTATION
    # =========================================================================

    def __repr__(self):
        return (
            f"<WorkOrder "
            f"{self.id} - "
            f"{self.title}>"
        )


# ============================================================================
# Older versions titled automatic PM work orders with a GREGORIAN date
# («[A-PM] ... 2026-10-21»).  Show those titles with the Jalali date
# everywhere (lists, reports, PDF/Excel) without rewriting the database:
# the converted title is set as the *loaded* value, so it is never written
# back unless the work order is edited and saved.
# ============================================================================

from sqlalchemy import event as _sa_event
from sqlalchemy.orm.attributes import set_committed_value as _set_committed


def _jalali_auto_title(target, *_args):
    try:
        title = target.__dict__.get("title")
        if title and "[A-PM]" in title:
            from utils.date_helpers import jalalize_text_dates
            fixed = jalalize_text_dates(title)
            if fixed != title:
                _set_committed(target, "title", fixed)
    except Exception:
        pass


_sa_event.listen(WorkOrder, "load", _jalali_auto_title)
_sa_event.listen(WorkOrder, "refresh", _jalali_auto_title)

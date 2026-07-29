# database/work_order.py
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Enum as SAEnum, Index, Numeric, UniqueConstraint
from sqlalchemy import Unicode, UnicodeText
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database.models import Base, work_order_technicians


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


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False, index=True)
    schedule_id = Column(Integer, ForeignKey("pm_schedules.id"), nullable=True)
    parent_work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True)
    root_parent_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True)

    type = Column(SAEnum(WorkOrderType), nullable=False, default=WorkOrderType.CORRECTIVE)
    status = Column(SAEnum(WorkOrderStatus), nullable=False, default=WorkOrderStatus.PENDING, index=True)
    priority = Column(SAEnum(WorkOrderPriority), nullable=False, default=WorkOrderPriority.MEDIUM)

    technician_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    supervisor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    emergency_reported_by = Column(Unicode(100), nullable=True)

    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    failure_report_time = Column(DateTime, nullable=True)
    operator_notes = Column(UnicodeText, nullable=True)
    operator_signature = Column(UnicodeText, nullable=True)

    title = Column(Unicode(200), nullable=False)
    description = Column(UnicodeText, nullable=True)
    parts_used = Column(UnicodeText, nullable=True)

    manual_cost = Column(Numeric(18, 2), default=0.0, nullable=False)
    cost_description = Column(UnicodeText, nullable=True)

    scheduled_date = Column(DateTime, nullable=True, index=True)
    deadline = Column(DateTime, nullable=True, index=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

    # --- New delay fields ---
    delay_minutes = Column(Integer, nullable=True)
    delay_reason = Column(UnicodeText, nullable=True)

    supervisor_notes = Column(UnicodeText, nullable=True)
    attachments = Column(UnicodeText, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    equipment = relationship("Equipment", backref="work_orders")
    technician = relationship("User", foreign_keys=[technician_id], backref="assigned_work_orders")
    supervisor = relationship("User", foreign_keys=[supervisor_id], backref="supervised_work_orders")
    operator = relationship("User", foreign_keys=[operator_id], backref="operator_work_orders")
    schedule = relationship("PMSchedule", backref="work_orders")
    parent = relationship("WorkOrder", remote_side=[id], foreign_keys=[parent_work_order_id], backref="children")
    root_parent = relationship("WorkOrder", remote_side=[id], foreign_keys=[root_parent_id])

    technicians = relationship("User", secondary=work_order_technicians, backref="additional_work_orders")

    __table_args__ = (
        Index("ix_work_orders_status_scheduled", "status", "scheduled_date"),
        Index("ix_work_orders_equipment_status", "equipment_id", "status"),
        UniqueConstraint("schedule_id", "scheduled_date", name="uq_wo_schedule_date"),
    )

    def __repr__(self):
        return f"<WorkOrder {self.id} - {self.title}>"
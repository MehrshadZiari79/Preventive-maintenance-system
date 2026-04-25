# database/work_order.py
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SAEnum, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database.db import Base


class WorkOrderType(enum.Enum):
    PREVENTIVE = "preventive"
    CORRECTIVE = "corrective"
    EMERGENCY = "emergency"          # added emergency type
    INSPECTION = "inspection"
    PM = "pm"


class WorkOrderStatus(enum.Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    APPROVED    = "approved"
    REJECTED    = "rejected"


class WorkOrderPriority(enum.Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    URGENT = "urgent"


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id           = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False, index=True)
    schedule_id  = Column(Integer, ForeignKey("pm_schedules.id"), nullable=True)

    type     = Column(SAEnum(WorkOrderType),     nullable=False, default=WorkOrderType.CORRECTIVE)
    status   = Column(SAEnum(WorkOrderStatus),   nullable=False, default=WorkOrderStatus.PENDING, index=True)
    priority = Column(SAEnum(WorkOrderPriority), nullable=False, default=WorkOrderPriority.MEDIUM)

    technician_id  = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    supervisor_id  = Column(Integer, ForeignKey("users.id"), nullable=True)

    # NEW FIELD for emergency work order origin
    emergency_reported_by = Column(String(100), nullable=True)   # full name or username of reporter

    operator_id        = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    failure_report_time = Column(DateTime, nullable=True)
    operator_notes     = Column(Text, nullable=True)
    operator_signature = Column(Text, nullable=True)

    title            = Column(String(200), nullable=False)
    description      = Column(Text, nullable=True)
    parts_used       = Column(Text, nullable=True)

    scheduled_date   = Column(DateTime, nullable=True, index=True)
    start_time       = Column(DateTime, nullable=True)
    end_time         = Column(DateTime, nullable=True)

    supervisor_notes = Column(Text, nullable=True)
    attachments      = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    equipment  = relationship("Equipment", backref="work_orders")
    technician = relationship("User", foreign_keys=[technician_id], backref="assigned_work_orders")
    supervisor = relationship("User", foreign_keys=[supervisor_id], backref="supervised_work_orders")
    operator   = relationship("User", foreign_keys=[operator_id], backref="operator_work_orders")
    schedule   = relationship("PMSchedule", backref="work_orders")

    __table_args__ = (
        Index("ix_work_orders_status_scheduled", "status", "scheduled_date"),
        Index("ix_work_orders_equipment_status", "equipment_id", "status"),
    )

    def __repr__(self):
        return f"<WorkOrder {self.id} - {self.title}>"
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SAEnum, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database.db import Base
from enum import Enum


class WorkOrderType(enum.Enum):
    PREVENTIVE = "preventive"   # PM scheduled maintenance
    CORRECTIVE = "corrective"   # breakdown / emergency repair
    INSPECTION = "inspection"   # routine inspection
    PM = "pm"  # Add this line



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

    equipment  = relationship("Equipment", backref="work_orders")
    technician = relationship("User", foreign_keys=[technician_id], backref="assigned_work_orders")
    supervisor = relationship("User", foreign_keys=[supervisor_id], backref="supervised_work_orders")
    schedule   = relationship("PMSchedule", backref="work_orders")

    # Composite index: most common filter combo (status + scheduled_date for overdue queries)
    __table_args__ = (
        Index("ix_work_orders_status_scheduled", "status", "scheduled_date"),
        Index("ix_work_orders_equipment_status", "equipment_id", "status"),
    )

    def __repr__(self):
        return f"<WorkOrder {self.id} - {self.title}>"
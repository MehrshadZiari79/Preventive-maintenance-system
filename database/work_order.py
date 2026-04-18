from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database.db import Base


class WorkOrderType(enum.Enum):
    PM = "pm"
    CORRECTIVE = "corrective"
    PREVENTIVE = "preventive"
    BREAKDOWN = "breakdown"
    INSPECTION = "inspection"


class WorkOrderStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    REJECTED = "rejected"


class WorkOrderPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    schedule_id = Column(Integer, ForeignKey("pm_schedules.id"), nullable=True)

    type = Column(SAEnum(WorkOrderType), nullable=False, default=WorkOrderType.CORRECTIVE)
    status = Column(SAEnum(WorkOrderStatus), default=WorkOrderStatus.PENDING, nullable=False)
    priority = Column(SAEnum(WorkOrderPriority), default=WorkOrderPriority.MEDIUM, nullable=False)

    technician_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    supervisor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    parts_used = Column(Text, nullable=True)

    scheduled_date = Column(DateTime, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

    supervisor_notes = Column(Text, nullable=True)
    attachments = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    equipment = relationship("Equipment", backref="work_orders")
    technician = relationship("User", foreign_keys=[technician_id], backref="assigned_work_orders")
    supervisor = relationship("User", foreign_keys=[supervisor_id], backref="supervised_work_orders")
    schedule = relationship("PMSchedule", backref="work_orders")

    def __repr__(self):
        return f"<WorkOrder {self.id} - {self.title}>"

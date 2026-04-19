from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
from database.db import Base


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

    # Composite index for the most common query: active schedules ordered by due date
    __table_args__ = (
        Index("ix_pm_schedules_active_due", "is_active", "next_due"),
    )

    def __repr__(self):
        return f"<PMSchedule {self.title} - {self.frequency}>"
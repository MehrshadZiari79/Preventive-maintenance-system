# schemas/inspection.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Checkpoint Schemas
class InspectionCheckpointBase(BaseModel):
    title: str
    description: Optional[str] = None
    checkpoint_type: str  # visual, measurement, functional, safety
    order_number: int


class InspectionCheckpointCreate(InspectionCheckpointBase):
    pass


class InspectionCheckpointUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    checkpoint_type: Optional[str] = None
    order_number: Optional[int] = None


class InspectionCheckpoint(InspectionCheckpointBase):
    id: int
    template_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Template Schemas
class InspectionTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    equipment_id: Optional[int] = None
    frequency: str  # daily, weekly, monthly, quarterly, yearly
    estimated_duration_minutes: Optional[int] = None
    is_active: bool = True


class InspectionTemplateCreate(InspectionTemplateBase):
    checkpoints: List[InspectionCheckpointCreate] = []


class InspectionTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    equipment_id: Optional[int] = None
    frequency: Optional[str] = None
    estimated_duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None


class InspectionTemplate(InspectionTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime
    checkpoints: List[InspectionCheckpoint] = []

    class Config:
        from_attributes = True


# Inspection Result Schemas
class InspectionResultBase(BaseModel):
    checkpoint_id: int
    result: str  # pass, fail, na
    comment: Optional[str] = None


class InspectionResultCreate(InspectionResultBase):
    inspection_id: int


class InspectionResult(InspectionResultBase):
    id: int
    inspection_id: int
    recorded_at: datetime

    class Config:
        from_attributes = True


# Inspection Schemas
class InspectionBase(BaseModel):
    template_id: int
    equipment_id: int
    inspector_id: int
    notes: Optional[str] = None


class InspectionCreate(InspectionBase):
    pass


class InspectionUpdate(BaseModel):
    status: Optional[str] = None
    overall_result: Optional[str] = None
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None


class Inspection(InspectionBase):
    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    overall_result: Optional[str] = None
    created_at: datetime
    results: List[InspectionResult] = []

    class Config:
        from_attributes = True

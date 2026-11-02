# database/machine_shift.py
"""
Shift log for machine hours (standard CMMS / OEE structure).

    machine_shift_logs       one row per equipment + date + shift
    machine_downtime_events  the stops inside that shift (from-to + reason)

The tables are created ONCE by deploy/add_machine_shift_tables.sql (after a
database backup). The application never creates or alters tables itself.
After every save the daily totals are also written to the existing
production_logs table, so dashboards / reports / OEE keep working unchanged.
"""

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Unicode,
)
from sqlalchemy.orm import relationship

from database.models import Base
from utils.date_helpers import tehran_now


# (code, Persian label, planned?)  - short list on purpose (best practice:
# at most ~8 unplanned categories, no catch-all "other"; details go in the
# free-text field).
DOWNTIME_CATEGORIES = [
    ("mechanical",          "مکانیکی",                         False),
    ("electrical",          "برقی و کنترل",                    False),
    ("utilities",           "تأسیسات (بخار، هوا، آب، برق)",    False),
    ("material",            "کمبود شیر / مواد / بسته‌بندی",     False),
    ("changeover",          "تعویض محصول / تنظیم",             False),
    ("process",             "فرآیند / کیفیت",                  False),
    ("operator",            "نیروی انسانی",                    False),
    ("cip",                 "شستشو (CIP)",                     True),
    ("planned_maintenance", "نت برنامه‌ریزی‌شده",              True),
    ("break",               "استراحت / جلسه",                  True),
    ("no_plan",             "بدون برنامه تولید",               True),
]
CATEGORY_LABEL = {code: label for code, label, _ in DOWNTIME_CATEGORIES}
CATEGORY_PLANNED = {code: planned for code, _, planned in DOWNTIME_CATEGORIES}


class MachineShiftLog(Base):
    __tablename__ = "machine_shift_logs"

    id = Column(Integer, primary_key=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False, index=True)
    log_date = Column(DateTime, nullable=False, index=True)        # day the shift started
    shift_name = Column(Unicode(30), nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    planned_stop_minutes = Column(Integer, nullable=False, default=0)
    unplanned_stop_minutes = Column(Integer, nullable=False, default=0)
    output_units = Column(Integer, nullable=True)
    notes = Column(Unicode(500), nullable=True)
    created_by = Column(Unicode(100), nullable=True)
    created_at = Column(DateTime, default=tehran_now)
    updated_at = Column(DateTime, default=tehran_now, onupdate=tehran_now)

    events = relationship(
        "MachineDowntimeEvent",
        back_populates="shift_log",
        cascade="all, delete-orphan",
        order_by="MachineDowntimeEvent.start_time",
    )


class MachineDowntimeEvent(Base):
    __tablename__ = "machine_downtime_events"

    id = Column(Integer, primary_key=True)
    shift_log_id = Column(Integer, ForeignKey("machine_shift_logs.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    category = Column(Unicode(30), nullable=False)
    is_planned = Column(Boolean, nullable=False, default=False)
    detail = Column(Unicode(300), nullable=True)
    created_at = Column(DateTime, default=tehran_now)

    shift_log = relationship("MachineShiftLog", back_populates="events")

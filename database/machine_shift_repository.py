# database/machine_shift_repository.py
"""
Data access for the machine-hours shift log.

save_sheet() writes, in ONE transaction:
  1. machine_shift_logs + machine_downtime_events for the date/shift, and
  2. the day's totals into production_logs (sum of all shifts of that day),
     so existing dashboards, reports and OEE keep working.

If the two shift tables have not been created yet (deploy script not run),
the repository works in "basic" mode: only production_logs is written (one
record per machine per day), stop reasons are not kept.
"""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta

from sqlalchemy import func, text

from database.machine_shift import (
    CATEGORY_PLANNED, MachineDowntimeEvent, MachineShiftLog,
)
from database.models import ProductionLog, Settings

SHIFTS_SETTING_KEY = "machine_hours.shifts"
DEFAULT_SHIFTS = [{"name": "شیفت روز", "start": "07:00", "end": "15:00"}]
BASIC_SHIFT_NAME = "کل روز"


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    return value


def _day_start(value):
    return datetime.combine(_day(value), time())


class MachineShiftRepository:
    _tables_ok = None          # cached per process

    def __init__(self, session_factory):
        self.Session = session_factory

    # ------------------------------------------------------------- feature

    def shift_tables_available(self, refresh=False):
        if MachineShiftRepository._tables_ok is not None and not refresh:
            return MachineShiftRepository._tables_ok
        session = self.Session()
        try:
            session.execute(text("SELECT COUNT(*) FROM machine_shift_logs WHERE 1 = 0"))
            session.execute(text("SELECT COUNT(*) FROM machine_downtime_events WHERE 1 = 0"))
            ok = True
        except Exception:
            session.rollback()
            ok = False
        finally:
            session.close()
        MachineShiftRepository._tables_ok = ok
        return ok

    # -------------------------------------------------------------- shifts

    def get_shifts(self):
        session = self.Session()
        try:
            row = session.query(Settings).filter(Settings.key == SHIFTS_SETTING_KEY).first()
            if row and row.value:
                data = json.loads(row.value)
                shifts = [s for s in data if s.get("name") and s.get("start") and s.get("end")]
                if shifts:
                    return shifts
        except Exception:
            session.rollback()
        finally:
            session.close()
        return [dict(s) for s in DEFAULT_SHIFTS]

    def save_shifts(self, shifts):
        session = self.Session()
        try:
            payload = json.dumps(shifts, ensure_ascii=False)
            row = session.query(Settings).filter(Settings.key == SHIFTS_SETTING_KEY).first()
            if row:
                row.value = payload
            else:
                session.add(Settings(key=SHIFTS_SETTING_KEY, value=payload))
            session.commit()
            return True, "شیفت‌ها ذخیره شد."
        except Exception as exc:
            session.rollback()
            return False, str(exc)
        finally:
            session.close()

    # --------------------------------------------------------------- read

    def load_sheet(self, day, shift_name):
        """
        {equipment_id: {"start","end","output","notes","events":[...],
                         "source": "shift"|"daily", "other_shifts": int}}
        "daily" = only an old one-per-day production_logs record exists.
        """
        start = _day_start(day)
        result = {}
        session = self.Session()
        try:
            if self.shift_tables_available():
                logs = (
                    session.query(MachineShiftLog)
                    .filter(MachineShiftLog.log_date == start)
                    .all()
                )
                per_eq_count = {}
                for log in logs:
                    per_eq_count[log.equipment_id] = per_eq_count.get(log.equipment_id, 0) + 1
                for log in logs:
                    if log.shift_name != shift_name:
                        continue
                    result[log.equipment_id] = {
                        "start": log.start_time,
                        "end": log.end_time,
                        "output": log.output_units,
                        "notes": log.notes or "",
                        "events": [
                            {"start": e.start_time, "end": e.end_time,
                             "category": e.category, "detail": e.detail or ""}
                            for e in log.events
                        ],
                        "source": "shift",
                        "other_shifts": per_eq_count.get(log.equipment_id, 1) - 1,
                    }
                with_shift = set(per_eq_count)
            else:
                with_shift = set()

            daily = (
                session.query(ProductionLog)
                .filter(ProductionLog.log_date >= start,
                        ProductionLog.log_date < start + timedelta(days=1))
                .all()
            )
            for p in daily:
                if p.equipment_id in result or p.equipment_id in with_shift:
                    continue
                result[p.equipment_id] = {
                    "start": None, "end": None,
                    "output": p.output_units,
                    "notes": "",
                    "events": [],
                    "source": "daily",
                    "daily": {
                        "planned": float(p.planned_hours or 0),
                        "operating": float(p.operating_hours or 0),
                        "downtime": float(p.downtime_hours or 0),
                    },
                    "other_shifts": 0,
                }
            return result
        finally:
            session.close()

    def has_shift_logs(self, equipment_id, day):
        if not self.shift_tables_available():
            return False
        session = self.Session()
        try:
            return session.query(MachineShiftLog.id).filter(
                MachineShiftLog.equipment_id == equipment_id,
                MachineShiftLog.log_date == _day_start(day),
            ).first() is not None
        finally:
            session.close()

    def downtime_pareto(self, start_day=None, end_day=None, equipment_id=None):
        """[(category, count, minutes)] largest first, for the period."""
        if not self.shift_tables_available():
            return []
        session = self.Session()
        try:
            q = (
                session.query(
                    MachineDowntimeEvent.category,
                    func.count(MachineDowntimeEvent.id),
                    func.sum(MachineDowntimeEvent.duration_minutes),
                )
                .join(MachineShiftLog, MachineShiftLog.id == MachineDowntimeEvent.shift_log_id)
            )
            if start_day:
                q = q.filter(MachineShiftLog.log_date >= _day_start(start_day))
            if end_day:
                q = q.filter(MachineShiftLog.log_date < _day_start(end_day) + timedelta(days=1))
            if equipment_id:
                q = q.filter(MachineShiftLog.equipment_id == equipment_id)
            rows = q.group_by(MachineDowntimeEvent.category).all()
            out = [(cat, int(cnt or 0), int(mins or 0)) for cat, cnt, mins in rows]
            return sorted(out, key=lambda r: r[2], reverse=True)
        finally:
            session.close()

    # -------------------------------------------------------------- write

    def save_sheet(self, day, shift_name, rows, user_name=""):
        """
        rows: {equipment_id: row or None}
           row = {"start": datetime, "end": datetime, "output": int|None,
                  "notes": str, "planned_stop": int, "unplanned_stop": int,
                  "events": [{"start": dt, "end": dt, "category": code, "detail": str}]}
           None = machine did not run in this shift -> delete its record.
        """
        if not rows:
            return True, "تغییری برای ذخیره وجود ندارد."
        if not self.shift_tables_available():
            return self._save_basic(day, rows)

        start = _day_start(day)
        session = self.Session()
        try:
            touched = set()
            for eq_id, row in rows.items():
                log = (
                    session.query(MachineShiftLog)
                    .filter(MachineShiftLog.equipment_id == eq_id,
                            MachineShiftLog.log_date == start,
                            MachineShiftLog.shift_name == shift_name)
                    .first()
                )
                touched.add(eq_id)
                if row is None:
                    if log is not None:
                        session.delete(log)
                    continue
                if log is None:
                    log = MachineShiftLog(equipment_id=eq_id, log_date=start,
                                          shift_name=shift_name, created_by=user_name or None)
                    session.add(log)
                log.start_time = row["start"]
                log.end_time = row["end"]
                log.output_units = row.get("output")
                log.notes = (row.get("notes") or "")[:500] or None
                log.planned_stop_minutes = int(row.get("planned_stop") or 0)
                log.unplanned_stop_minutes = int(row.get("unplanned_stop") or 0)
                log.events = [
                    MachineDowntimeEvent(
                        start_time=e["start"], end_time=e["end"],
                        duration_minutes=int(round((e["end"] - e["start"]).total_seconds() / 60)),
                        category=e["category"],
                        is_planned=bool(CATEGORY_PLANNED.get(e["category"], False)),
                        detail=(e.get("detail") or "")[:300] or None,
                    )
                    for e in row.get("events") or []
                ]
            session.flush()
            for eq_id in touched:
                self._rebuild_daily(session, eq_id, start)
            session.commit()
            return True, f"{len(rows)} ردیف ذخیره شد."
        except Exception as exc:
            session.rollback()
            return False, str(exc)
        finally:
            session.close()

    @staticmethod
    def _rebuild_daily(session, equipment_id, start):
        """production_logs(day) = sum of every shift of that machine on that day."""
        logs = (
            session.query(MachineShiftLog)
            .filter(MachineShiftLog.equipment_id == equipment_id,
                    MachineShiftLog.log_date == start)
            .all()
        )
        daily = (
            session.query(ProductionLog)
            .filter(ProductionLog.equipment_id == equipment_id,
                    ProductionLog.log_date >= start,
                    ProductionLog.log_date < start + timedelta(days=1))
            .first()
        )
        if not logs:
            if daily is not None:
                session.delete(daily)
            return
        planned = run = unplanned = 0.0
        output = 0
        for log in logs:
            if log.start_time is None or log.end_time is None:
                continue
            window = (log.end_time - log.start_time).total_seconds() / 60.0
            planned_prod = window - (log.planned_stop_minutes or 0)
            planned += planned_prod
            run += planned_prod - (log.unplanned_stop_minutes or 0)
            unplanned += log.unplanned_stop_minutes or 0
            output += int(log.output_units or 0)
        if daily is None:
            daily = ProductionLog(equipment_id=equipment_id, log_date=start)
            session.add(daily)
        daily.planned_hours = round(planned / 60.0, 2)
        daily.operating_hours = round(max(0.0, run) / 60.0, 2)
        daily.downtime_hours = round(unplanned / 60.0, 2)
        daily.output_units = output

    def _save_basic(self, day, rows):
        """Shift tables missing: one production_logs record per machine per day."""
        start = _day_start(day)
        session = self.Session()
        try:
            for eq_id, row in rows.items():
                daily = (
                    session.query(ProductionLog)
                    .filter(ProductionLog.equipment_id == eq_id,
                            ProductionLog.log_date >= start,
                            ProductionLog.log_date < start + timedelta(days=1))
                    .first()
                )
                if row is None:
                    if daily is not None:
                        session.delete(daily)
                    continue
                window = (row["end"] - row["start"]).total_seconds() / 60.0
                planned_prod = window - int(row.get("planned_stop") or 0)
                unplanned = int(row.get("unplanned_stop") or 0)
                if daily is None:
                    daily = ProductionLog(equipment_id=eq_id, log_date=start)
                    session.add(daily)
                daily.planned_hours = round(planned_prod / 60.0, 2)
                daily.operating_hours = round(max(0.0, planned_prod - unplanned) / 60.0, 2)
                daily.downtime_hours = round(unplanned / 60.0, 2)
                daily.output_units = int(row.get("output") or 0)
            session.commit()
            return True, f"{len(rows)} ردیف ذخیره شد."
        except Exception as exc:
            session.rollback()
            return False, str(exc)
        finally:
            session.close()

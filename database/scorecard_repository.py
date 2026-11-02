"""
Maintenance scorecard (Reports > «شاخص‌های استاندارد»).

Plant-level maintenance KPIs in the style of the SMRP Best Practice metrics,
computed only from data the system already records.  The same definitions
as the equipment-performance report are used, so numbers agree between tabs:

    failure          corrective / emergency work order created in the
                     period, except REJECTED
    MTTR             average (end - start) of finished corrective / emergency
                     work orders that have both times
    MTBF             operating hours / failures (production logs)
    availability     operating hours / planned hours (production logs)
    planned work %   finished preventive / PM / inspection work orders out of
                     all finished work orders (by finish time)
    PM compliance    taken from ReportRepository.get_schedule_compliance

Everything is aggregated in Python from a few narrow queries, so the code
runs unchanged on every SQL Server version the plant uses.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from database.models import (
    Equipment,
    Inspection,
    InspectionResult,
    PMSchedule,
    ProductionLog,
    RepairRequestCompletion,
    RepairRequestDocument,
    SparePart,
    SparePartTransaction,
)
from database.work_order import WorkOrder, WorkOrderStatus, WorkOrderType
from utils.date_helpers import tehran_now

DONE = (WorkOrderStatus.APPROVED, WorkOrderStatus.COMPLETED)
OPEN = (
    WorkOrderStatus.PENDING_APPROVAL,
    WorkOrderStatus.PENDING,
    WorkOrderStatus.IN_PROGRESS,
    WorkOrderStatus.FINISH_REQUESTED,
)
PLANNED_TYPES = (WorkOrderType.PREVENTIVE, WorkOrderType.PM, WorkOrderType.INSPECTION)
REACTIVE_TYPES = (WorkOrderType.CORRECTIVE, WorkOrderType.EMERGENCY)
REPEAT_WINDOW_DAYS = 30

# Common reference values (SMRP / industry practice).  Shown as guidance only.
TARGETS = {
    "planned_pct": (">=", 80.0),
    "emergency_pct": ("<=", 10.0),
    "pm_compliance": (">=", 90.0),
    "availability": (">=", 90.0),
    "repeat_pct": ("<=", 10.0),
    "backlog_old_pct": ("<=", 20.0),
    "inspection_pass": (">=", 95.0),
}


def _as_datetime(value, end=False):
    if value is None:
        return None
    if isinstance(value, datetime):
        value = value.date() if end else value
        if not end:
            return value
    if isinstance(value, date):
        base = datetime.combine(value, time())
        return base + timedelta(days=1) if end else base
    return value


def _hours(a, b):
    if not a or not b or b < a:
        return None
    return (b - a).total_seconds() / 3600.0


def _avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _pct(part, whole):
    return part * 100.0 / whole if whole else None


def _status(key, value):
    """'good' / 'bad' / None against the reference value."""
    if value is None or key not in TARGETS:
        return None
    op, ref = TARGETS[key]
    ok = value >= ref if op == ">=" else value <= ref
    return "good" if ok else "bad"


class ScorecardRepository:
    def __init__(self, session_factory):
        self.Session = session_factory

    def build(self, start_date=None, end_date=None, report_repo=None) -> dict:
        start = _as_datetime(start_date)
        end_excl = _as_datetime(end_date, end=True)
        now = tehran_now()
        session = self.Session()
        try:
            eq_names = {eid: name for eid, name in session.query(Equipment.id, Equipment.name)}

            def in_period(value):
                if value is None:
                    return False
                if start is not None and value < start:
                    return False
                if end_excl is not None and value >= end_excl:
                    return False
                return True

            # ---------------------------------------------------- work orders
            cols = (
                WorkOrder.id, WorkOrder.equipment_id, WorkOrder.type, WorkOrder.status,
                WorkOrder.priority, WorkOrder.created_at, WorkOrder.start_time,
                WorkOrder.end_time, WorkOrder.deadline, WorkOrder.manual_cost,
            )
            q = session.query(*cols)
            # created in the period, finished in the period, or still open
            rows = [
                r for r in q.all()
                if in_period(r.created_at) or in_period(r.end_time) or r.status in OPEN
            ]

            created = [r for r in rows if in_period(r.created_at)]
            finished = [r for r in rows if r.status in DONE and in_period(r.end_time)]
            failures = [
                r for r in created
                if r.type in REACTIVE_TYPES and r.status != WorkOrderStatus.REJECTED
            ]

            # work mix (finished work, by finish time)
            planned_done = sum(1 for r in finished if r.type in PLANNED_TYPES)
            emergency_done = sum(1 for r in finished if r.type == WorkOrderType.EMERGENCY)
            corrective_done = sum(1 for r in finished if r.type == WorkOrderType.CORRECTIVE)

            # response time (created -> start) for reactive work started in period
            response = [
                _hours(r.created_at, r.start_time)
                for r in rows
                if r.type in REACTIVE_TYPES and in_period(r.start_time)
            ]
            response_em = [
                _hours(r.created_at, r.start_time)
                for r in rows
                if r.type == WorkOrderType.EMERGENCY and in_period(r.start_time)
            ]

            # MTTR - finished reactive work with both times (created in period,
            # same population as the equipment report)
            repair_hours = [
                _hours(r.start_time, r.end_time)
                for r in created
                if r.type in REACTIVE_TYPES and r.status in DONE
            ]

            # production logs -> MTBF / availability
            op_hours = planned_hours = 0.0
            plq = session.query(
                ProductionLog.equipment_id, ProductionLog.log_date,
                ProductionLog.operating_hours, ProductionLog.planned_hours,
            )
            if start is not None:
                plq = plq.filter(ProductionLog.log_date >= start)
            if end_excl is not None:
                plq = plq.filter(ProductionLog.log_date < end_excl)
            for _eid, _d, op, pl in plq.all():
                op_hours += float(op or 0)
                planned_hours += float(pl or 0)
            availability = (
                max(0.0, min(100.0, op_hours / planned_hours * 100.0))
                if planned_hours > 0 else None
            )
            mtbf = op_hours / len(failures) if failures and op_hours else None

            # repeat failures: same equipment fails again within 30 days
            by_eq = defaultdict(list)
            for r in failures:
                by_eq[r.equipment_id].append(r.created_at)
            repeats = 0
            for times in by_eq.values():
                times.sort()
                for prev, cur in zip(times, times[1:]):
                    if (cur - prev).days < REPEAT_WINDOW_DAYS:
                        repeats += 1

            # bad actors: most failures in the period
            repair_by_eq = defaultdict(float)
            cost_by_eq = defaultdict(float)
            for r in created:
                if r.type in REACTIVE_TYPES and r.status in DONE:
                    h = _hours(r.start_time, r.end_time)
                    if h:
                        repair_by_eq[r.equipment_id] += h
                    cost_by_eq[r.equipment_id] += float(r.manual_cost or 0)
            bad_actors = sorted(
                (
                    {
                        "equipment": eq_names.get(eid, f"#{eid}"),
                        "failures": len(times),
                        "repeats": sum(
                            1 for a, b in zip(sorted(times), sorted(times)[1:])
                            if (b - a).days < REPEAT_WINDOW_DAYS
                        ),
                        "repair_hours": round(repair_by_eq.get(eid, 0.0), 1),
                        "cost": round(cost_by_eq.get(eid, 0.0)),
                    }
                    for eid, times in by_eq.items()
                ),
                key=lambda x: (-x["failures"], -x["repair_hours"]),
            )[:10]

            # ------------------------------------------------------- backlog
            open_rows = [r for r in rows if r.status in OPEN]
            buckets = {"0-7": 0, "8-30": 0, "31-90": 0, "90+": 0}
            for r in open_rows:
                age = (now - r.created_at).days if r.created_at else 0
                if age <= 7:
                    buckets["0-7"] += 1
                elif age <= 30:
                    buckets["8-30"] += 1
                elif age <= 90:
                    buckets["31-90"] += 1
                else:
                    buckets["90+"] += 1
            overdue_open = sum(1 for r in open_rows if r.deadline and r.deadline < now)
            status_counts = defaultdict(int)
            for r in open_rows:
                status_counts[r.status.name if r.status else ""] += 1
            old = buckets["31-90"] + buckets["90+"]

            # ---------------------------------------------------- PM program
            pm_rows = session.query(
                PMSchedule.id, PMSchedule.title, PMSchedule.equipment_id, PMSchedule.next_due,
            ).filter(PMSchedule.is_active == True).all()  # noqa: E712
            overdue_pms = sorted(
                (
                    {
                        "title": t or "",
                        "equipment": eq_names.get(eid, ""),
                        "next_due": nd,
                        "days_overdue": (now - nd).days,
                    }
                    for _id, t, eid, nd in pm_rows
                    if nd and nd < now
                ),
                key=lambda x: -x["days_overdue"],
            )
            due_14 = sum(1 for *_x, nd in pm_rows if nd and now <= nd <= now + timedelta(days=14))

            # ---------------------------------------------------- spare parts
            parts = session.query(
                SparePart.id, SparePart.part_number, SparePart.name,
                SparePart.current_stock, SparePart.min_stock, SparePart.unit_price,
            ).all()
            price = {p.id: float(p.unit_price or 0) for p in parts}
            stockouts = [p for p in parts if (p.current_stock or 0) <= 0]
            below_min = [
                p for p in parts
                if 0 < (p.current_stock or 0) <= (p.min_stock or 0)
            ]
            tq = session.query(
                SparePartTransaction.part_id, SparePartTransaction.quantity,
                SparePartTransaction.created_at,
            ).filter(SparePartTransaction.transaction_type == "OUT")
            if start is not None:
                tq = tq.filter(SparePartTransaction.created_at >= start)
            if end_excl is not None:
                tq = tq.filter(SparePartTransaction.created_at < end_excl)
            used_value = defaultdict(float)
            used_qty = defaultdict(float)
            for pid, qty, _c in tq.all():
                used_qty[pid] += float(qty or 0)
                used_value[pid] += float(qty or 0) * price.get(pid, 0.0)
            names = {p.id: f"{p.part_number} - {p.name}" for p in parts}
            top_parts = sorted(
                (
                    {"part": names.get(pid, f"#{pid}"), "quantity": used_qty[pid], "value": round(v)}
                    for pid, v in used_value.items()
                ),
                key=lambda x: -x["value"],
            )[:5]
            critical_parts = [
                {
                    "part": f"{p.part_number} - {p.name}",
                    "stock": p.current_stock or 0,
                    "min": p.min_stock or 0,
                }
                for p in sorted(stockouts + below_min, key=lambda p: (p.current_stock or 0))
            ][:10]

            # ---------------------------------------------------- inspections
            ins_q = session.query(Inspection.id, Inspection.status, Inspection.overall_result,
                                  Inspection.completed_at)
            ins_rows = [r for r in ins_q.all() if r.status == "completed" and in_period(r.completed_at)]
            ins_ids = [r.id for r in ins_rows]
            passed = failed = 0
            for chunk_start in range(0, len(ins_ids), 500):
                chunk = ins_ids[chunk_start:chunk_start + 500]
                for (res,) in session.query(InspectionResult.result).filter(
                        InspectionResult.inspection_id.in_(chunk)):
                    if res == "pass":
                        passed += 1
                    elif res == "fail":
                        failed += 1
            ins_failed = sum(1 for r in ins_rows if r.overall_result == "fail")

            # ------------------------------------------------ repair requests
            rr = session.query(
                RepairRequestDocument.id, RepairRequestDocument.breakdown_datetime,
                RepairRequestCompletion.completion_datetime,
            ).outerjoin(
                RepairRequestCompletion,
                RepairRequestCompletion.repair_request_id == RepairRequestDocument.id,
            ).all()
            rr_period = [r for r in rr if in_period(r.breakdown_datetime)]
            rr_done = [r for r in rr_period if r.completion_datetime]
            rr_open = sum(1 for r in rr if not r.completion_datetime)

            # ------------------------------------------------- PM compliance
            compliance = None
            if report_repo is not None:
                try:
                    compliance = report_repo.get_schedule_compliance(start_date, end_date)
                except Exception:
                    compliance = None

            planned_pct = _pct(planned_done, len(finished))
            emergency_pct = _pct(emergency_done, len(finished))
            repeat_pct = _pct(repeats, len(failures))
            old_pct = _pct(old, len(open_rows))
            pass_rate = _pct(passed, passed + failed)
            pm_comp = compliance.get("compliance_rate") if compliance else None

            return {
                "period": {"start": start, "end": end_excl - timedelta(days=1) if end_excl else None},
                "kpis": [
                    # key, label, value, unit, hint
                    ("planned_pct", "کار برنامه‌ریزی‌شده", planned_pct, "%",
                     f"{planned_done} از {len(finished)} کار تمام‌شده (PM و بازرسی)"),
                    ("emergency_pct", "کار اضطراری", emergency_pct, "%",
                     f"{emergency_done} اضطراری، {corrective_done} اصلاحی"),
                    ("pm_compliance", "انطباق PM (به‌موقع)", pm_comp, "%",
                     (f"{compliance.get('on_time', 0)} به‌موقع از {compliance.get('total_tasks', 0)}"
                      if compliance else "—")),
                    ("availability", "دسترس‌پذیری تجهیزات", availability, "%",
                     f"{op_hours:,.0f} از {planned_hours:,.0f} ساعت برنامه‌ریزی‌شده"),
                    ("mtbf", "MTBF (میانگین زمان بین خرابی)", mtbf, "ساعت",
                     f"{len(failures)} خرابی در بازه"),
                    ("mttr", "MTTR (میانگین زمان تعمیر)", _avg(repair_hours), "ساعت",
                     f"{len([h for h in repair_hours if h is not None])} تعمیر زمان‌دار"),
                    ("response", "میانگین زمان واکنش", _avg(response), "ساعت",
                     "از ثبت تا شروع کار اصلاحی/اضطراری"),
                    ("response_em", "زمان واکنش اضطراری", _avg(response_em), "ساعت",
                     f"{len([h for h in response_em if h is not None])} کار اضطراری"),
                    ("repeat_pct", "خرابی تکراری (۳۰ روز)", repeat_pct, "%",
                     f"{repeats} خرابی تکراری"),
                    ("backlog_old_pct", "کارهای باز قدیمی‌تر از ۳۰ روز", old_pct, "%",
                     f"{old} از {len(open_rows)} کار باز"),
                    ("inspection_pass", "قبولی چک‌پوینت‌های بازرسی", pass_rate, "%",
                     f"{len(ins_rows)} بازرسی، {ins_failed} مردود"),
                ],
                "status": {
                    "planned_pct": _status("planned_pct", planned_pct),
                    "emergency_pct": _status("emergency_pct", emergency_pct),
                    "pm_compliance": _status("pm_compliance", pm_comp),
                    "availability": _status("availability", availability),
                    "repeat_pct": _status("repeat_pct", repeat_pct),
                    "backlog_old_pct": _status("backlog_old_pct", old_pct),
                    "inspection_pass": _status("inspection_pass", pass_rate),
                },
                "targets": TARGETS,
                "backlog": {
                    "total": len(open_rows),
                    "overdue": overdue_open,
                    "buckets": buckets,
                    "by_status": dict(status_counts),
                },
                "bad_actors": bad_actors,
                "pm": {
                    "active": len(pm_rows),
                    "overdue": overdue_pms[:10],
                    "overdue_count": len(overdue_pms),
                    "due_14": due_14,
                },
                "parts": {
                    "stockouts": len(stockouts),
                    "below_min": len(below_min),
                    "critical": critical_parts,
                    "top_used": top_parts,
                    "used_value": round(sum(used_value.values())),
                },
                "repair_requests": {
                    "in_period": len(rr_period),
                    "done": len(rr_done),
                    "open": rr_open,
                    "avg_hours": _avg(
                        [_hours(r.breakdown_datetime, r.completion_datetime) for r in rr_done]
                    ),
                },
            }
        finally:
            session.close()

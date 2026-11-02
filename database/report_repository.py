# database/report_repository.py
"""
PM System - Report Repository
=============================

REPORTING WORKFLOW
------------------

The application now distinguishes between:

    User
        Application/login account.

    Department
        Responsible maintenance department selected when a Work Order
        or PM is created.

    Personnel
        Actual maintenance worker who performed the work.

New Work Order workflow:

    Work Order
        equipment
        department
        scheduled date/time

Completion workflow:

    Work Order
        department
            ->
        Personnel belonging to that department
            ->
        completed_by_personnel_id
            ->
        finish request
            ->
        manager approval

IMPORTANT
---------
The legacy User/technician fields are intentionally NOT deleted.

Historical Work Orders may still contain:
    technician_id
    User-based technician assignments

New reports should use:
    completed_by_personnel_id

This repository does not perform migrations.
"""


from datetime import (
    datetime,
    timedelta,
)

from sqlalchemy import (
    func,
    and_,
    case,
    text,
)


# case(): SQLAlchemy 1.4+/2.x take the WHEN tuples positionally; 2.x rejects
# the old list form that v2.3 used (every KPI query raised ArgumentError).
# Keep working on 1.3 too, just in case the build environment is older.
import sqlalchemy as _sa
from sqlalchemy import case as _sa_case

if tuple(int(x) for x in _sa.__version__.split(".")[:2]) < (1, 4):
    def case(*whens, **kw):
        return _sa_case(list(whens), **kw)
else:
    case = _sa_case

from sqlalchemy.orm import (
    joinedload,
)

from database.work_order import (
    WorkOrder,
    WorkOrderStatus,
    WorkOrderType,
)

from database.models import (
    Equipment,
    Personnel,
    SparePart,
    SparePartTransaction,
    Inspection,
    InspectionResult,
    InspectionCheckpoint,
    ProductionLog,
)
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


# A work order counts as finished when it was approved, or (older records)
# completed under the previous workflow. v2.3 counted APPROVED only in most
# KPIs but APPROVED+COMPLETED in personnel performance.
DONE_STATUSES = [WorkOrderStatus.APPROVED, WorkOrderStatus.COMPLETED]


# Statuses whose end_time is final for schedule/PM compliance.
_FINISHED_FOR_COMPLIANCE = DONE_STATUSES + [WorkOrderStatus.FINISH_REQUESTED]
_OPEN_STATUSES = [
    WorkOrderStatus.PENDING_APPROVAL,
    WorkOrderStatus.PENDING,
    WorkOrderStatus.IN_PROGRESS,
]


def _compliance_outcome(wo, now):
    """
    'on_time', 'late' or None (not due yet / not applicable).

    * explicit deadline: finishing any time on the deadline DAY is on time
      (v2.3 compared with the deadline's 00:00 and marked same-day work late)
    * otherwise scheduled date + allowed days (مدت مجاز, days) of the PM
      schedule, at least 1 day (v2.3 used 0 days when the field was empty)
    * work that is still open after its deadline counts as LATE
      (v2.3 ignored it, so overdue PMs made compliance look better)
    """
    scheduled = wo.scheduled_date
    if scheduled is None:
        return None
    if wo.deadline is not None:
        deadline_day = wo.deadline.date() if hasattr(wo.deadline, "date") else wo.deadline
        limit = datetime.combine(deadline_day, datetime.min.time()) + timedelta(days=1)
    else:
        days = 0
        if wo.schedule_id and getattr(wo, "schedule", None) is not None:
            try:
                days = int(getattr(wo.schedule, "estimated_duration", 0) or 0)
            except (TypeError, ValueError):
                days = 0
        limit = scheduled + timedelta(days=max(1, days))

    end = wo.end_time if wo.status in _FINISHED_FOR_COMPLIANCE else None
    if end is not None:
        return "on_time" if end <= limit else "late"
    if wo.status in _OPEN_STATUSES and now > limit:
        return "late"
    return None


class ReportRepository:

    def __init__(
        self,
        session_factory,
    ):
        self.Session = session_factory

    # =========================================================================
    # DATE HELPERS
    # =========================================================================

    @staticmethod
    def _apply_created_date_filter(
        query,
        start_date=None,
        end_date=None,
        field=None,
    ):
        """
        Apply a safe date range.

        end_date is treated as the beginning of the next day when it is a
        datetime/date value. This prevents records later on the selected
        end date from being accidentally excluded.
        """

        if field is None:
            field = WorkOrder.created_at

        if start_date is not None:
            query = query.filter(
                field >= start_date
            )

        if end_date is not None:

            try:

                end_exclusive = (
                    end_date
                    + timedelta(days=1)
                )

            except Exception:

                end_exclusive = end_date

            query = query.filter(
                field < end_exclusive
            )

        return query

    # =========================================================================
    # KPI SUMMARY
    # =========================================================================

    def get_kpi_summary(
        self,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            wo_query = session.query(
                func.count(
                    WorkOrder.id
                ).label(
                    "total_wo"
                ),

                func.sum(
                    case(
                         
                            (
                                WorkOrder.status.in_(DONE_STATUSES),
                                1,
                            )
                         ,
                        else_=0,
                    )
                ).label(
                    "completed"
                ),

                func.sum(
                    case(
                         
                            (
                                WorkOrder.status
                                == WorkOrderStatus.PENDING,
                                1,
                            )
                         ,
                        else_=0,
                    )
                ).label(
                    "pending"
                ),

                func.sum(
                    case(
                         
                            (
                                WorkOrder.status
                                == WorkOrderStatus.IN_PROGRESS,
                                1,
                            )
                         ,
                        else_=0,
                    )
                ).label(
                    "in_progress"
                ),

                # every work order that is not finished, approved or rejected
                func.sum(
                    case(
                        (
                            WorkOrder.status.in_([
                                WorkOrderStatus.PENDING_APPROVAL,
                                WorkOrderStatus.PENDING,
                                WorkOrderStatus.IN_PROGRESS,
                                WorkOrderStatus.FINISH_REQUESTED,
                            ]),
                            1,
                        ),
                        else_=0,
                    )
                ).label(
                    "open_total"
                ),

                func.sum(
                    case(
                         
                            (
                                WorkOrder.type.in_(
                                    [
                                        WorkOrderType.PREVENTIVE,
                                        WorkOrderType.PM,
                                    ]
                                ),
                                1,
                            )
                         ,
                        else_=0,
                    )
                ).label(
                    "pm_total"
                ),

                func.sum(
                    case(
                         
                            (
                                WorkOrder.type
                                == WorkOrderType.CORRECTIVE,
                                1,
                            )
                         ,
                        else_=0,
                    )
                ).label(
                    "cm_total"
                ),

                func.sum(
                    case(
                         
                            (
                                WorkOrder.type
                                == WorkOrderType.EMERGENCY,
                                1,
                            )
                         ,
                        else_=0,
                    )
                ).label(
                    "emergency_total"
                ),
            )

            wo_query = (
                self._apply_created_date_filter(
                    wo_query,
                    start_date,
                    end_date,
                )
            )

            wo_stats = (
                wo_query.one()
            )

            # -----------------------------------------------------------------
            # Overdue
            # -----------------------------------------------------------------

            now = tehran_now()

            overdue_query = (
                session.query(
                    WorkOrder
                )
                .filter(
                    WorkOrder.status.in_(
                        [
                            WorkOrderStatus.PENDING,
                            WorkOrderStatus.IN_PROGRESS,
                        ]
                    ),
                    WorkOrder.scheduled_date.isnot(
                        None
                    ),
                    WorkOrder.scheduled_date < now,
                )
            )

            overdue_query = (
                self._apply_created_date_filter(
                    overdue_query,
                    start_date,
                    end_date,
                )
            )

            overdue = (
                overdue_query.count()
            )

            # -----------------------------------------------------------------
            # Average completion time
            # -----------------------------------------------------------------

            avg_time_query = (
                session.query(
                    func.avg(
                        (
                            func.datediff(
                                text("second"),
                                WorkOrder.start_time,
                                WorkOrder.end_time,
                            )
                        ) / 3600.0
                    )
                )
                .filter(
                    WorkOrder.status.in_(DONE_STATUSES),

                    WorkOrder.start_time.isnot(
                        None
                    ),

                    WorkOrder.end_time.isnot(
                        None
                    ),
                )
            )

            avg_time_query = (
                self._apply_created_date_filter(
                    avg_time_query,
                    start_date,
                    end_date,
                )
            )

            try:

                avg_time_raw = (
                    avg_time_query.scalar()
                    or 0
                )

            except Exception:

                # SQL Server / SQLAlchemy compatibility fallback.
                avg_time_sql = text(
                    """
                    SELECT AVG(
                        DATEDIFF(
                            second,
                            start_time,
                            end_time
                        ) / 3600.0
                    )
                    FROM work_orders
                    WHERE status IN ('APPROVED', 'COMPLETED')
                      AND start_time IS NOT NULL
                      AND end_time IS NOT NULL
                    """
                )

                params = {}

                if start_date:

                    avg_time_sql = text(
                        str(
                            avg_time_sql
                        ).rstrip()
                        + " AND created_at >= :start"
                    )

                    params[
                        "start"
                    ] = start_date

                if end_date:

                    end_exclusive = (
                        end_date
                        + timedelta(days=1)
                    )

                    avg_time_sql = text(
                        str(
                            avg_time_sql
                        ).rstrip()
                        + " AND created_at < :end"
                    )

                    params[
                        "end"
                    ] = end_exclusive

                avg_time_raw = (
                    session.execute(
                        avg_time_sql,
                        params,
                    ).scalar()
                    or 0
                )

            # -----------------------------------------------------------------
            # Equipment stats
            # -----------------------------------------------------------------

            eq_stats = (
                session.query(
                    func.count(
                        Equipment.id
                    ).label(
                        "total_eq"
                    ),

                    func.sum(
                        case(
                             
                                (
                                    Equipment.status
                                    == "operational",
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "operational"
                    ),
                )
                .one()
            )

            # -----------------------------------------------------------------
            # PM compliance
            # -----------------------------------------------------------------

            pm_query = (
                session.query(WorkOrder)
                .options(joinedload(WorkOrder.schedule))
                .filter(
                    WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM]),
                    WorkOrder.status != WorkOrderStatus.REJECTED,
                    WorkOrder.scheduled_date.isnot(None),
                )
            )
            pm_query = self._apply_created_date_filter(pm_query, start_date, end_date)

            on_time_pm = 0
            pm_work_orders_total = 0
            for wo in pm_query.all():
                outcome = _compliance_outcome(wo, now)
                if outcome is None:
                    continue
                pm_work_orders_total += 1
                if outcome == "on_time":
                    on_time_pm += 1

            pm_compliance = (
                on_time_pm / pm_work_orders_total * 100
                if pm_work_orders_total else 0
            )

            return {
                "total_work_orders":
                    wo_stats.total_wo
                    or 0,

                "completed_work_orders":
                    wo_stats.completed
                    or 0,

                "pending_work_orders":
                    wo_stats.pending
                    or 0,

                "in_progress_work_orders":
                    wo_stats.in_progress
                    or 0,

                "emergency_work_orders":
                    wo_stats.emergency_total
                    or 0,

                "overdue_work_orders":
                    overdue,

                "total_equipment":
                    eq_stats.total_eq
                    or 0,

                "operational_equipment":
                    eq_stats.operational
                    or 0,

                "avg_completion_time_hours":
                    round(
                        float(
                            avg_time_raw
                            or 0
                        ),
                        2,
                    ),

                "pm_compliance_rate":
                    round(
                        pm_compliance,
                        2,
                    ),

                "cm_work_orders":
                    wo_stats.cm_total
                    or 0,

                "open_work_orders":
                    wo_stats.open_total
                    or 0,
            }

        finally:

            session.close()

    # =========================================================================
    # BACKLOG
    # =========================================================================

    def get_backlog_analysis(
        self,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            now = tehran_now()

            query = session.query(
                func.sum(
                    case(
                         
                            (
                                WorkOrder.status
                                == WorkOrderStatus.PENDING,
                                1,
                            )
                         ,
                        else_=0,
                    )
                ).label(
                    "pending"
                ),

                func.sum(
                    case(
                         
                            (
                                WorkOrder.status
                                == WorkOrderStatus.IN_PROGRESS,
                                1,
                            )
                         ,
                        else_=0,
                    )
                ).label(
                    "in_progress"
                ),

                func.sum(
                    case(
                         
                            (
                                and_(
                                    WorkOrder.status.in_(
                                        [
                                            WorkOrderStatus.PENDING,
                                            WorkOrderStatus.IN_PROGRESS,
                                        ]
                                    ),

                                    WorkOrder.scheduled_date.isnot(
                                        None
                                    ),

                                    WorkOrder.scheduled_date
                                    < now,
                                ),
                                1,
                            )
                         ,
                        else_=0,
                    )
                ).label(
                    "overdue"
                ),
            )

            query = (
                self._apply_created_date_filter(
                    query,
                    start_date,
                    end_date,
                )
            )

            row = query.one()

            pending = (
                row.pending
                or 0
            )

            in_progress = (
                row.in_progress
                or 0
            )

            overdue = (
                row.overdue
                or 0
            )

            return {
                "pending": pending,
                "in_progress": in_progress,
                "overdue": overdue,
                "total_backlog":
                    pending
                    + in_progress,
            }

        finally:

            session.close()

    # =========================================================================
    # DELAY SUMMARY
    # =========================================================================

    def get_delay_summary(
        self,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            query = (
                session.query(
                    func.coalesce(
                        func.sum(
                            WorkOrder.delay_minutes
                        ),
                        0,
                    ).label(
                        "total_minutes"
                    ),

                    func.count(
                        WorkOrder.id
                    ).label(
                        "delayed_count"
                    ),
                )
                .filter(
                    WorkOrder.delay_minutes > 0
                )
            )

            query = (
                self._apply_created_date_filter(
                    query,
                    start_date,
                    end_date,
                )
            )

            row = query.one()

            return {
                "total_minutes":
                    int(
                        row.total_minutes
                        or 0
                    ),

                "delayed_count":
                    int(
                        row.delayed_count
                        or 0
                    ),
            }

        finally:

            session.close()

    # =========================================================================
    # REJECTION
    # =========================================================================

    def get_rejection_percentage(
        self,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            total_q = (
                session.query(
                    func.count(
                        WorkOrder.id
                    )
                )
                .filter(
                    WorkOrder.status.in_(
                        [
                            WorkOrderStatus.APPROVED,
                            WorkOrderStatus.COMPLETED,
                            WorkOrderStatus.REJECTED,
                        ]
                    )
                )
            )

            rejected_q = (
                session.query(
                    func.count(
                        WorkOrder.id
                    )
                )
                .filter(
                    WorkOrder.status
                    == WorkOrderStatus.REJECTED
                )
            )

            total_q = (
                self._apply_created_date_filter(
                    total_q,
                    start_date,
                    end_date,
                )
            )

            rejected_q = (
                self._apply_created_date_filter(
                    rejected_q,
                    start_date,
                    end_date,
                )
            )

            total = (
                total_q.scalar()
                or 0
            )

            rejected = (
                rejected_q.scalar()
                or 0
            )

            pct = (
                (
                    rejected
                    / total
                )
                * 100
                if total > 0
                else 0.0
            )

            return {
                "total": total,
                "rejected": rejected,
                "percentage": pct,
            }

        finally:

            session.close()

    # =========================================================================
    # EQUIPMENT REPORT
    # =========================================================================

    def get_equipment_report(
        self,
        equipment_id: int,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            eq = (
                session.query(
                    Equipment
                )
                .filter(
                    Equipment.id
                    == equipment_id
                )
                .first()
            )

            if not eq:
                return None

            query = (
                session.query(
                    func.count(
                        WorkOrder.id
                    ).label(
                        "total"
                    ),

                    func.sum(
                        case(
                             
                                (
                                    WorkOrder.status.in_(DONE_STATUSES),
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "completed"
                    ),

                    func.sum(
                        case(
                             
                                (
                                    WorkOrder.type.in_(
                                        [
                                            WorkOrderType.PREVENTIVE,
                                            WorkOrderType.PM,
                                        ]
                                    ),
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "pm"
                    ),

                    func.sum(
                        case(
                             
                                (
                                    WorkOrder.type
                                    == WorkOrderType.CORRECTIVE,
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "cm"
                    ),

                    func.avg(
                        case(
                             
                                (
                                    and_(
                                        WorkOrder.start_time.isnot(
                                            None
                                        ),

                                        WorkOrder.end_time.isnot(
                                            None
                                        ),
                                    ),

                                    func.datediff(
                                        text("second"),
                                        WorkOrder.start_time,
                                        WorkOrder.end_time,
                                    )
                                    / 3600.0,
                                )
                             ,
                            else_=None,
                        )
                    ).label(
                        "avg_repair_hours"
                    ),

                    func.sum(
                        case(
                             
                                (
                                    and_(
                                        WorkOrder.type.in_(
                                            [
                                                WorkOrderType.CORRECTIVE,
                                                WorkOrderType.EMERGENCY,
                                                WorkOrderType.PREVENTIVE,
                                                WorkOrderType.PM,
                                            ]
                                        ),

                                        WorkOrder.start_time.isnot(
                                            None
                                        ),

                                        WorkOrder.end_time.isnot(
                                            None
                                        ),
                                    ),

                                    func.datediff(
                                        text("second"),
                                        WorkOrder.start_time,
                                        WorkOrder.end_time,
                                    )
                                    / 3600.0,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "total_downtime_hours"
                    ),
                )
                .filter(
                    WorkOrder.equipment_id
                    == equipment_id
                )
            )

            query = (
                self._apply_created_date_filter(
                    query,
                    start_date,
                    end_date,
                )
            )

            row = query.one()

            total_wo = (
                row.total
                or 0
            )

            completed = (
                row.completed
                or 0
            )

            pm = (
                row.pm
                or 0
            )

            cm = (
                row.cm
                or 0
            )

            avg_repair = float(
                row.avg_repair_hours
                or 0
            )

            total_downtime = float(
                row.total_downtime_hours
                or 0
            )

            # -----------------------------------------------------------------
            # MTBF / MTTR
            # -----------------------------------------------------------------

            failure_query = (
                session.query(
                    func.count(
                        WorkOrder.id
                    )
                )
                .filter(
                    WorkOrder.equipment_id
                    == equipment_id,

                    WorkOrder.type.in_(
                        [
                            WorkOrderType.CORRECTIVE,
                            WorkOrderType.EMERGENCY,
                        ]
                    ),

                    WorkOrder.status != WorkOrderStatus.REJECTED,  # every reported failure counts (MTBF)
                )
            )

            failure_query = (
                self._apply_created_date_filter(
                    failure_query,
                    start_date,
                    end_date,
                )
            )

            failure_count = (
                failure_query.scalar()
                or 0
            )

            operating_hours = (
                self._get_operating_hours(
                    session,
                    equipment_id,
                    start_date,
                    end_date,
                )
            )

            mtbf = (
                (
                    operating_hours
                    / failure_count
                )
                if failure_count > 0
                else operating_hours
            )

            mttr = (
                avg_repair
            )

            pm_compliance = (
                self._get_equipment_pm_compliance(
                    session,
                    equipment_id,
                    start_date,
                    end_date,
                )
            )

            return {
                "equipment_id":
                    eq.id,

                "equipment_name":
                    eq.name,

                "equipment_status":
                    eq.status,

                "total_work_orders":
                    total_wo,

                "completed_work_orders":
                    completed,

                "pm_work_orders":
                    pm,

                "cm_work_orders":
                    cm,

                "avg_repair_time_hours":
                    round(
                        avg_repair,
                        2,
                    ),

                "total_downtime_hours":
                    round(
                        total_downtime,
                        2,
                    ),

                "avg_downtime_hours":
                    round(
                        (
                            total_downtime
                            / failure_count
                        )
                        if failure_count
                        else 0,
                        2,
                    ),

                "pm_compliance_rate":
                    round(
                        pm_compliance,
                        2,
                    ),

                "mtbf_hours":
                    round(
                        float(
                            mtbf
                            or 0
                        ),
                        2,
                    ),

                "mttr_hours":
                    round(
                        float(
                            mttr
                            or 0
                        ),
                        2,
                    ),

                "failure_count":
                    int(
                        failure_count
                    ),
            }

        finally:

            session.close()

    # =========================================================================
    # EQUIPMENT PM COMPLIANCE
    # =========================================================================

    def _get_equipment_pm_compliance(
        self,
        session,
        equipment_id,
        start_date=None,
        end_date=None,
    ):

        query = (
            session.query(
                WorkOrder
            )
            .options(
                joinedload(
                    WorkOrder.schedule
                )
            )
            .filter(
                WorkOrder.equipment_id
                == equipment_id,

                WorkOrder.type.in_(
                    [
                        WorkOrderType.PREVENTIVE,
                        WorkOrderType.PM,
                    ]
                ),

                WorkOrder.status.in_(DONE_STATUSES),

                WorkOrder.scheduled_date.isnot(
                    None
                ),

                WorkOrder.end_time.isnot(
                    None
                ),
            )
        )

        query = (
            self._apply_created_date_filter(
                query,
                start_date,
                end_date,
            )
        )

        rows = query.all()

        if not rows:
            return 0.0

        on_time = 0

        for wo in rows:

            scheduled = (
                wo.scheduled_date
            )

            if wo.deadline:

                deadline = (
                    wo.deadline
                )

            elif (
                wo.schedule_id
                and wo.schedule
            ):

                duration_days = int(
                    getattr(
                        wo.schedule,
                        "estimated_duration",
                        0,
                    )
                    or 0
                )

                deadline = (
                    scheduled
                    + timedelta(
                        days=duration_days
                    )
                )

            else:

                deadline = (
                    scheduled
                    + timedelta(
                        days=1
                    )
                )

            if wo.end_time <= deadline:
                on_time += 1

        return (
            on_time
            / len(rows)
            * 100
        )

    # =========================================================================
    # MTBF
    # =========================================================================

    def get_mtbf(
        self,
        equipment_id=None,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            query = (
                session.query(
                    Equipment
                )
            )

            if equipment_id:

                query = query.filter(
                    Equipment.id
                    == equipment_id
                )

            results = []

            for eq in query.all():

                failures_query = (
                    session.query(
                        func.count(
                            WorkOrder.id
                        )
                    )
                    .filter(
                        WorkOrder.equipment_id
                        == eq.id,

                        WorkOrder.type.in_(
                            [
                                WorkOrderType.CORRECTIVE,
                                WorkOrderType.EMERGENCY,
                            ]
                        ),

                        WorkOrder.status != WorkOrderStatus.REJECTED,  # every reported failure counts (MTBF)
                    )
                )

                failures_query = (
                    self._apply_created_date_filter(
                        failures_query,
                        start_date,
                        end_date,
                    )
                )

                failure_count = (
                    failures_query.scalar()
                    or 0
                )

                operating_hours = (
                    self._get_operating_hours(
                        session,
                        eq.id,
                        start_date,
                        end_date,
                    )
                )

                mtbf = (
                    (
                        operating_hours
                        / failure_count
                    )
                    if failure_count > 0
                    else operating_hours
                )

                results.append(
                    {
                        "equipment_id":
                            eq.id,

                        "equipment_name":
                            eq.name,

                        "mtbf_hours":
                            round(
                                float(
                                    mtbf
                                    or 0
                                ),
                                2,
                            ),

                        "failure_count":
                            int(
                                failure_count
                            ),
                    }
                )

            return results

        finally:

            session.close()

    # =========================================================================
    # MTTR
    # =========================================================================

    def get_mttr(
        self,
        equipment_id=None,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            query = (
                session.query(
                    Equipment
                )
            )

            if equipment_id:

                query = query.filter(
                    Equipment.id
                    == equipment_id
                )

            results = []

            for eq in query.all():

                repair_query = (
                    session.query(
                        func.avg(
                            func.datediff(
                                text("second"),
                                WorkOrder.start_time,
                                WorkOrder.end_time,
                            )
                            / 3600.0
                        )
                    )
                    .filter(
                        WorkOrder.equipment_id
                        == eq.id,

                        WorkOrder.type.in_(
                            [
                                WorkOrderType.CORRECTIVE,
                                WorkOrderType.EMERGENCY,
                            ]
                        ),

                        WorkOrder.status.in_(DONE_STATUSES),

                        WorkOrder.start_time.isnot(
                            None
                        ),

                        WorkOrder.end_time.isnot(
                            None
                        ),
                    )
                )

                repair_query = (
                    self._apply_created_date_filter(
                        repair_query,
                        start_date,
                        end_date,
                    )
                )

                avg_hours = (
                    repair_query.scalar()
                    or 0
                )

                count_query = (
                    session.query(
                        func.count(
                            WorkOrder.id
                        )
                    )
                    .filter(
                        WorkOrder.equipment_id
                        == eq.id,

                        WorkOrder.type.in_(
                            [
                                WorkOrderType.CORRECTIVE,
                                WorkOrderType.EMERGENCY,
                            ]
                        ),

                        WorkOrder.status.in_(DONE_STATUSES),

                        WorkOrder.start_time.isnot(
                            None
                        ),

                        WorkOrder.end_time.isnot(
                            None
                        ),
                    )
                )

                count_query = (
                    self._apply_created_date_filter(
                        count_query,
                        start_date,
                        end_date,
                    )
                )

                cnt = (
                    count_query.scalar()
                    or 0
                )

                results.append(
                    {
                        "equipment_id":
                            eq.id,

                        "equipment_name":
                            eq.name,

                        "mttr_hours":
                            round(
                                float(
                                    avg_hours
                                    or 0
                                ),
                                2,
                            ),

                        "repair_count":
                            int(cnt),
                    }
                )

            return results

        finally:

            session.close()

    # =========================================================================
    # OEE
    # =========================================================================

    def get_oee_metrics(
        self,
        equipment_id=None,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            query = (
                session.query(
                    Equipment
                )
            )

            if equipment_id:

                query = query.filter(
                    Equipment.id
                    == equipment_id
                )

            results = []

            for eq in query.all():

                planned_hours = (
                    self._get_planned_hours(
                        session,
                        eq.id,
                        start_date,
                        end_date,
                    )
                )

                downtime_seconds = (
                    self._get_downtime_internal(
                        session,
                        eq.id,
                        start_date,
                        end_date,
                    )
                )

                downtime_hours = (
                    downtime_seconds
                    / 3600.0
                )

                availability = (
                    (
                        (
                            planned_hours
                            - downtime_hours
                        )
                        / planned_hours
                    )
                    * 100
                    if planned_hours > 0
                    else 0
                )

                # Preserve existing application assumption.
                performance = 95.0

                quality = (
                    self._get_inspection_pass_rate(
                        session,
                        eq.id,
                        start_date,
                        end_date,
                    )
                )

                oee = (
                    availability
                    * performance
                    * quality
                    / 10000
                )

                results.append(
                    {
                        "equipment_id":
                            eq.id,

                        "equipment_name":
                            eq.name,

                        "availability":
                            round(
                                availability,
                                2,
                            ),

                        "performance":
                            round(
                                performance,
                                2,
                            ),

                        "quality":
                            round(
                                quality,
                                2,
                            ),

                        "oee":
                            round(
                                oee,
                                2,
                            ),
                    }
                )

            return results

        finally:

            session.close()

    # =========================================================================
    # PM / CM RATIO
    # =========================================================================

    def get_pm_cm_ratio(
        self,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            query = (
                session.query(
                    func.sum(
                        case(
                             
                                (
                                    WorkOrder.type.in_(
                                        [
                                            WorkOrderType.PREVENTIVE,
                                            WorkOrderType.PM,
                                        ]
                                    ),
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "pm"
                    ),

                    func.sum(
                        case(
                             
                                (
                                    WorkOrder.type
                                    == WorkOrderType.CORRECTIVE,
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "cm"
                    ),

                    func.sum(
                        case(
                             
                                (
                                    WorkOrder.type
                                    == WorkOrderType.EMERGENCY,
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "emergency"
                    ),
                )
                .filter(
                    WorkOrder.status.in_(DONE_STATUSES)
                )
            )

            query = (
                self._apply_created_date_filter(
                    query,
                    start_date,
                    end_date,
                )
            )

            row = query.one()

            pm = (
                row.pm
                or 0
            )

            cm = (
                row.cm
                or 0
            )

            emergency = (
                row.emergency
                or 0
            )

            ratio = (
                (
                    pm
                    / cm
                )
                if cm > 0
                else float(pm)
            )

            return {
                "preventive_count":
                    pm,

                "corrective_count":
                    cm,

                "emergency_count":
                    emergency,

                "ratio":
                    round(
                        ratio,
                        2,
                    ),

                "total":
                    pm
                    + cm
                    + emergency,
            }

        finally:

            session.close()

    # =========================================================================
    # SCHEDULE COMPLIANCE
    # =========================================================================

    def get_schedule_compliance(
        self,
        start_date=None,
        end_date=None,
    ):
        """
        Work orders whose SCHEDULED date is in the period: finished by the
        deadline vs. finished late or still open after the deadline.
        """
        session = self.Session()

        try:
            query = (
                session.query(WorkOrder)
                .options(joinedload(WorkOrder.schedule))
                .filter(
                    WorkOrder.status != WorkOrderStatus.REJECTED,
                    WorkOrder.scheduled_date.isnot(None),
                )
            )
            query = self._apply_created_date_filter(
                query, start_date, end_date, field=WorkOrder.scheduled_date)

            now = tehran_now()
            on_time = late = overdue_open = 0
            for wo in query.all():
                outcome = _compliance_outcome(wo, now)
                if outcome == "on_time":
                    on_time += 1
                elif outcome == "late":
                    late += 1
                    if wo.status in _OPEN_STATUSES:
                        overdue_open += 1

            total = on_time + late
            rate = on_time / total * 100 if total > 0 else 0

            return {
                "on_time": on_time,
                "late": late,
                "overdue_open": overdue_open,
                "total_tasks": total,
                "compliance_rate": round(rate, 1),
            }

        finally:
            session.close()

    # =========================================================================
    # COST ANALYSIS
    # =========================================================================

    def get_cost_analysis(
        self,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            # Parts are summed per work order FIRST (derived table). v2.3
            # joined the transactions directly, so a work order with N part
            # lines had its labour and manual cost counted N times, and a work
            # order whose only transactions were "IN" disappeared entirely.
            where_parts = [
                "wo.status IN ('APPROVED', 'COMPLETED')",
            ]

            params = {}

            if start_date:
                where_parts.append("wo.created_at >= :start")
                params["start"] = start_date

            if end_date:
                where_parts.append("wo.created_at < :end")
                params["end"] = end_date + timedelta(days=1)

            where_clause = " AND ".join(where_parts)

            sql = f"""
                SELECT
                    wo.type,
                    ISNULL(SUM(pc.part_cost), 0) AS part_cost,
                    ISNULL(SUM(
                        CASE
                            WHEN wo.start_time IS NOT NULL
                             AND wo.end_time IS NOT NULL
                             AND wo.end_time >= wo.start_time
                            THEN DATEDIFF(second, wo.start_time, wo.end_time) / 3600.0 * 50
                            ELSE 0
                        END
                    ), 0) AS labor_cost,
                    ISNULL(SUM(wo.manual_cost), 0) AS manual_cost
                FROM work_orders wo
                LEFT JOIN (
                    SELECT
                        w2.id AS wo_id,
                        SUM(sp.unit_price * spt.quantity) AS part_cost
                    FROM work_orders w2
                    JOIN spare_part_transactions spt
                      ON (
                           spt.reference = CAST(w2.id AS VARCHAR(50))
                        OR spt.reference = 'WO-' + CAST(w2.id AS VARCHAR(50))
                      )
                    JOIN spare_parts sp
                      ON sp.id = spt.part_id
                    WHERE (spt.transaction_type = 'OUT' OR spt.transaction_type IS NULL)
                    GROUP BY w2.id
                ) pc
                  ON pc.wo_id = wo.id
                WHERE {where_clause}
                GROUP BY wo.type
            """

            result = (
                session.execute(
                    text(sql),
                    params,
                )
                .fetchall()
            )

            breakdown = []
            total_cost = 0.0

            for row in result:

                type_name = (
                    row[0].name
                    if hasattr(
                        row[0],
                        "name",
                    )
                    else str(
                        row[0]
                    )
                )

                part = float(
                    row[1]
                    or 0
                )

                labor = float(
                    row[2]
                    or 0
                )

                manual = float(
                    row[3]
                    or 0
                )

                cost = (
                    part
                    + labor
                    + manual
                )

                breakdown.append(
                    {
                        "type":
                            type_name,

                        "total_cost":
                            round(
                                cost,
                                2,
                            ),

                        "part_cost":
                            round(
                                part,
                                2,
                            ),

                        "labor_cost":
                            round(
                                labor,
                                2,
                            ),

                        "manual_cost":
                            round(
                                manual,
                                2,
                            ),
                    }
                )

                total_cost += cost

            for item in breakdown:

                item[
                    "percentage"
                ] = (
                    round(
                        (
                            item[
                                "total_cost"
                            ]
                            / total_cost
                        )
                        * 100,
                        2,
                    )
                    if total_cost > 0
                    else 0
                )

            return {
                "breakdown":
                    breakdown,

                "total_cost":
                    round(
                        total_cost,
                        2,
                    ),
            }

        finally:

            session.close()

    # =========================================================================
    # EQUIPMENT RISK
    # =========================================================================

    def get_equipment_risk_score(
        self
    ):

        session = self.Session()

        try:

            cutoff = (
                tehran_now()
                - timedelta(
                    days=30
                )
            )

            rows = (
                session.query(
                    Equipment.id,
                    Equipment.name,
                    Equipment.criticality_level,

                    func.sum(
                        case(
                             
                                (
                                    and_(
                                        WorkOrder.type.in_(
                                            [
                                                WorkOrderType.CORRECTIVE,
                                                WorkOrderType.EMERGENCY,
                                            ]
                                        ),

                                        WorkOrder.created_at
                                        >= cutoff,
                                    WorkOrder.status != WorkOrderStatus.REJECTED,
                                    ),
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "recent_failures"
                    ),
                )
                .outerjoin(
                    WorkOrder,
                    WorkOrder.equipment_id
                    == Equipment.id,
                )
                .group_by(
                    Equipment.id,
                    Equipment.name,
                    Equipment.criticality_level,
                )
                .all()
            )

            criticality_factor = {
                "low": 1,
                "medium": 2,
                "high": 3,
                "critical": 4,
            }

            # Average repair time per equipment in ONE grouped query
            # (v2.3 ran one query per equipment).
            repair_rows = (
                session.query(
                    WorkOrder.equipment_id,
                    func.avg(
                        func.datediff(text("second"), WorkOrder.start_time, WorkOrder.end_time)
                        / 3600.0
                    ),
                )
                .filter(
                    WorkOrder.type.in_([WorkOrderType.CORRECTIVE, WorkOrderType.EMERGENCY]),
                    WorkOrder.status.in_(DONE_STATUSES),
                    WorkOrder.start_time.isnot(None),
                    WorkOrder.end_time.isnot(None),
                    WorkOrder.end_time >= WorkOrder.start_time,
                )
                .group_by(WorkOrder.equipment_id)
                .all()
            )
            avg_repair = {eq_id: float(v or 0) for eq_id, v in repair_rows}

            results = []

            for (
                eq_id,
                eq_name,
                crit,
                failures,
            ) in rows:

                failures = (
                    failures
                    or 0
                )

                avg_hours = avg_repair.get(eq_id, 0.0)

                factor = (
                    criticality_factor.get(
                        str(
                            crit
                            or ""
                        ).lower(),
                        2,
                    )
                )

                raw = (
                    (
                        failures
                        * 10
                    )
                    + (
                        float(
                            avg_hours
                            or 0
                        )
                        * 5
                    )
                )

                risk_score = min(
                    100,
                    raw * factor,
                )

                results.append(
                    {
                        "equipment_id":
                            eq_id,

                        "equipment_name":
                            eq_name,

                        "failure_count":
                            failures,

                        "avg_downtime_hours":
                            round(
                                float(
                                    avg_hours
                                    or 0
                                ),
                                2,
                            ),

                        "criticality":
                            crit,

                        "risk_score":
                            round(
                                float(
                                    risk_score
                                ),
                                2,
                            ),

                        "risk_level":
                            (
                                "HIGH"
                                if risk_score > 70
                                else
                                "MEDIUM"
                                if risk_score > 40
                                else
                                "LOW"
                            ),
                    }
                )

            return sorted(
                results,
                key=lambda x:
                x[
                    "risk_score"
                ],
                reverse=True,
            )

        finally:

            session.close()

    # =========================================================================
    # NEW PERSONNEL PERFORMANCE
    # =========================================================================

    def get_personnel_performance(
        self,
        start_date=None,
        end_date=None,
    ):
        """
        Actual maintenance Personnel performance.

        IMPORTANT:
        ---------

        This does NOT use:
            WorkOrder.technician_id

        It uses:
            WorkOrder.completed_by_personnel_id

        Therefore the report reflects the Personnel actually selected
        when the Work Order finish request is submitted.

        Historical Work Orders without completed_by_personnel_id remain
        valid and simply do not appear in the Personnel performance
        results.
        """

        session = self.Session()

        try:

            personnel_list = (
                session.query(
                    Personnel
                )
                .options(
                    joinedload(
                        Personnel.department
                    )
                )
                .order_by(
                    Personnel.full_name.asc()
                )
                .all()
            )

            output = []

            for person in (
                personnel_list
            ):

                query = (
                    session.query(
                        WorkOrder
                    )
                    .filter(
                        WorkOrder.completed_by_personnel_id
                        == person.id
                    )
                )

                query = (
                    self._apply_created_date_filter(
                        query,
                        start_date,
                        end_date,
                    )
                )

                work_orders = (
                    query.all()
                )

                total = len(
                    work_orders
                )

                completed = 0

                durations = []

                for wo in work_orders:

                    status_name = (
                        getattr(
                            wo.status,
                            "name",
                            "",
                        )
                        or ""
                    ).upper()

                    if status_name in {
                        "APPROVED",
                        "COMPLETED",
                    }:

                        completed += 1

                    if (
                        wo.start_time
                        and wo.end_time
                    ):

                        try:

                            seconds = (
                                wo.end_time
                                - wo.start_time
                            ).total_seconds()

                            hours = (
                                seconds
                                / 3600.0
                            )

                            if hours >= 0:

                                durations.append(
                                    hours
                                )

                        except Exception:

                            pass

                completion_rate = (
                    (
                        completed
                        / total
                    )
                    * 100
                    if total > 0
                    else 0
                )

                avg_hours = (
                    sum(
                        durations
                    )
                    / len(
                        durations
                    )
                    if durations
                    else 0
                )

                department = getattr(
                    person,
                    "department",
                    None,
                )

                department_name = (
                    getattr(
                        department,
                        "name",
                        None,
                    )
                    or "بدون دپارتمان"
                )

                personnel_code = (
                    getattr(
                        person,
                        "personnel_code",
                        "",
                    )
                    or ""
                )

                full_name = (
                    getattr(
                        person,
                        "full_name",
                        "",
                    )
                    or "—"
                )

                output.append(
                    {
                        "personnel_id":
                            person.id,

                        "personnel_code":
                            personnel_code,

                        "personnel_name":
                            full_name,

                        "department_id":
                            getattr(
                                person,
                                "department_id",
                                None,
                            ),

                        "department_name":
                            department_name,

                        "total_tasks":
                            total,

                        "completed_tasks":
                            completed,

                        "completion_rate":
                            round(
                                completion_rate,
                                2,
                            ),

                        "avg_completion_hours":
                            round(
                                avg_hours,
                                2,
                            ),
                    }
                )

            # Personnel with actual activity first.
            output.sort(
                key=lambda item: (
                    -item[
                        "total_tasks"
                    ],
                    -item[
                        "completed_tasks"
                    ],
                    item[
                        "personnel_name"
                    ],
                )
            )

            return output

        finally:

            session.close()

    # =========================================================================
    # LEGACY TECHNICIAN PERFORMANCE
    # =========================================================================

    def get_technician_performance(
        self,
        start_date=None,
        end_date=None,
    ):
        """
        Compatibility wrapper.

        Older code may still call get_technician_performance().

        The returned data now comes from Personnel, not User technician_id.

        Existing callers receive the familiar keys:
            technician_id
            technician_name
            total_tasks
            completed_tasks
            completion_rate
            avg_completion_hours

        New code should prefer:
            get_personnel_performance()
        """

        personnel_data = (
            self.get_personnel_performance(
                start_date,
                end_date,
            )
        )

        output = []

        for item in (
            personnel_data
        ):

            output.append(
                {
                    "technician_id":
                        item.get(
                            "personnel_id"
                        ),

                    "technician_name":
                        item.get(
                            "personnel_name",
                            "—",
                        ),

                    "personnel_id":
                        item.get(
                            "personnel_id"
                        ),

                    "personnel_code":
                        item.get(
                            "personnel_code",
                            "",
                        ),

                    "department_id":
                        item.get(
                            "department_id"
                        ),

                    "department_name":
                        item.get(
                            "department_name",
                            "—",
                        ),

                    "total_tasks":
                        item.get(
                            "total_tasks",
                            0,
                        ),

                    "completed_tasks":
                        item.get(
                            "completed_tasks",
                            0,
                        ),

                    "completion_rate":
                        item.get(
                            "completion_rate",
                            0,
                        ),

                    "avg_completion_hours":
                        item.get(
                            "avg_completion_hours",
                            0,
                        ),
                }
            )

        return output

    # =========================================================================
    # MONTHLY TRENDS
    # =========================================================================

    def get_monthly_trends(
        self,
        months=6,
    ):
        """
        Work orders per JALALI month and type for the last ``months`` months
        (current month included).  Returns the same keys as before
        (year, month, type, count) - year/month are now Jalali (e.g. 1405/07)
        instead of Gregorian, matching the rest of the application.
        """
        import jdatetime

        session = self.Session()

        try:
            today = jdatetime.date.fromgregorian(date=tehran_now().date())
            y, m = today.year, today.month
            for _ in range(max(1, int(months)) - 1):
                m -= 1
                if m == 0:
                    y, m = y - 1, 12
            start_date = datetime.combine(jdatetime.date(y, m, 1).togregorian(), datetime.min.time())

            rows = (
                session.query(WorkOrder.created_at, WorkOrder.type)
                .filter(WorkOrder.created_at >= start_date)
                .all()
            )

            counts = {}
            for created_at, wo_type in rows:
                if created_at is None:
                    continue
                j = jdatetime.date.fromgregorian(date=created_at.date())
                type_name = wo_type.name if hasattr(wo_type, "name") else str(wo_type)
                key = (j.year, j.month, type_name)
                counts[key] = counts.get(key, 0) + 1

            return [
                {"year": year, "month": month, "type": type_name, "count": count}
                for (year, month, type_name), count in sorted(counts.items())
            ]

        finally:
            session.close()

    # =========================================================================
    # INSPECTION EFFECTIVENESS
    # =========================================================================

    def get_inspection_effectiveness(
        self,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            query = (
                session.query(
                    func.count(
                        InspectionResult.id
                    ).label(
                        "total"
                    ),

                    func.sum(
                        case(
                             
                                (
                                    InspectionResult.result
                                    == "pass",
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "passed"
                    ),
                )
                .join(
                    Inspection,
                    Inspection.id
                    == InspectionResult.inspection_id,
                )
                .filter(
                    Inspection.status
                    == "completed"
                )
            )

            if start_date:

                query = query.filter(
                    Inspection.completed_at
                    >= start_date
                )

            if end_date:

                end_exclusive = (
                    end_date
                    + timedelta(
                        days=1
                    )
                )

                query = query.filter(
                    Inspection.completed_at
                    < end_exclusive
                )

            row = query.one()

            total = (
                row.total
                or 0
            )

            passed = (
                row.passed
                or 0
            )

            effectiveness = (
                passed
                / total
                * 100
                if total
                else 0
            )

            return {
                "total_checkpoints":
                    total,

                "passed":
                    passed,

                "effectiveness":
                    round(
                        effectiveness,
                        2,
                    ),
            }

        finally:

            session.close()

    # =========================================================================
    # CLEANING SCORE
    # =========================================================================

    def get_cleaning_score(
        self,
        start_date=None,
        end_date=None,
    ):

        session = self.Session()

        try:

            query = (
                session.query(
                    func.count(
                        InspectionResult.id
                    ).label(
                        "total"
                    ),

                    func.sum(
                        case(
                             
                                (
                                    InspectionResult.result
                                    == "pass",
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "passed"
                    ),
                )
                .join(
                    InspectionCheckpoint,
                    InspectionCheckpoint.id
                    == InspectionResult.checkpoint_id,
                )
                .join(
                    Inspection,
                    Inspection.id
                    == InspectionResult.inspection_id,
                )
                .filter(
                    Inspection.status
                    == "completed",

                    InspectionCheckpoint.checkpoint_type
                    == "safety",
                )
            )

            if start_date:

                query = query.filter(
                    Inspection.completed_at
                    >= start_date
                )

            if end_date:

                query = query.filter(
                    Inspection.completed_at
                    < (
                        end_date
                        + timedelta(
                            days=1
                        )
                    )
                )

            row = query.one()

            total = (
                row.total
                or 0
            )

            passed = (
                row.passed
                or 0
            )

            score = (
                passed
                / total
                * 100
                if total
                else 0
            )

            return {
                "total_cleaning_checks":
                    total,

                "passed":
                    passed,

                "score":
                    round(
                        score,
                        2,
                    ),
            }

        finally:

            session.close()

    # =========================================================================
    # SPARE PARTS TURNOVER
    # =========================================================================

    def get_spare_parts_turnover(
        self
    ):

        session = self.Session()

        try:

            one_year_ago = (
                tehran_now()
                - timedelta(
                    days=365
                )
            )

            consumption = (
                session.query(
                    func.sum(
                        SparePartTransaction.quantity
                        * SparePart.unit_price
                    )
                )
                .join(
                    SparePart,
                    SparePart.id
                    == SparePartTransaction.part_id,
                )
                .filter(
                    SparePartTransaction.transaction_type
                    == "OUT",

                    SparePartTransaction.created_at
                    >= one_year_ago,
                )
                .scalar()
                or 0
            )

            avg_inventory = (
                session.query(
                    func.sum(
                        SparePart.current_stock
                        * SparePart.unit_price
                    )
                )
                .scalar()
                or 0
            )

            turnover = (
                consumption
                / avg_inventory
                if avg_inventory > 0
                else 0
            )

            return {
                "annual_consumption":
                    round(
                        float(
                            consumption
                            or 0
                        ),
                        2,
                    ),

                "average_inventory_value":
                    round(
                        float(
                            avg_inventory
                            or 0
                        ),
                        2,
                    ),

                "turnover_ratio":
                    round(
                        float(
                            turnover
                            or 0
                        ),
                        2,
                    ),
            }

        finally:

            session.close()

    # =========================================================================
    # ALL EQUIPMENT PERFORMANCE
    # =========================================================================

    def get_all_equipment_performance(
        self,
        start_date=None,
        end_date=None,
    ):
        """
        Performance data for all Equipment (Reports > تجهیزات tab).

        Definitions (shared with the machine-hours page):
            failures      corrective + emergency work orders created in the
                          period, except REJECTED
            MTTR          average (end - start) of FINISHED corrective /
                          emergency work orders that have both times
            MTBF          operating hours / failures   (operating hours when
                          there were no failures - unchanged convention)
            availability  operating hours / planned hours (production logs),
                          limited to 0..100 %
            quality       inspection pass rate in the period, "na" answers
                          ignored; 100 % when the equipment has no inspection
            performance   95 % fixed assumption (no ideal-rate data exists)
            OEE           availability x performance x quality

        v2.3 problems fixed here: MTTR divided total repair time by ALL
        failures (also those never repaired/timed), availability used repair
        time of unapproved/rejected work orders and could go negative, quality
        was a fixed 100 % here but the pass rate elsewhere, and one cost query
        per equipment made the tab slow.  Now 4 grouped queries in total.
        """

        session = self.Session()

        try:
            failure_types = [WorkOrderType.CORRECTIVE, WorkOrderType.EMERGENCY]
            pm_types = [WorkOrderType.PREVENTIVE, WorkOrderType.PM]
            is_failure = WorkOrder.type.in_(failure_types)
            is_done = WorkOrder.status.in_(DONE_STATUSES)
            timed_repair = and_(
                is_failure,
                is_done,
                WorkOrder.start_time.isnot(None),
                WorkOrder.end_time.isnot(None),
                WorkOrder.end_time >= WorkOrder.start_time,
            )
            repair_hours_expr = (
                func.datediff(text("second"), WorkOrder.start_time, WorkOrder.end_time) / 3600.0
            )

            # ---- work orders, grouped per equipment -------------------------
            wo_query = session.query(
                WorkOrder.equipment_id,
                func.count(WorkOrder.id),
                func.sum(case((is_done, 1), else_=0)),
                func.sum(case((WorkOrder.type.in_(pm_types), 1), else_=0)),
                func.sum(case((WorkOrder.type == WorkOrderType.CORRECTIVE, 1), else_=0)),
                func.sum(case((WorkOrder.type == WorkOrderType.EMERGENCY, 1), else_=0)),
                func.sum(case(
                    (and_(is_failure, WorkOrder.status != WorkOrderStatus.REJECTED), 1), else_=0)),
                func.sum(case((timed_repair, 1), else_=0)),
                func.sum(case((timed_repair, repair_hours_expr), else_=0)),
                func.sum(case((is_done, func.coalesce(WorkOrder.manual_cost, 0)), else_=0)),
            ).group_by(WorkOrder.equipment_id)
            wo_query = self._apply_created_date_filter(wo_query, start_date, end_date)
            wo_stats = {row[0]: row for row in wo_query.all()}

            # ---- production logs -------------------------------------------
            prod_query = session.query(
                ProductionLog.equipment_id,
                func.sum(ProductionLog.operating_hours),
                func.sum(ProductionLog.planned_hours),
            ).group_by(ProductionLog.equipment_id)
            prod_query = self._apply_created_date_filter(
                prod_query, start_date, end_date, field=ProductionLog.log_date)
            prod_stats = {row[0]: row for row in prod_query.all()}

            # ---- inspection quality -----------------------------------------
            quality_stats = self._inspection_pass_rates(session, start_date, end_date)

            results = []
            for eq in session.query(Equipment).order_by(Equipment.id).all():
                wo = wo_stats.get(eq.id)
                prod = prod_stats.get(eq.id)

                def col(i, row=wo):
                    return float(row[i] or 0) if row else 0.0

                total_wo, completed = col(1), col(2)
                pm, cm, em = col(3), col(4), col(5)
                failures, timed_count, repair_hours, manual_cost = col(6), col(7), col(8), col(9)
                operating_hours = float(prod[1] or 0) if prod else 0.0
                planned_hours = float(prod[2] or 0) if prod else 0.0

                mtbf = operating_hours / failures if failures > 0 else operating_hours
                mttr = repair_hours / timed_count if timed_count > 0 else 0.0
                availability = (
                    max(0.0, min(100.0, operating_hours / planned_hours * 100.0))
                    if planned_hours > 0 else 0.0
                )
                quality = quality_stats.get(eq.id, 100.0)
                performance = 95.0
                oee = availability * performance * quality / 10000.0

                results.append({
                    "equipment_id": eq.id,
                    "equipment_code": getattr(eq, "code", "") or "",
                    "equipment_name": eq.name,
                    "equipment_status": eq.status,
                    # for the report filters / summary
                    "equipment_category": getattr(eq, "category", "") or "",
                    "equipment_location": getattr(eq, "location", "") or "",
                    "planned_hours": round(planned_hours, 2),
                    "operating_hours": round(operating_hours, 2),
                    "total_work_orders": int(total_wo),
                    "completed_work_orders": int(completed),
                    "pm_work_orders": int(pm),
                    "cm_work_orders": int(cm),
                    "em_work_orders": int(em),
                    "mtbf_hours": round(mtbf, 2),
                    "mttr_hours": round(mttr, 2),
                    "availability": round(availability, 2),
                    "oee": round(oee, 2),
                    "total_downtime_hours": round(repair_hours, 2),
                    "total_cost": round(manual_cost, 2),
                })

            return results

        finally:
            session.close()

    def _inspection_pass_rates(self, session, start_date=None, end_date=None):
        """{equipment_id: pass %} over completed inspections; 'na' answers ignored."""
        answered = InspectionResult.result != "na"
        query = (
            session.query(
                Inspection.equipment_id,
                func.sum(case((answered, 1), else_=0)),
                func.sum(case((InspectionResult.result == "pass", 1), else_=0)),
            )
            .join(Inspection, Inspection.id == InspectionResult.inspection_id)
            .filter(Inspection.status == "completed")
            .group_by(Inspection.equipment_id)
        )
        query = self._apply_created_date_filter(
            query, start_date, end_date, field=Inspection.completed_at)
        rates = {}
        for eq_id, total, passed in query.all():
            total = float(total or 0)
            if total > 0:
                rates[eq_id] = float(passed or 0) / total * 100.0
        return rates

    # =========================================================================
    # TOP FAILURE MODES
    # =========================================================================

    def get_top_failure_modes(
        self,
        start_date=None,
        end_date=None,
        limit=20,
    ):

        session = self.Session()

        try:

            # Keep limit integer-safe.
            try:
                limit = int(
                    limit
                )
            except (
                TypeError,
                ValueError,
            ):
                limit = 20

            limit = max(
                1,
                min(
                    limit,
                    1000,
                ),
            )

            sql = f"""
                SELECT TOP {limit}

                    CAST(
                        description
                        AS NVARCHAR(4000)
                    ) AS description,

                    COUNT(id) AS count

                FROM work_orders

                WHERE type IN (
                    'CORRECTIVE',
                    'EMERGENCY'
                )

                AND status IN ('APPROVED', 'COMPLETED')

                AND description IS NOT NULL

                AND LEN(
                    CAST(
                        description
                        AS NVARCHAR(4000)
                    )
                ) > 0
            """

            params = {}

            if start_date:

                sql += (
                    " AND created_at >= :start"
                )

                params[
                    "start"
                ] = start_date

            if end_date:

                sql += (
                    " AND created_at < :end"
                )

                params[
                    "end"
                ] = (
                    end_date
                    + timedelta(days=1)
                )

            sql += """
                GROUP BY
                    CAST(
                        description
                        AS NVARCHAR(4000)
                    )

                ORDER BY
                    COUNT(id) DESC
            """

            result = (
                session.execute(
                    text(sql),
                    params,
                )
                .fetchall()
            )

            return [
                {
                    "description":
                        row[0],

                    "count":
                        row[1],
                }
                for row in result
            ]

        finally:

            session.close()

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _get_downtime_internal(
        self,
        session,
        equipment_id,
        start_date=None,
        end_date=None,
    ):

        query = (
            session.query(
                func.sum(
                    func.datediff(
                        text("second"),
                        WorkOrder.start_time,
                        WorkOrder.end_time,
                    )
                )
            )
            .filter(
                WorkOrder.equipment_id
                == equipment_id,

                WorkOrder.type.in_(
                    [
                        WorkOrderType.CORRECTIVE,
                        WorkOrderType.EMERGENCY,
                    ]
                ),

                WorkOrder.status.in_(DONE_STATUSES),

                WorkOrder.start_time.isnot(
                    None
                ),

                WorkOrder.end_time.isnot(
                    None
                ),
            )
        )

        query = (
            self._apply_created_date_filter(
                query,
                start_date,
                end_date,
            )
        )

        return (
            query.scalar()
            or 0
        )

    # -------------------------------------------------------------------------

    def _get_operating_hours(
        self,
        session,
        equipment_id,
        start_date=None,
        end_date=None,
    ):

        query = (
            session.query(
                func.sum(
                    ProductionLog.operating_hours
                )
            )
            .filter(
                ProductionLog.equipment_id
                == equipment_id
            )
        )

        if start_date:

            query = query.filter(
                ProductionLog.log_date
                >= start_date
            )

        if end_date:

            query = query.filter(
                ProductionLog.log_date
                < (
                    end_date
                    + timedelta(
                        days=1
                    )
                )
            )

        return (
            query.scalar()
            or 0
        )

    # -------------------------------------------------------------------------

    def _get_planned_hours(
        self,
        session,
        equipment_id,
        start_date=None,
        end_date=None,
    ):

        query = (
            session.query(
                func.sum(
                    ProductionLog.planned_hours
                )
            )
            .filter(
                ProductionLog.equipment_id
                == equipment_id
            )
        )

        if start_date:

            query = query.filter(
                ProductionLog.log_date
                >= start_date
            )

        if end_date:

            query = query.filter(
                ProductionLog.log_date
                < (
                    end_date
                    + timedelta(
                        days=1
                    )
                )
            )

        return (
            query.scalar()
            or 0
        )

    # -------------------------------------------------------------------------

    def _get_inspection_pass_rate(
        self,
        session,
        equipment_id,
        start_date,
        end_date,
    ):

        query = (
            session.query(
                func.count(
                    InspectionResult.id
                ).label(
                    "total"
                ),

                func.sum(
                    case(
                         
                            (
                                InspectionResult.result
                                == "pass",
                                1,
                            )
                         ,
                        else_=0,
                    )
                ).label(
                    "passed"
                ),
            )
            .join(
                Inspection,
                Inspection.id
                == InspectionResult.inspection_id,
            )
            .filter(
                Inspection.equipment_id
                == equipment_id,

                Inspection.status
                == "completed",
            )
        )

        if start_date:

            query = query.filter(
                Inspection.completed_at
                >= start_date
            )

        if end_date:

            query = query.filter(
                Inspection.completed_at
                < (
                    end_date
                    + timedelta(
                        days=1
                    )
                )
            )

        row = query.one()

        total = (
            row.total
            or 0
        )

        passed = (
            row.passed
            or 0
        )

        return (
            (
                passed
                / total
            )
            * 100
            if total
            else 0
        )
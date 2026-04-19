# database/report_repository.py
from sqlalchemy import func, extract, and_, case
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from database.db import SessionLocal
from database.work_order import WorkOrder, WorkOrderStatus, WorkOrderType
from database.models import Equipment, User


class ReportRepository:
    """
    All methods open and close their own session per call.
    No shared session state — safe, consistent with other repositories.
    """

    def _session(self):
        return SessionLocal()

    # ─────────────────────────── DASHBOARD KPIs ─────────────────────────────

    def get_kpi_summary(self):
        """
        Overall KPI summary for main dashboard.
        Fixed: was 8 separate queries — now 2 queries total.
        """
        with self._session() as session:
            # Query 1: All WorkOrder counts in one shot using conditional aggregation
            wo_row = session.query(
                func.count(WorkOrder.id).label("total"),
                func.sum(case((WorkOrder.status == WorkOrderStatus.COMPLETED, 1), else_=0)).label("completed"),
                func.sum(case((WorkOrder.status == WorkOrderStatus.PENDING, 1), else_=0)).label("pending"),
                func.sum(case((WorkOrder.status == WorkOrderStatus.IN_PROGRESS, 1), else_=0)).label("in_progress"),
                func.sum(case((WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM ]), 1), else_=0)).label("pm"),
                func.sum(case((WorkOrder.type == WorkOrderType.CORRECTIVE, 1), else_=0)).label("cm"),
                func.sum(case((
                    and_(
                        WorkOrder.status.in_([WorkOrderStatus.PENDING, WorkOrderStatus.IN_PROGRESS]),
                        WorkOrder.scheduled_date < datetime.now()
                    ), 1), else_=0)).label("overdue"),
                (func.avg(
                    func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
                ) * 24).label("avg_hours"),
            ).filter(
                WorkOrder.end_time.isnot(None),
                WorkOrder.start_time.isnot(None),
            ).one()

            # Query 2: Equipment counts in one shot
            eq_row = session.query(
                func.count(Equipment.id).label("total"),
                func.sum(case((Equipment.status == "operational", 1), else_=0)).label("operational"),
            ).one()

            total_wo    = wo_row.total or 0
            pm_count    = wo_row.pm or 0
            pm_compliance = (pm_count / total_wo * 100) if total_wo > 0 else 0

            return {
                "total_work_orders":       total_wo,
                "completed_work_orders":   wo_row.completed or 0,
                "pending_work_orders":     wo_row.pending or 0,
                "in_progress_work_orders": wo_row.in_progress or 0,
                "overdue_work_orders":     wo_row.overdue or 0,
                "total_equipment":         eq_row.total or 0,
                "operational_equipment":   eq_row.operational or 0,
                "avg_completion_time_hours": round(wo_row.avg_hours or 0, 2),
                "pm_compliance_rate":      round(pm_compliance, 2),
                "cm_work_orders":          wo_row.cm or 0,
            }

    def get_backlog_analysis(self):
        """
        Pending and overdue work orders.
        Fixed: was 3 separate queries — now 1 query.
        """
        now = datetime.now()
        with self._session() as session:
            row = session.query(
                func.sum(case((WorkOrder.status == WorkOrderStatus.PENDING, 1), else_=0)).label("pending"),
                func.sum(case((WorkOrder.status == WorkOrderStatus.IN_PROGRESS, 1), else_=0)).label("in_progress"),
                func.sum(case((
                    and_(
                        WorkOrder.status.in_([WorkOrderStatus.PENDING, WorkOrderStatus.IN_PROGRESS]),
                        WorkOrder.scheduled_date < now
                    ), 1), else_=0)).label("overdue"),
            ).one()

            pending     = row.pending or 0
            in_progress = row.in_progress or 0
            overdue     = row.overdue or 0

            return {
                "pending":       pending,
                "in_progress":   in_progress,
                "overdue":       overdue,
                "total_backlog": pending + in_progress,
            }

    # ─────────────────────────── PER-EQUIPMENT REPORT ───────────────────────

    def get_equipment_report(self, equipment_id: int):
        """
        Detailed report for a specific equipment.
        Fixed: reduced from 7 queries to 3 queries.
        """
        with self._session() as session:
            equipment = session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if not equipment:
                return None

            # Query 1: All WorkOrder aggregates for this equipment in one shot
            row = session.query(
                func.count(WorkOrder.id).label("total"),
                func.sum(case((WorkOrder.status == WorkOrderStatus.COMPLETED, 1), else_=0)).label("completed"),
                func.sum(case((WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM]), 1), else_=0)).label("pm"),
                func.sum(case((WorkOrder.type == WorkOrderType.CORRECTIVE, 1), else_=0)).label("cm"),
                (func.avg(
                    func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
                ) * 24).label("avg_repair"),
                (func.sum(case((
                    WorkOrder.type == WorkOrderType.CORRECTIVE,
                    func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
                ), else_=0)) * 24).label("total_downtime"),
            ).filter(
                WorkOrder.equipment_id == equipment_id,
                WorkOrder.end_time.isnot(None),
                WorkOrder.start_time.isnot(None),
            ).one()

            total_wo     = row.total or 0
            cm_count     = row.cm or 0
            avg_repair   = row.avg_repair or 0
            total_down   = row.total_downtime or 0
            pm_compliance = (row.pm or 0) / total_wo * 100 if total_wo > 0 else 0

            # Query 2: MTBF — first and last corrective failure times
            mtbf = 0
            if cm_count > 1:
                failure_times = session.query(WorkOrder.start_time).filter(
                    WorkOrder.equipment_id == equipment_id,
                    WorkOrder.type == WorkOrderType.CORRECTIVE,
                    WorkOrder.start_time.isnot(None),
                ).order_by(WorkOrder.start_time).all()

                if len(failure_times) >= 2:
                    first = failure_times[0][0]
                    last  = failure_times[-1][0]
                    if first != last:
                        span_hours = (last - first).total_seconds() / 3600
                        mtbf = span_hours / (cm_count - 1)

            return {
                "equipment_id":        equipment_id,
                "equipment_name":      equipment.name,
                "equipment_status":    equipment.status,
                "total_work_orders":   total_wo,
                "completed_work_orders": row.completed or 0,
                "pm_work_orders":      row.pm or 0,
                "cm_work_orders":      cm_count,
                "avg_repair_time_hours":  round(avg_repair, 2),
                "total_downtime_hours":   round(total_down, 2),
                "pm_compliance_rate":     round(pm_compliance, 2),
                "mtbf_hours":          round(mtbf, 2),
                "mttr_hours":          round(avg_repair, 2),
                "failure_count":       cm_count,
            }

    # ─────────────────────────── KPI METHODS ────────────────────────────────

    def get_oee_metrics(self, equipment_id=None, start_date=None, end_date=None):
        """OEE: Availability × Performance × Quality"""
        with self._session() as session:
            query = session.query(Equipment)
            if equipment_id:
                query = query.filter(Equipment.id == equipment_id)

            results = []
            for eq in query.all():
                total_hours  = 720
                downtime     = self._get_downtime_internal(session, eq.id, start_date, end_date)
                availability = ((total_hours - downtime) / total_hours) * 100
                performance  = 95
                quality      = 98
                oee          = (availability * performance * quality) / 10000

                results.append({
                    "equipment_id":   eq.id,
                    "equipment_name": eq.name,
                    "availability":   round(availability, 2),
                    "performance":    round(performance, 2),
                    "quality":        round(quality, 2),
                    "oee":            round(oee, 2),
                })
            return results

    def get_mtbf(self, equipment_id=None, start_date=None, end_date=None):
        """MTBF = Total Operating Time / Number of Failures"""
        with self._session() as session:
            query = session.query(
                Equipment.id,
                Equipment.name,
                func.count(WorkOrder.id).label("failure_count"),
            ).outerjoin(WorkOrder, and_(
                WorkOrder.equipment_id == Equipment.id,
                WorkOrder.type == WorkOrderType.CORRECTIVE,
                WorkOrder.status == WorkOrderStatus.COMPLETED,
            ))

            if equipment_id:
                query = query.filter(Equipment.id == equipment_id)
            if start_date:
                query = query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                query = query.filter(WorkOrder.created_at <= end_date)

            query = query.group_by(Equipment.id, Equipment.name)

            results = []
            for eq_id, eq_name, failures in query.all():
                operating_hours = 720
                mtbf = operating_hours / failures if failures > 0 else operating_hours
                results.append({
                    "equipment_id":   eq_id,
                    "equipment_name": eq_name,
                    "mtbf_hours":     round(mtbf, 2),
                    "failure_count":  failures,
                })
            return results

    def get_mttr(self, equipment_id=None, start_date=None, end_date=None):
        """MTTR = Total Repair Time / Number of Repairs"""
        with self._session() as session:
            query = session.query(
                Equipment.id,
                Equipment.name,
                (func.avg(
                    func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
                ) * 24).label("avg_repair_hours"),
                func.count(WorkOrder.id).label("repair_count"),
            ).join(WorkOrder, and_(
                WorkOrder.equipment_id == Equipment.id,
                WorkOrder.type == WorkOrderType.CORRECTIVE,
                WorkOrder.status == WorkOrderStatus.COMPLETED,
                WorkOrder.start_time.isnot(None),
                WorkOrder.end_time.isnot(None),
            ))

            if equipment_id:
                query = query.filter(Equipment.id == equipment_id)
            if start_date:
                query = query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                query = query.filter(WorkOrder.created_at <= end_date)

            query = query.group_by(Equipment.id, Equipment.name)

            results = []
            for eq_id, eq_name, avg_hours, count in query.all():
                results.append({
                    "equipment_id":   eq_id,
                    "equipment_name": eq_name,
                    "mttr_hours":     round(avg_hours or 0, 2),
                    "repair_count":   count,
                })
            return results

    def get_pm_cm_ratio(self, start_date=None, end_date=None):
        """PM/CM Ratio — higher is better"""
        with self._session() as session:
            query = session.query(
                func.sum(case((WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM]), 1), else_=0)).label("pm"),
                func.sum(case((WorkOrder.type == WorkOrderType.CORRECTIVE, 1), else_=0)).label("cm"),
            ).filter(WorkOrder.status == WorkOrderStatus.COMPLETED)

            if start_date:
                query = query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                query = query.filter(WorkOrder.created_at <= end_date)

            row = query.one()
            pm_count = row.pm or 0
            cm_count = row.cm or 0
            ratio    = pm_count / cm_count if cm_count > 0 else float(pm_count)

            return {
                "preventive_count": pm_count,
                "corrective_count": cm_count,
                "ratio":            round(ratio, 2),
                "total":            pm_count + cm_count,
            }

    def get_cost_analysis(self, start_date=None, end_date=None):
        """Maintenance cost breakdown by type (estimated)"""
        with self._session() as session:
            query = session.query(
                WorkOrder.type,
                func.count(WorkOrder.id).label("count"),
            ).filter(WorkOrder.status == WorkOrderStatus.COMPLETED)

            if start_date:
                query = query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                query = query.filter(WorkOrder.created_at <= end_date)

            query = query.group_by(WorkOrder.type)

            results    = []
            total_cost = 0
            for wo_type, count in query.all():
                estimated_cost = count * 500
                total_cost    += estimated_cost
                results.append({
                    "type":       wo_type.name,
                    "total_cost": round(estimated_cost, 2),
                    "count":      count,
                    "avg_cost":   500.0,
                })

            for r in results:
                r["percentage"] = round((r["total_cost"] / total_cost * 100), 2) if total_cost > 0 else 0

            return {"breakdown": results, "total_cost": round(total_cost, 2)}

    def get_schedule_compliance(self, start_date=None, end_date=None):
        """Percentage of PM tasks completed on time"""
        with self._session() as session:
            query = session.query(
                func.count(WorkOrder.id).label("total"),
                func.sum(case(
                    (WorkOrder.end_time <= WorkOrder.scheduled_date, 1),
                    else_=0
                )).label("on_time"),
            ).filter(
                WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM]),
                WorkOrder.status == WorkOrderStatus.COMPLETED,
                WorkOrder.scheduled_date.isnot(None),
                WorkOrder.end_time.isnot(None),
            )

            if start_date:
                query = query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                query = query.filter(WorkOrder.created_at <= end_date)

            row        = query.one()
            total      = row.total or 0
            on_time    = row.on_time or 0
            compliance = (on_time / total * 100) if total > 0 else 0

            return {
                "total_tasks":    total,
                "on_time":        on_time,
                "late":           total - on_time,
                "compliance_rate": round(compliance, 2),
            }

    def get_equipment_risk_score(self):
        """
        Risk = Failure Frequency × Downtime Impact.
        Fixed: was N+1 queries (2 queries per equipment in a loop).
        Now: 1 query for all equipment data at once.
        """
        with self._session() as session:
            cutoff = datetime.now() - timedelta(days=30)

            # Single query: join Equipment with WorkOrder aggregates
            rows = session.query(
                Equipment.id,
                Equipment.name,
                func.sum(case((
                    and_(
                        WorkOrder.type == WorkOrderType.CORRECTIVE,
                        WorkOrder.created_at >= cutoff,
                    ), 1), else_=0)).label("recent_failures"),
                func.avg(case((
                    and_(
                        WorkOrder.start_time.isnot(None),
                        WorkOrder.end_time.isnot(None),
                    ),
                    func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
                ), else_=None)).label("avg_downtime_days"),
            ).outerjoin(WorkOrder, WorkOrder.equipment_id == Equipment.id
            ).group_by(Equipment.id, Equipment.name).all()

            results = []
            for eq_id, eq_name, failures, avg_down in rows:
                failures    = failures or 0
                avg_down    = avg_down or 0
                avg_hours   = avg_down * 24
                risk_score  = min(100, (failures * 10) + (avg_hours * 5))

                results.append({
                    "equipment_id":       eq_id,
                    "equipment_name":     eq_name,
                    "failure_count":      failures,
                    "avg_downtime_hours": round(avg_hours, 2),
                    "avg_cost":           0.0,
                    "risk_score":         round(risk_score, 2),
                    "risk_level":         "HIGH" if risk_score > 70 else "MEDIUM" if risk_score > 40 else "LOW",
                })

            return sorted(results, key=lambda x: x["risk_score"], reverse=True)

    def get_technician_performance(self, start_date=None, end_date=None):
        """Technician workload and efficiency — single grouped query"""
        with self._session() as session:
            query = session.query(
                User.id,
                User.full_name,
                func.count(WorkOrder.id).label("total_tasks"),
                func.sum(case((WorkOrder.status == WorkOrderStatus.COMPLETED, 1), else_=0)).label("completed_tasks"),
                (func.avg(
                    func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
                ) * 24).label("avg_completion_hours"),
            ).join(WorkOrder, User.id == WorkOrder.technician_id)

            if start_date:
                query = query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                query = query.filter(WorkOrder.created_at <= end_date)

            query = query.group_by(User.id, User.full_name)

            results = []
            for user_id, name, total, completed, avg_hours in query.all():
                completion_rate = (completed / total * 100) if total > 0 else 0
                results.append({
                    "technician_id":         user_id,
                    "technician_name":       name,
                    "total_tasks":           total,
                    "completed_tasks":       completed,
                    "completion_rate":       round(completion_rate, 2),
                    "avg_completion_hours":  round(avg_hours or 0, 2),
                })
            return results

    def get_monthly_trends(self, months=6):
        """Work order trends over time — single grouped query"""
        with self._session() as session:
            start_date = datetime.now() - timedelta(days=months * 30)

            rows = session.query(
                extract("year",  WorkOrder.created_at).label("year"),
                extract("month", WorkOrder.created_at).label("month"),
                WorkOrder.type,
                func.count(WorkOrder.id).label("count"),
            ).filter(
                WorkOrder.created_at >= start_date,
                WorkOrder.status == WorkOrderStatus.COMPLETED,
            ).group_by("year", "month", WorkOrder.type
            ).order_by("year", "month").all()

            return [
                {
                    "year":       int(year),
                    "month":      int(month),
                    "type":       wo_type.name,
                    "count":      count,
                    "total_cost": 0.0,
                }
                for year, month, wo_type, count in rows
            ]

    # ─────────────────────────── PRIVATE HELPERS ────────────────────────────

    def _get_downtime_internal(self, session, equipment_id, start_date, end_date):
        """Internal helper — reuses an existing session, no new connection opened."""
        query = session.query(
            func.sum(
                func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
            )
        ).filter(
            WorkOrder.equipment_id == equipment_id,
            WorkOrder.type == WorkOrderType.CORRECTIVE,
            WorkOrder.start_time.isnot(None),
            WorkOrder.end_time.isnot(None),
        )

        if start_date:
            query = query.filter(WorkOrder.created_at >= start_date)
        if end_date:
            query = query.filter(WorkOrder.created_at <= end_date)

        downtime_days = query.scalar() or 0
        return downtime_days * 24
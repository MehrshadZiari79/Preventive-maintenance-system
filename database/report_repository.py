# database/report_repository.py
from sqlalchemy import func, and_, case, text
from datetime import datetime, timedelta
from database.work_order import WorkOrder, WorkOrderStatus, WorkOrderType
from database.models import Equipment, User, SparePart, SparePartTransaction, Inspection, InspectionResult, InspectionCheckpoint, ProductionLog, PMSchedule
from sqlalchemy.orm import joinedload


class ReportRepository:
    def __init__(self, session_factory):
        self.Session = session_factory

    # ── KPI Summary ──────────────────────────────────────────────────
    def get_kpi_summary(self, start_date=None, end_date=None):
        session = self.Session()
        try:
            wo_query = session.query(
                func.count(WorkOrder.id).label("total_wo"),
                func.sum(case([(WorkOrder.status == WorkOrderStatus.APPROVED, 1)], else_=0)).label("completed"),
                func.sum(case([(WorkOrder.status == WorkOrderStatus.PENDING, 1)], else_=0)).label("pending"),
                func.sum(case([(WorkOrder.status == WorkOrderStatus.IN_PROGRESS, 1)], else_=0)).label("in_progress"),
                func.sum(case([(WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM]), 1)], else_=0)).label("pm_total"),
                func.sum(case([(WorkOrder.type == WorkOrderType.CORRECTIVE, 1)], else_=0)).label("cm_total"),
                func.sum(case([(WorkOrder.type == WorkOrderType.EMERGENCY, 1)], else_=0)).label("emergency_total"),
            )
            if start_date:
                wo_query = wo_query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                wo_query = wo_query.filter(WorkOrder.created_at <= end_date)
            wo_stats = wo_query.one()

            now = datetime.now()
            overdue_query = session.query(WorkOrder).filter(
                WorkOrder.status.in_([WorkOrderStatus.PENDING, WorkOrderStatus.IN_PROGRESS]),
                WorkOrder.scheduled_date < now
            )
            if start_date:
                overdue_query = overdue_query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                overdue_query = overdue_query.filter(WorkOrder.created_at <= end_date)
            overdue = overdue_query.count()

            avg_time_sql = text("""
                SELECT AVG(DATEDIFF(second, start_time, end_time) / 3600.0)
                FROM work_orders
                WHERE status = 'APPROVED'
                AND start_time IS NOT NULL
                AND end_time IS NOT NULL
            """)
            params = {}
            if start_date and end_date:
                avg_time_sql = text("""
                    SELECT AVG(DATEDIFF(second, start_time, end_time) / 3600.0)
                    FROM work_orders
                    WHERE status = 'APPROVED'
                    AND start_time IS NOT NULL
                    AND end_time IS NOT NULL
                    AND created_at BETWEEN :start AND :end
                """)
                params = {'start': start_date, 'end': end_date}
            elif start_date:
                avg_time_sql = text("""
                    SELECT AVG(DATEDIFF(second, start_time, end_time) / 3600.0)
                    FROM work_orders
                    WHERE status = 'APPROVED'
                    AND start_time IS NOT NULL
                    AND end_time IS NOT NULL
                    AND created_at >= :start
                """)
                params['start'] = start_date
            elif end_date:
                avg_time_sql = text("""
                    SELECT AVG(DATEDIFF(second, start_time, end_time) / 3600.0)
                    FROM work_orders
                    WHERE status = 'APPROVED'
                    AND start_time IS NOT NULL
                    AND end_time IS NOT NULL
                    AND created_at <= :end
                """)
                params['end'] = end_date
            avg_time_raw = session.execute(avg_time_sql, params).scalar() or 0

            eq_stats = session.query(
                func.count(Equipment.id).label("total_eq"),
                func.sum(case([(Equipment.status == "operational", 1)], else_=0)).label("operational")
            ).one()

            pm_wos = session.query(WorkOrder).options(joinedload(WorkOrder.schedule)).filter(
                WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM]),
                WorkOrder.status == WorkOrderStatus.APPROVED,
                WorkOrder.scheduled_date.isnot(None),
                WorkOrder.end_time.isnot(None)
            )
            if start_date:
                pm_wos = pm_wos.filter(WorkOrder.created_at >= start_date)
            if end_date:
                pm_wos = pm_wos.filter(WorkOrder.created_at <= end_date)
            pm_wos = pm_wos.all()

            on_time_pm = 0
            pm_work_orders_total = len(pm_wos)
            for wo in pm_wos:
                scheduled = wo.scheduled_date
                end = wo.end_time
                if wo.deadline is not None:
                    deadline = wo.deadline
                elif wo.schedule_id and wo.schedule:
                    est_days = wo.schedule.estimated_duration or 0
                    deadline = scheduled + timedelta(days=est_days)
                else:
                    deadline = scheduled + timedelta(days=1)
                if end <= deadline:
                    on_time_pm += 1

            pm_compliance = (on_time_pm / pm_work_orders_total * 100) if pm_work_orders_total > 0 else 0

            return {
                "total_work_orders": wo_stats.total_wo or 0,
                "completed_work_orders": wo_stats.completed or 0,
                "pending_work_orders": wo_stats.pending or 0,
                "in_progress_work_orders": wo_stats.in_progress or 0,
                "emergency_work_orders": wo_stats.emergency_total or 0,
                "overdue_work_orders": overdue,
                "total_equipment": eq_stats.total_eq or 0,
                "operational_equipment": eq_stats.operational or 0,
                "avg_completion_time_hours": round(avg_time_raw, 2),
                "pm_compliance_rate": round(pm_compliance, 2),
                "cm_work_orders": wo_stats.cm_total or 0,
            }
        finally:
            session.close()

    # ── Backlog Analysis ─────────────────────────────────────────────
    def get_backlog_analysis(self, start_date=None, end_date=None):
        session = self.Session()
        try:
            now = datetime.now()
            query = session.query(
                func.sum(case([(WorkOrder.status == WorkOrderStatus.PENDING, 1)], else_=0)).label("pending"),
                func.sum(case([(WorkOrder.status == WorkOrderStatus.IN_PROGRESS, 1)], else_=0)).label("in_progress"),
                func.sum(case([
                    (and_(
                        WorkOrder.status.in_([WorkOrderStatus.PENDING, WorkOrderStatus.IN_PROGRESS]),
                        WorkOrder.scheduled_date < now
                    ), 1)
                ], else_=0)).label("overdue"),
            )
            if start_date:
                query = query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                query = query.filter(WorkOrder.created_at <= end_date)
            row = query.one()
            return {
                "pending": row.pending or 0,
                "in_progress": row.in_progress or 0,
                "overdue": row.overdue or 0,
                "total_backlog": (row.pending or 0) + (row.in_progress or 0),
            }
        finally:
            session.close()

    def get_delay_summary(self, start_date=None, end_date=None):
        session = self.Session()
        try:
            query = session.query(
                func.coalesce(func.sum(WorkOrder.delay_minutes), 0).label("total_minutes"),
                func.count(WorkOrder.id).label("delayed_count")
            ).filter(WorkOrder.delay_minutes > 0)
            if start_date:
                query = query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                query = query.filter(WorkOrder.created_at <= end_date)
            row = query.one()
            return {"total_minutes": int(row.total_minutes), "delayed_count": row.delayed_count}
        finally:
            session.close()

    # ── Rejection Percentage ────────────────────────────────────────
    def get_rejection_percentage(self, start_date=None, end_date=None) -> dict:
        session = self.Session()
        try:
            total_q = session.query(func.count(WorkOrder.id)).filter(WorkOrder.status.in_([
                WorkOrderStatus.APPROVED, WorkOrderStatus.REJECTED]))
            rejected_q = session.query(func.count(WorkOrder.id)).filter(WorkOrder.status == WorkOrderStatus.REJECTED)
            if start_date:
                total_q = total_q.filter(WorkOrder.created_at >= start_date)
                rejected_q = rejected_q.filter(WorkOrder.created_at >= start_date)
            if end_date:
                total_q = total_q.filter(WorkOrder.created_at <= end_date)
                rejected_q = rejected_q.filter(WorkOrder.created_at <= end_date)
            total = total_q.scalar() or 0
            rejected = rejected_q.scalar() or 0
            pct = (rejected / total * 100) if total > 0 else 0.0
            return {"total": total, "rejected": rejected, "percentage": pct}
        finally:
            session.close()

    # ── Equipment Report (single equipment) ────────────────────────
    def get_equipment_report(self, equipment_id: int, start_date=None, end_date=None):
        session = self.Session()
        try:
            eq = session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if not eq:
                return None

            sql = """
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN type IN ('PREVENTIVE','PM') THEN 1 ELSE 0 END) AS pm,
                    SUM(CASE WHEN type = 'CORRECTIVE' THEN 1 ELSE 0 END) AS cm,
                    AVG(CASE WHEN start_time IS NOT NULL AND end_time IS NOT NULL 
                             THEN DATEDIFF(second, start_time, end_time) / 3600.0 
                             ELSE NULL END) AS avg_repair_hours,
                    SUM(CASE WHEN type IN ('CORRECTIVE','EMERGENCY','PREVENTIVE','PM') 
                              AND start_time IS NOT NULL AND end_time IS NOT NULL 
                             THEN DATEDIFF(second, start_time, end_time) / 3600.0 
                             ELSE 0 END) AS total_downtime_hours
                FROM work_orders
                WHERE equipment_id = :eq_id
            """
            params = {'eq_id': equipment_id}
            if start_date:
                sql += " AND created_at >= :start"
                params['start'] = start_date
            if end_date:
                sql += " AND created_at <= :end"
                params['end'] = end_date

            row = session.execute(text(sql), params).fetchone()
            total_wo = row[0] or 0
            completed = row[1] or 0
            pm = row[2] or 0
            cm = row[3] or 0
            avg_repair = row[4] or 0
            total_downtime = row[5] or 0

            wo_count = session.execute(
                text("""
                    SELECT COUNT(*) FROM work_orders
                    WHERE equipment_id = :eq_id
                    AND status = 'APPROVED'
                    AND start_time IS NOT NULL
                    AND end_time IS NOT NULL
                    AND type IN ('CORRECTIVE','EMERGENCY','PREVENTIVE','PM')
                """), {'eq_id': equipment_id}
            ).scalar() or 1
            avg_downtime = total_downtime / wo_count if wo_count > 0 else 0.0

            operating_hours = self._get_operating_hours(session, equipment_id, start_date, end_date)
            mtbf = operating_hours / cm if cm > 0 else operating_hours

            return {
                "equipment_id": eq.id,
                "equipment_name": eq.name,
                "equipment_status": eq.status,
                "total_work_orders": total_wo,
                "completed_work_orders": completed,
                "pm_work_orders": pm,
                "cm_work_orders": cm,
                "avg_repair_time_hours": round(avg_repair, 2),
                "total_downtime_hours": round(total_downtime, 2),
                "avg_downtime_hours": round(avg_downtime, 2),
                "pm_compliance_rate": round((pm / total_wo * 100) if total_wo > 0 else 0, 2),
                "mtbf_hours": round(mtbf, 2),
                "mttr_hours": round(avg_repair, 2),
                "failure_count": cm,
            }
        finally:
            session.close()

    def get_mtbf(self, equipment_id=None, start_date=None, end_date=None):
        session = self.Session()
        try:
            query = session.query(Equipment)
            if equipment_id:
                query = query.filter(Equipment.id == equipment_id)
            results = []
            for eq in query.all():
                failures = session.query(func.count(WorkOrder.id)).filter(
                    WorkOrder.equipment_id == eq.id,
                    WorkOrder.type.in_([WorkOrderType.CORRECTIVE, WorkOrderType.EMERGENCY]),
                    WorkOrder.status == WorkOrderStatus.APPROVED,
                )
                if start_date:
                    failures = failures.filter(WorkOrder.created_at >= start_date)
                if end_date:
                    failures = failures.filter(WorkOrder.created_at <= end_date)
                failure_count = failures.scalar() or 0
                operating_hours = self._get_operating_hours(session, eq.id, start_date, end_date)
                mtbf = operating_hours / failure_count if failure_count > 0 else operating_hours
                results.append({
                    "equipment_id": eq.id,
                    "equipment_name": eq.name,
                    "mtbf_hours": round(mtbf, 2),
                    "failure_count": failure_count,
                })
            return results
        finally:
            session.close()

    def get_mttr(self, equipment_id=None, start_date=None, end_date=None):
        session = self.Session()
        try:
            query = session.query(Equipment)
            if equipment_id:
                query = query.filter(Equipment.id == equipment_id)
            results = []
            for eq in query.all():
                repair_sql = text("""
                    SELECT AVG(DATEDIFF(second, start_time, end_time) / 3600.0)
                    FROM work_orders
                    WHERE equipment_id = :eq_id
                    AND type IN ('CORRECTIVE', 'EMERGENCY')
                    AND status = 'APPROVED'
                    AND start_time IS NOT NULL
                    AND end_time IS NOT NULL
                """)
                params = {'eq_id': eq.id}
                avg_hours = session.execute(repair_sql, params).scalar() or 0
                count_sql = text("""
                    SELECT COUNT(*)
                    FROM work_orders
                    WHERE equipment_id = :eq_id
                    AND type IN ('CORRECTIVE', 'EMERGENCY')
                    AND status = 'APPROVED'
                    AND start_time IS NOT NULL
                    AND end_time IS NOT NULL
                """)
                cnt = session.execute(count_sql, params).scalar() or 0
                results.append({
                    "equipment_id": eq.id,
                    "equipment_name": eq.name,
                    "mttr_hours": round(avg_hours, 2),
                    "repair_count": cnt,
                })
            return results
        finally:
            session.close()

    def get_oee_metrics(self, equipment_id=None, start_date=None, end_date=None):
        session = self.Session()
        try:
            query = session.query(Equipment)
            if equipment_id:
                query = query.filter(Equipment.id == equipment_id)
            results = []
            for eq in query.all():
                planned_hours = self._get_planned_hours(session, eq.id, start_date, end_date)
                downtime_seconds = self._get_downtime_internal(session, eq.id, start_date, end_date)
                downtime_hours = downtime_seconds / 3600.0
                availability = ((planned_hours - downtime_hours) / planned_hours * 100) if planned_hours > 0 else 0
                performance = 95.0
                quality = self._get_inspection_pass_rate(session, eq.id, start_date, end_date)
                oee = (availability * performance * quality) / 10000
                results.append({
                    "equipment_id": eq.id,
                    "equipment_name": eq.name,
                    "availability": round(availability, 2),
                    "performance": round(performance, 2),
                    "quality": round(quality, 2),
                    "oee": round(oee, 2),
                })
            return results
        finally:
            session.close()

    def get_pm_cm_ratio(self, start_date=None, end_date=None):
        session = self.Session()
        try:
            query = session.query(
                func.sum(case([(WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM]), 1)], else_=0)).label("pm"),
                func.sum(case([(WorkOrder.type == WorkOrderType.CORRECTIVE, 1)], else_=0)).label("cm"),
                func.sum(case([(WorkOrder.type == WorkOrderType.EMERGENCY, 1)], else_=0)).label("emergency"),
            ).filter(WorkOrder.status == WorkOrderStatus.APPROVED)
            if start_date:
                query = query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                query = query.filter(WorkOrder.created_at <= end_date)
            row = query.one()
            pm = row.pm or 0
            cm = row.cm or 0
            emergency = row.emergency or 0
            ratio = pm / cm if cm > 0 else float(pm)
            return {
                "preventive_count": pm,
                "corrective_count": cm,
                "emergency_count": emergency,
                "ratio": round(ratio, 2),
                "total": pm + cm + emergency,
            }
        finally:
            session.close()

    def get_schedule_compliance(self, start_date=None, end_date=None):
        session = self.Session()
        try:
            query = session.query(WorkOrder).options(
                joinedload(WorkOrder.schedule)
            ).filter(
                WorkOrder.status == WorkOrderStatus.APPROVED,
                WorkOrder.scheduled_date.isnot(None),
                WorkOrder.end_time.isnot(None)
            )
            if start_date:
                query = query.filter(WorkOrder.scheduled_date >= start_date)
            if end_date:
                query = query.filter(WorkOrder.scheduled_date <= end_date)

            on_time = 0
            late = 0
            for wo in query.all():
                scheduled = wo.scheduled_date
                end = wo.end_time
                if wo.deadline is not None:
                    deadline = wo.deadline
                elif wo.schedule_id and wo.schedule:
                    est_days = wo.schedule.estimated_duration or 0
                    deadline = scheduled + timedelta(days=est_days)
                else:
                    deadline = scheduled + timedelta(days=1)

                if end <= deadline:
                    on_time += 1
                else:
                    late += 1

            total = on_time + late
            rate = (on_time / total * 100) if total > 0 else 0
            return {
                "on_time": on_time,
                "late": late,
                "total_tasks": total,
                "compliance_rate": round(rate, 1)
            }
        finally:
            session.close()

    def get_cost_analysis(self, start_date=None, end_date=None):
        session = self.Session()
        try:
            where_parts = ["wo.status = 'APPROVED'",
                           "(spt.transaction_type = 'OUT' OR spt.transaction_type IS NULL)"]
            params = {}
            if start_date:
                where_parts.append("wo.created_at >= :start")
                params['start'] = start_date
            if end_date:
                where_parts.append("wo.created_at <= :end")
                params['end'] = end_date
            where_clause = " AND ".join(where_parts)

            sql = f"""
                SELECT
                    wo.type,
                    ISNULL(SUM(sp.unit_price * spt.quantity), 0) AS part_cost,
                    ISNULL(SUM(CASE WHEN wo.start_time IS NOT NULL AND wo.end_time IS NOT NULL
                                   THEN DATEDIFF(second, wo.start_time, wo.end_time) / 3600.0 * 50
                                   ELSE 0 END), 0) AS labor_cost,
                    ISNULL(SUM(wo.manual_cost), 0) AS manual_cost
                FROM work_orders wo
                LEFT JOIN spare_part_transactions spt
                    ON (spt.reference = CAST(wo.id AS VARCHAR(50))
                        OR spt.reference = 'WO-' + CAST(wo.id AS VARCHAR(50)))
                LEFT JOIN spare_parts sp ON sp.id = spt.part_id
                WHERE {where_clause}
                GROUP BY wo.type
            """
            result = session.execute(text(sql), params).fetchall()
            breakdown = []
            total_cost = 0.0
            for row in result:
                type_name = row[0].name if hasattr(row[0], 'name') else str(row[0])
                part = float(row[1])
                labor = float(row[2])
                manual = float(row[3])
                cost = part + labor + manual
                breakdown.append({
                    "type": type_name,
                    "total_cost": round(cost, 2),
                    "part_cost": round(part, 2),
                    "labor_cost": round(labor, 2),
                    "manual_cost": round(manual, 2),
                })
                total_cost += cost
            for b in breakdown:
                b["percentage"] = round((b["total_cost"] / total_cost * 100), 2) if total_cost > 0 else 0
            return {"breakdown": breakdown, "total_cost": round(total_cost, 2)}
        finally:
            session.close()

    def get_equipment_risk_score(self):
        session = self.Session()
        try:
            cutoff = datetime.now() - timedelta(days=30)
            rows = session.query(
                Equipment.id,
                Equipment.name,
                Equipment.criticality_level,
                func.sum(
                    case(
                        [(and_(WorkOrder.type.in_([WorkOrderType.CORRECTIVE, WorkOrderType.EMERGENCY]), WorkOrder.created_at >= cutoff), 1)],
                        else_=0
                    )
                ).label("recent_failures"),
            ).outerjoin(WorkOrder, WorkOrder.equipment_id == Equipment.id
            ).group_by(Equipment.id, Equipment.name, Equipment.criticality_level).all()

            criticality_factor = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            results = []
            for eq_id, eq_name, crit, failures in rows:
                failures = failures or 0
                downtime_sql = text("""
                    SELECT AVG(DATEDIFF(second, start_time, end_time) / 3600.0)
                    FROM work_orders
                    WHERE equipment_id = :eq_id
                    AND type IN ('CORRECTIVE', 'EMERGENCY')
                    AND status = 'APPROVED'
                    AND start_time IS NOT NULL
                    AND end_time IS NOT NULL
                """)
                avg_hours = session.execute(downtime_sql, {'eq_id': eq_id}).scalar() or 0
                factor = criticality_factor.get(crit, 2)
                raw = (failures * 10) + (avg_hours * 5)
                risk_score = min(100, raw * factor)
                results.append({
                    "equipment_id": eq_id,
                    "equipment_name": eq_name,
                    "failure_count": failures,
                    "avg_downtime_hours": round(avg_hours, 2),
                    "criticality": crit,
                    "risk_score": round(risk_score, 2),
                    "risk_level": "HIGH" if risk_score > 70 else "MEDIUM" if risk_score > 40 else "LOW",
                })
            return sorted(results, key=lambda x: x["risk_score"], reverse=True)
        finally:
            session.close()

    def get_technician_performance(self, start_date=None, end_date=None):
        session = self.Session()
        try:
            sql = """
                SELECT
                    u.id,
                    u.full_name,
                    COUNT(wo.id) as total_tasks,
                    SUM(CASE WHEN wo.status = 'APPROVED' THEN 1 ELSE 0 END) as completed_tasks,
                    AVG(CASE WHEN wo.start_time IS NOT NULL AND wo.end_time IS NOT NULL
                             THEN DATEDIFF(second, wo.start_time, wo.end_time) / 3600.0
                             ELSE NULL END) as avg_completion_hours
                FROM users u
                JOIN work_orders wo ON u.id = wo.technician_id
                WHERE 1=1
            """
            params = {}
            if start_date:
                sql += " AND wo.created_at >= :start"
                params['start'] = start_date
            if end_date:
                sql += " AND wo.created_at <= :end"
                params['end'] = end_date
            sql += " GROUP BY u.id, u.full_name"
            results = session.execute(text(sql), params).fetchall()
            output = []
            for row in results:
                total = row[2] or 0
                completed = row[3] or 0
                comp_rate = (completed / total * 100) if total > 0 else 0
                output.append({
                    "technician_id": row[0],
                    "technician_name": row[1],
                    "total_tasks": total,
                    "completed_tasks": completed,
                    "completion_rate": round(comp_rate, 2),
                    "avg_completion_hours": round(row[4] or 0, 2),
                })
            return output
        finally:
            session.close()

    def get_monthly_trends(self, months=6):
        session = self.Session()
        try:
            start_date = datetime.now() - timedelta(days=months * 30)
            sql = text("""
                SELECT
                    DATEPART(year, created_at) as year,
                    DATEPART(month, created_at) as month,
                    type,
                    COUNT(*) as count
                FROM work_orders
                WHERE created_at >= :start
                GROUP BY DATEPART(year, created_at), DATEPART(month, created_at), type
                ORDER BY year, month
            """)
            results = session.execute(sql, {'start': start_date}).fetchall()
            output = []
            for row in results:
                output.append({
                    "year": row[0],
                    "month": row[1],
                    "type": row[2].name if hasattr(row[2], 'name') else str(row[2]),
                    "count": row[3],
                })
            return output
        finally:
            session.close()

    def get_inspection_effectiveness(self, start_date=None, end_date=None):
        session = self.Session()
        try:
            query = session.query(
                func.count(InspectionResult.id).label("total"),
                func.sum(case([(InspectionResult.result == "pass", 1)], else_=0)).label("passed"),
            ).join(Inspection, Inspection.id == InspectionResult.inspection_id
            ).filter(Inspection.status == "completed")
            if start_date:
                query = query.filter(Inspection.completed_at >= start_date)
            if end_date:
                query = query.filter(Inspection.completed_at <= end_date)
            row = query.one()
            total = row.total or 1
            passed = row.passed or 0
            return {
                "total_checkpoints": total,
                "passed": passed,
                "effectiveness": round(passed / total * 100, 2),
            }
        finally:
            session.close()

    def get_cleaning_score(self, start_date=None, end_date=None):
        session = self.Session()
        try:
            query = session.query(
                func.count(InspectionResult.id).label("total"),
                func.sum(case([(InspectionResult.result == "pass", 1)], else_=0)).label("passed"),
            ).join(InspectionCheckpoint, InspectionCheckpoint.id == InspectionResult.checkpoint_id
            ).join(Inspection, Inspection.id == InspectionResult.inspection_id
            ).filter(
                Inspection.status == "completed",
                InspectionCheckpoint.checkpoint_type == "safety"
            )
            if start_date:
                query = query.filter(Inspection.completed_at >= start_date)
            if end_date:
                query = query.filter(Inspection.completed_at <= end_date)
            row = query.one()
            total = row.total or 1
            passed = row.passed or 0
            return {
                "total_cleaning_checks": total,
                "passed": passed,
                "score": round(passed / total * 100, 2),
            }
        finally:
            session.close()

    def get_spare_parts_turnover(self):
        session = self.Session()
        try:
            one_year_ago = datetime.now() - timedelta(days=365)
            consumption = session.query(
                func.sum(SparePartTransaction.quantity * SparePart.unit_price)
            ).join(
                SparePart, SparePart.id == SparePartTransaction.part_id
            ).filter(
                SparePartTransaction.transaction_type == 'OUT',
                SparePartTransaction.created_at >= one_year_ago
            ).scalar() or 0
            avg_inventory = session.query(
                func.sum(SparePart.current_stock * SparePart.unit_price)
            ).scalar() or 0
            turnover = consumption / avg_inventory if avg_inventory > 0 else 0
            return {
                "annual_consumption": round(consumption, 2),
                "average_inventory_value": round(avg_inventory, 2),
                "turnover_ratio": round(turnover, 2),
            }
        finally:
            session.close()

    # ── Optimised all‑equipment performance (raw SQL, fixed) ────────
    def get_all_equipment_performance(self, start_date=None, end_date=None):
        """
        Returns a list of dicts with performance metrics for ALL equipment.
        Uses raw SQL with correct column references (no alias 'wo').
        """
        session = self.Session()
        try:
            # Build date conditions (without alias)
            params = {}
            wo_date_condition = ""
            prod_date_condition = ""
            if start_date and end_date:
                wo_date_condition = " AND created_at BETWEEN :start AND :end"
                prod_date_condition = " AND log_date BETWEEN :start AND :end"
                params['start'] = start_date
                params['end'] = end_date
            elif start_date:
                wo_date_condition = " AND created_at >= :start"
                prod_date_condition = " AND log_date >= :start"
                params['start'] = start_date
            elif end_date:
                wo_date_condition = " AND created_at <= :end"
                prod_date_condition = " AND log_date <= :end"
                params['end'] = end_date

            # 1. Work order aggregates
            wo_sql = f"""
                SELECT
                    equipment_id,
                    COUNT(*) AS total_wo,
                    SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN type IN ('PREVENTIVE','PM') THEN 1 ELSE 0 END) AS pm,
                    SUM(CASE WHEN type = 'CORRECTIVE' THEN 1 ELSE 0 END) AS cm,
                    SUM(CASE WHEN type = 'EMERGENCY' THEN 1 ELSE 0 END) AS em,
                    SUM(CASE WHEN type IN ('CORRECTIVE','EMERGENCY')
                              AND start_time IS NOT NULL
                              AND end_time IS NOT NULL
                             THEN DATEDIFF(second, start_time, end_time) / 3600.0
                             ELSE 0 END) AS total_downtime_hours
                FROM work_orders
                WHERE 1=1 {wo_date_condition}
                GROUP BY equipment_id
            """
            wo_result = session.execute(text(wo_sql), params).fetchall()
            wo_stats = {row[0]: row for row in wo_result}

            # 2. Production logs
            prod_sql = f"""
                SELECT
                    equipment_id,
                    SUM(operating_hours) AS operating_hours,
                    SUM(planned_hours) AS planned_hours
                FROM production_logs
                WHERE 1=1 {prod_date_condition}
                GROUP BY equipment_id
            """
            prod_result = session.execute(text(prod_sql), params).fetchall()
            prod_stats = {row[0]: row for row in prod_result}

            # 3. Get all equipment
            eqs = session.query(Equipment).all()

            results = []
            for eq in eqs:
                wo = wo_stats.get(eq.id)
                prod = prod_stats.get(eq.id)

                total_wo = wo[1] if wo else 0
                completed = wo[2] if wo else 0
                pm = wo[3] if wo else 0
                cm = wo[4] if wo else 0
                em = wo[5] if wo else 0
                total_downtime = wo[6] if wo else 0

                operating_hours = prod[1] if prod else 0
                planned_hours = prod[2] if prod else 0

                failures = cm + em
                mtbf = (operating_hours / failures) if failures > 0 else operating_hours
                mttr = (total_downtime / failures) if failures > 0 else 0
                availability = ((planned_hours - total_downtime) / planned_hours * 100) if planned_hours > 0 else 0

                quality = 100.0
                performance = 95.0
                oee = (availability * performance * quality) / 10000

                results.append({
                    "equipment_id": eq.id,
                    "equipment_name": eq.name,
                    "equipment_status": eq.status,
                    "total_work_orders": total_wo,
                    "completed_work_orders": completed,
                    "pm_work_orders": pm,
                    "cm_work_orders": cm,
                    "em_work_orders": em,
                    "mtbf_hours": round(mtbf, 2),
                    "mttr_hours": round(mttr, 2),
                    "availability": round(availability, 2),
                    "oee": round(oee, 2),
                    "total_downtime_hours": round(total_downtime, 2),
                })
            return results
        finally:
            session.close()

    # ── Top failure modes ──────────────────────────────────────────
    def get_top_failure_modes(self, start_date=None, end_date=None, limit=20):
        session = self.Session()
        try:
            sql = "SELECT TOP " + str(limit) + " CAST(description AS NVARCHAR(4000)) AS description, COUNT(id) AS count FROM work_orders WHERE type IN ('CORRECTIVE', 'EMERGENCY') AND status = 'APPROVED' AND description IS NOT NULL AND LEN(CAST(description AS NVARCHAR(4000))) > 0"
            params = {}
            if start_date:
                sql += " AND created_at >= :start"
                params['start'] = start_date
            if end_date:
                sql += " AND created_at <= :end"
                params['end'] = end_date
            sql += " GROUP BY CAST(description AS NVARCHAR(4000)) ORDER BY COUNT(id) DESC"
            result = session.execute(text(sql), params).fetchall()
            return [{'description': row[0], 'count': row[1]} for row in result]
        finally:
            session.close()

    # ── Helper methods ──────────────────────────────────────────────
    def _get_downtime_internal(self, session, equipment_id, start_date, end_date):
        sql = text("""
            SELECT SUM(DATEDIFF(second, start_time, end_time))
            FROM work_orders
            WHERE equipment_id = :eq_id
            AND type IN ('CORRECTIVE', 'EMERGENCY')
            AND start_time IS NOT NULL
            AND end_time IS NOT NULL
        """)
        params = {'eq_id': equipment_id}
        return session.execute(sql, params).scalar() or 0

    def _get_operating_hours(self, session, equipment_id, start_date=None, end_date=None):
        query = session.query(func.sum(ProductionLog.operating_hours)).filter(
            ProductionLog.equipment_id == equipment_id
        )
        if start_date:
            query = query.filter(ProductionLog.log_date >= start_date)
        if end_date:
            query = query.filter(ProductionLog.log_date <= end_date)
        return query.scalar() or 0

    def _get_planned_hours(self, session, equipment_id, start_date=None, end_date=None):
        query = session.query(func.sum(ProductionLog.planned_hours)).filter(
            ProductionLog.equipment_id == equipment_id
        )
        if start_date:
            query = query.filter(ProductionLog.log_date >= start_date)
        if end_date:
            query = query.filter(ProductionLog.log_date <= end_date)
        return query.scalar() or 0

    def _get_inspection_pass_rate(self, session, equipment_id, start_date, end_date):
        query = session.query(
            func.count(InspectionResult.id).label("total"),
            func.sum(case([(InspectionResult.result == "pass", 1)], else_=0)).label("passed"),
        ).join(Inspection, Inspection.id == InspectionResult.inspection_id
        ).filter(
            Inspection.equipment_id == equipment_id,
            Inspection.status == "completed",
        )
        if start_date:
            query = query.filter(Inspection.completed_at >= start_date)
        if end_date:
            query = query.filter(Inspection.completed_at <= end_date)
        row = query.one()
        total = row.total or 1
        passed = row.passed or 0
        return (passed / total) * 100
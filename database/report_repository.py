# database/report_repository.py
from sqlalchemy import func, extract, and_, case, String
from datetime import datetime, timedelta
from database.db import SessionLocal
from database.work_order import WorkOrder, WorkOrderStatus, WorkOrderType
from database.models import Equipment, User, SparePart, SparePartTransaction, Inspection, InspectionResult, InspectionCheckpoint, ProductionLog, PMSchedule


class ReportRepository:
    def _session(self):
        return SessionLocal()

    # ==================== DASHBOARD OVERVIEW ====================
    def get_kpi_summary(self):
        with self._session() as session:
            # Work order stats
            wo_stats = session.query(
                func.count(WorkOrder.id).label("total_wo"),
                func.sum(case((WorkOrder.status == WorkOrderStatus.COMPLETED, 1), else_=0)).label("completed"),
                func.sum(case((WorkOrder.status == WorkOrderStatus.PENDING, 1), else_=0)).label("pending"),
                func.sum(case((WorkOrder.status == WorkOrderStatus.IN_PROGRESS, 1), else_=0)).label("in_progress"),
                func.sum(case((WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM]), 1), else_=0)).label("pm_total"),
                func.sum(case((WorkOrder.type == WorkOrderType.CORRECTIVE, 1), else_=0)).label("cm_total"),
            ).one()

            now = datetime.now()
            overdue = session.query(WorkOrder).filter(
                WorkOrder.status.in_([WorkOrderStatus.PENDING, WorkOrderStatus.IN_PROGRESS]),
                WorkOrder.scheduled_date < now
            ).count()

            avg_time = session.query(
                func.avg(func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)) * 24
            ).filter(
                WorkOrder.status == WorkOrderStatus.COMPLETED,
                WorkOrder.start_time.isnot(None),
                WorkOrder.end_time.isnot(None)
            ).scalar() or 0

            eq_stats = session.query(
                func.count(Equipment.id).label("total_eq"),
                func.sum(case((Equipment.status == "operational", 1), else_=0)).label("operational")
            ).one()

            # PM Compliance: on-time completed PM work orders vs total scheduled PM tasks
            total_pm_scheduled = session.query(PMSchedule).filter(PMSchedule.is_active == True).count()
            on_time_pm = session.query(WorkOrder).filter(
                WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM]),
                WorkOrder.status == WorkOrderStatus.COMPLETED,
                WorkOrder.end_time <= WorkOrder.scheduled_date
            ).count()

            pm_compliance = (on_time_pm / total_pm_scheduled * 100) if total_pm_scheduled > 0 else 0

            return {
                "total_work_orders": wo_stats.total_wo or 0,
                "completed_work_orders": wo_stats.completed or 0,
                "pending_work_orders": wo_stats.pending or 0,
                "in_progress_work_orders": wo_stats.in_progress or 0,
                "overdue_work_orders": overdue,
                "total_equipment": eq_stats.total_eq or 0,
                "operational_equipment": eq_stats.operational or 0,
                "avg_completion_time_hours": round(avg_time, 2),
                "pm_compliance_rate": round(pm_compliance, 2),
                "cm_work_orders": wo_stats.cm_total or 0,
            }

    def get_backlog_analysis(self):
        with self._session() as session:
            now = datetime.now()
            row = session.query(
                func.sum(case((WorkOrder.status == WorkOrderStatus.PENDING, 1), else_=0)).label("pending"),
                func.sum(case((WorkOrder.status == WorkOrderStatus.IN_PROGRESS, 1), else_=0)).label("in_progress"),
                func.sum(case((
                    and_(
                        WorkOrder.status.in_([WorkOrderStatus.PENDING, WorkOrderStatus.IN_PROGRESS]),
                        WorkOrder.scheduled_date < now
                    ), 1), else_=0)).label("overdue"),
            ).one()
            return {
                "pending": row.pending or 0,
                "in_progress": row.in_progress or 0,
                "overdue": row.overdue or 0,
                "total_backlog": (row.pending or 0) + (row.in_progress or 0),
            }

    # ==================== PER‑EQUIPMENT REPORT ====================
    def get_equipment_report(self, equipment_id: int, start_date=None, end_date=None):
        with self._session() as session:
            eq = session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if not eq:
                return None

            # Apply date filters to work orders
            wo_filter = WorkOrder.equipment_id == equipment_id
            if start_date:
                wo_filter = and_(wo_filter, WorkOrder.created_at >= start_date)
            if end_date:
                wo_filter = and_(wo_filter, WorkOrder.created_at <= end_date)

            wo_agg = session.query(
                func.count(WorkOrder.id).label("total"),
                func.sum(case((WorkOrder.status == WorkOrderStatus.COMPLETED, 1), else_=0)).label("completed"),
                func.sum(case((WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM]), 1), else_=0)).label("pm"),
                func.sum(case((WorkOrder.type == WorkOrderType.CORRECTIVE, 1), else_=0)).label("cm"),
                (func.avg(case((
                    and_(WorkOrder.start_time.isnot(None), WorkOrder.end_time.isnot(None)),
                    func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
                ), else_=None)) * 24).label("avg_repair_hours"),
                (func.sum(case((
                    WorkOrder.type == WorkOrderType.CORRECTIVE,
                    func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
                ), else_=0)) * 24).label("total_downtime_hours"),
            ).filter(wo_filter).one()

            total_wo = wo_agg.total or 0
            cm_count = wo_agg.cm or 0
            pm_compliance = (wo_agg.pm / total_wo * 100) if total_wo > 0 else 0
            operating_hours = self._get_operating_hours(session, equipment_id, start_date, end_date)
            mtbf = operating_hours / cm_count if cm_count > 0 else operating_hours

            return {
                "equipment_id": eq.id,
                "equipment_name": eq.name,
                "equipment_status": eq.status,
                "total_work_orders": total_wo,
                "completed_work_orders": wo_agg.completed or 0,
                "pm_work_orders": wo_agg.pm or 0,
                "cm_work_orders": cm_count,
                "avg_repair_time_hours": round(wo_agg.avg_repair_hours or 0, 2),
                "total_downtime_hours": round(wo_agg.total_downtime_hours or 0, 2),
                "pm_compliance_rate": round(pm_compliance, 2),
                "mtbf_hours": round(mtbf, 2),
                "mttr_hours": round(wo_agg.avg_repair_hours or 0, 2),
                "failure_count": cm_count,
            }

    # ==================== RELIABILITY KPIs ====================
    def get_mtbf(self, equipment_id=None, start_date=None, end_date=None):
        with self._session() as session:
            query = session.query(Equipment)
            if equipment_id:
                query = query.filter(Equipment.id == equipment_id)
            results = []
            for eq in query.all():
                failures = session.query(func.count(WorkOrder.id)).filter(
                    WorkOrder.equipment_id == eq.id,
                    WorkOrder.type == WorkOrderType.CORRECTIVE,
                    WorkOrder.status == WorkOrderStatus.COMPLETED,
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

    def get_mttr(self, equipment_id=None, start_date=None, end_date=None):
        with self._session() as session:
            query = session.query(Equipment)
            if equipment_id:
                query = query.filter(Equipment.id == equipment_id)
            results = []
            for eq in query.all():
                repairs = session.query(
                    func.sum(func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)) * 24,
                    func.count(WorkOrder.id)
                ).filter(
                    WorkOrder.equipment_id == eq.id,
                    WorkOrder.type == WorkOrderType.CORRECTIVE,
                    WorkOrder.status == WorkOrderStatus.COMPLETED,
                    WorkOrder.start_time.isnot(None),
                    WorkOrder.end_time.isnot(None),
                )
                if start_date:
                    repairs = repairs.filter(WorkOrder.created_at >= start_date)
                if end_date:
                    repairs = repairs.filter(WorkOrder.created_at <= end_date)
                total_repair_hours, repair_count = repairs.one()
                repair_count = repair_count or 0
                mttr = (total_repair_hours / repair_count) if repair_count > 0 else 0
                results.append({
                    "equipment_id": eq.id,
                    "equipment_name": eq.name,
                    "mttr_hours": round(mttr, 2),
                    "repair_count": repair_count,
                })
            return results

    def get_oee_metrics(self, equipment_id=None, start_date=None, end_date=None):
        with self._session() as session:
            query = session.query(Equipment)
            if equipment_id:
                query = query.filter(Equipment.id == equipment_id)
            results = []
            for eq in query.all():
                planned_hours = self._get_planned_hours(session, eq.id, start_date, end_date)
                downtime = self._get_downtime_internal(session, eq.id, start_date, end_date)
                availability = ((planned_hours - downtime) / planned_hours * 100) if planned_hours > 0 else 0
                performance = 95.0  # placeholder – replace with actual speed/efficiency data if available
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

    # ==================== PM/CM RATIO & COMPLIANCE ====================
    def get_pm_cm_ratio(self, start_date=None, end_date=None):
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
            pm = row.pm or 0
            cm = row.cm or 0
            ratio = pm / cm if cm > 0 else float(pm)
            return {
                "preventive_count": pm,
                "corrective_count": cm,
                "ratio": round(ratio, 2),
                "total": pm + cm,
            }

    def get_schedule_compliance(self, start_date=None, end_date=None):
        with self._session() as session:
            query = session.query(
                func.count(WorkOrder.id).label("total"),
                func.sum(case((WorkOrder.end_time <= WorkOrder.scheduled_date, 1), else_=0)).label("on_time"),
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
            row = query.one()
            total = row.total or 0
            on_time = row.on_time or 0
            compliance = (on_time / total * 100) if total > 0 else 0
            return {
                "total_tasks": total,
                "on_time": on_time,
                "late": total - on_time,
                "compliance_rate": round(compliance, 2),
            }

    # ==================== COST ANALYSIS ====================
    def get_cost_analysis(self, start_date=None, end_date=None):
        with self._session() as session:
            # Spare part costs via reference field (stores work order ID as string)
            part_cost_query = session.query(
                WorkOrder.type,
                func.sum(SparePartTransaction.quantity * SparePart.unit_price).label("part_cost")
            ).join(
                SparePartTransaction,
                SparePartTransaction.reference == func.cast(WorkOrder.id, String)
            ).join(
                SparePart, SparePart.id == SparePartTransaction.part_id
            ).filter(
                WorkOrder.status == WorkOrderStatus.COMPLETED,
                SparePartTransaction.transaction_type == 'OUT'
            )
            if start_date:
                part_cost_query = part_cost_query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                part_cost_query = part_cost_query.filter(WorkOrder.created_at <= end_date)
            part_cost_by_type = {row.type.name: row.part_cost or 0 for row in part_cost_query.group_by(WorkOrder.type).all()}

            # Labor cost: estimated from repair hours * 50 per hour
            labor_query = session.query(
                WorkOrder.type,
                func.sum(func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)) * 24 * 50
            ).filter(
                WorkOrder.status == WorkOrderStatus.COMPLETED,
                WorkOrder.start_time.isnot(None),
                WorkOrder.end_time.isnot(None),
            )
            if start_date:
                labor_query = labor_query.filter(WorkOrder.created_at >= start_date)
            if end_date:
                labor_query = labor_query.filter(WorkOrder.created_at <= end_date)
            labor_by_type = {row.type.name: row[1] or 0 for row in labor_query.group_by(WorkOrder.type).all()}

            all_types = set(part_cost_by_type.keys()) | set(labor_by_type.keys())
            breakdown = []
            total_cost = 0
            for t in all_types:
                cost = part_cost_by_type.get(t, 0) + labor_by_type.get(t, 0)
                breakdown.append({
                    "type": t,
                    "total_cost": round(cost, 2),
                    "part_cost": round(part_cost_by_type.get(t, 0), 2),
                    "labor_cost": round(labor_by_type.get(t, 0), 2),
                })
                total_cost += cost
            for b in breakdown:
                b["percentage"] = round((b["total_cost"] / total_cost * 100), 2) if total_cost > 0 else 0
            return {"breakdown": breakdown, "total_cost": round(total_cost, 2)}

    # ==================== RISK & TECHNICIAN PERFORMANCE ====================
    def get_equipment_risk_score(self):
        with self._session() as session:
            cutoff = datetime.now() - timedelta(days=30)
            rows = session.query(
                Equipment.id,
                Equipment.name,
                Equipment.criticality_level,
                func.sum(case((
                    and_(WorkOrder.type == WorkOrderType.CORRECTIVE, WorkOrder.created_at >= cutoff), 1), else_=0)).label("recent_failures"),
                func.avg(case((
                    and_(WorkOrder.start_time.isnot(None), WorkOrder.end_time.isnot(None)),
                    func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
                ), else_=None)).label("avg_downtime_days"),
            ).outerjoin(WorkOrder, WorkOrder.equipment_id == Equipment.id
            ).group_by(Equipment.id, Equipment.name, Equipment.criticality_level).all()

            criticality_factor = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            results = []
            for eq_id, eq_name, crit, failures, avg_down in rows:
                failures = failures or 0
                avg_hours = (avg_down or 0) * 24
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

    def get_technician_performance(self, start_date=None, end_date=None):
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
                    "technician_id": user_id,
                    "technician_name": name,
                    "total_tasks": total,
                    "completed_tasks": completed,
                    "completion_rate": round(completion_rate, 2),
                    "avg_completion_hours": round(avg_hours or 0, 2),
                })
            return results

    # ==================== TRENDS ====================
    def get_monthly_trends(self, months=6):
        with self._session() as session:
            start_date = datetime.now() - timedelta(days=months * 30)
            rows = session.query(
                extract("year", WorkOrder.end_time).label("year"),
                extract("month", WorkOrder.end_time).label("month"),
                WorkOrder.type,
                func.count(WorkOrder.id).label("count"),
            ).filter(
                WorkOrder.end_time >= start_date,
                WorkOrder.status == WorkOrderStatus.COMPLETED,
            ).group_by("year", "month", WorkOrder.type
            ).order_by("year", "month").all()
            return [
                {
                    "year": int(year),
                    "month": int(month),
                    "type": wo_type.name,
                    "count": count,
                }
                for year, month, wo_type, count in rows
            ]

    # ==================== DAIRY‑SPECIFIC KPIs ====================
    def get_inspection_effectiveness(self, start_date=None, end_date=None):
        with self._session() as session:
            query = session.query(
                func.count(InspectionResult.id).label("total"),
                func.sum(case((InspectionResult.result == "pass", 1), else_=0)).label("passed"),
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

    def get_cleaning_score(self, start_date=None, end_date=None):
        with self._session() as session:
            query = session.query(
                func.count(InspectionResult.id).label("total"),
                func.sum(case((InspectionResult.result == "pass", 1), else_=0)).label("passed"),
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

    def get_spare_parts_turnover(self):
        with self._session() as session:
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

    # ==================== PRIVATE HELPERS ====================
    def _get_downtime_internal(self, session, equipment_id, start_date, end_date):
        query = session.query(
            func.sum(func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)) * 24
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
        return query.scalar() or 0

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
            func.sum(case((InspectionResult.result == "pass", 1), else_=0)).label("passed"),
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
        return (passed / total) * 1
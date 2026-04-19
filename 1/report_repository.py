# database/report_repository.py
from sqlalchemy import func, extract, and_, case
from datetime import datetime, timedelta
from database.db import SessionLocal
from database.work_order import WorkOrder, WorkOrderStatus, WorkOrderType
from database.equipment_repository import Equipment


class ReportRepository:
    def __init__(self, session=None):
        self.session = session if session else SessionLocal()
        self._owns_session = session is None

    def __del__(self):
        if self._owns_session:
            self.session.close()

    # NEW: Overall KPI Summary for Dashboard
    def get_kpi_summary(self):
        """Get overall KPI summary for main dashboard"""
        total_work_orders = self.session.query(func.count(WorkOrder.id)).scalar() or 0

        completed_work_orders = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.status == WorkOrderStatus.COMPLETED
        ).scalar() or 0

        pending_work_orders = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.status == WorkOrderStatus.PENDING
        ).scalar() or 0

        in_progress_work_orders = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.status == WorkOrderStatus.IN_PROGRESS
        ).scalar() or 0

        total_equipment = self.session.query(func.count(Equipment.id)).scalar() or 0

        operational_equipment = self.session.query(func.count(Equipment.id)).filter(
            Equipment.status == 'operational'
        ).scalar() or 0

        avg_completion_time = self.session.query(
            func.avg(
                func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
            ) * 24
        ).filter(
            WorkOrder.status == WorkOrderStatus.COMPLETED,
            WorkOrder.end_time.isnot(None),
            WorkOrder.start_time.isnot(None)
        ).scalar() or 0

        pm_work_orders = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM])
        ).scalar() or 0

        cm_work_orders = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.type == WorkOrderType.CORRECTIVE
        ).scalar() or 0

        pm_compliance = (pm_work_orders / total_work_orders * 100) if total_work_orders > 0 else 0

        overdue_work_orders = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.status.in_([WorkOrderStatus.PENDING, WorkOrderStatus.IN_PROGRESS]),
            WorkOrder.scheduled_date < datetime.now()
        ).scalar() or 0

        return {
            'total_work_orders': total_work_orders,
            'completed_work_orders': completed_work_orders,
            'pending_work_orders': pending_work_orders,
            'in_progress_work_orders': in_progress_work_orders,
            'total_equipment': total_equipment,
            'operational_equipment': operational_equipment,
            'avg_completion_time_hours': round(avg_completion_time, 2),
            'pm_compliance_rate': round(pm_compliance, 2),
            'overdue_work_orders': overdue_work_orders,
            'cm_work_orders': cm_work_orders
        }

    # NEW: Per-Equipment Detailed Report
    def get_equipment_report(self, equipment_id: int):
        """Get detailed report for specific equipment"""
        equipment = self.session.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not equipment:
            return None

        total_work_orders = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.equipment_id == equipment_id
        ).scalar() or 0

        completed_work_orders = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.equipment_id == equipment_id,
            WorkOrder.status == WorkOrderStatus.COMPLETED
        ).scalar() or 0

        pm_work_orders = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.equipment_id == equipment_id,
            WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM])
        ).scalar() or 0

        cm_work_orders = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.equipment_id == equipment_id,
            WorkOrder.type == WorkOrderType.CORRECTIVE
        ).scalar() or 0

        avg_repair_time = self.session.query(
            func.avg(
                func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
            ) * 24
        ).filter(
            WorkOrder.equipment_id == equipment_id,
            WorkOrder.status == WorkOrderStatus.COMPLETED,
            WorkOrder.end_time.isnot(None),
            WorkOrder.start_time.isnot(None)
        ).scalar() or 0

        total_downtime = self.session.query(
            func.sum(
                func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
            ) * 24
        ).filter(
            WorkOrder.equipment_id == equipment_id,
            WorkOrder.status == WorkOrderStatus.COMPLETED,
            WorkOrder.type == WorkOrderType.CORRECTIVE,
            WorkOrder.end_time.isnot(None),
            WorkOrder.start_time.isnot(None)
        ).scalar() or 0

        pm_compliance = (pm_work_orders / total_work_orders * 100) if total_work_orders > 0 else 0

        failure_count = cm_work_orders

        if failure_count > 1:
            first_failure = self.session.query(WorkOrder.start_time).filter(
                WorkOrder.equipment_id == equipment_id,
                WorkOrder.type == WorkOrderType.CORRECTIVE,
                WorkOrder.start_time.isnot(None)
            ).order_by(WorkOrder.start_time.asc()).first()

            last_failure = self.session.query(WorkOrder.start_time).filter(
                WorkOrder.equipment_id == equipment_id,
                WorkOrder.type == WorkOrderType.CORRECTIVE,
                WorkOrder.start_time.isnot(None)
            ).order_by(WorkOrder.start_time.desc()).first()

            if first_failure and last_failure and first_failure[0] != last_failure[0]:
                time_span = (last_failure[0] - first_failure[0]).total_seconds() / 3600
                mtbf = time_span / (failure_count - 1)
            else:
                mtbf = 0
        else:
            mtbf = 0

        mttr = avg_repair_time

        return {
            'equipment_id': equipment_id,
            'equipment_name': equipment.name,
            'equipment_status': equipment.status,
            'total_work_orders': total_work_orders,
            'completed_work_orders': completed_work_orders,
            'pm_work_orders': pm_work_orders,
            'cm_work_orders': cm_work_orders,
            'avg_repair_time_hours': round(avg_repair_time, 2),
            'total_downtime_hours': round(total_downtime, 2),
            'pm_compliance_rate': round(pm_compliance, 2),
            'mtbf_hours': round(mtbf, 2),
            'mttr_hours': round(mttr, 2),
            'failure_count': failure_count
        }

    # KPI 1: Overall Equipment Effectiveness (OEE)
    def get_oee_metrics(self, equipment_id=None, start_date=None, end_date=None):
        """Calculate OEE: Availability × Performance × Quality"""
        query = self.session.query(Equipment)
        if equipment_id:
            query = query.filter(Equipment.id == equipment_id)

        results = []
        for eq in query.all():
            total_hours = 720
            downtime = self._get_downtime(eq.id, start_date, end_date)
            availability = ((total_hours - downtime) / total_hours) * 100

            performance = 95
            quality = 98

            oee = (availability * performance * quality) / 10000

            results.append({
                'equipment_id': eq.id,
                'equipment_name': eq.name,
                'availability': round(availability, 2),
                'performance': round(performance, 2),
                'quality': round(quality, 2),
                'oee': round(oee, 2)
            })

        return results

    # KPI 2: Mean Time Between Failures (MTBF)
    def get_mtbf(self, equipment_id=None, start_date=None, end_date=None):
        """MTBF = Total Operating Time / Number of Failures"""
        query = self.session.query(
            Equipment.id,
            Equipment.name,
            func.count(WorkOrder.id).label('failure_count')
        ).outerjoin(WorkOrder).filter(
            WorkOrder.type == WorkOrderType.CORRECTIVE,
            WorkOrder.status == WorkOrderStatus.COMPLETED
        )

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
                'equipment_id': eq_id,
                'equipment_name': eq_name,
                'mtbf_hours': round(mtbf, 2),
                'failure_count': failures
            })

        return results

    # KPI 3: Mean Time To Repair (MTTR)
    def get_mttr(self, equipment_id=None, start_date=None, end_date=None):
        """MTTR = Total Repair Time / Number of Repairs"""
        query = self.session.query(
            Equipment.id,
            Equipment.name,
            func.avg(
                func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
            ).label('avg_repair_time'),
            func.count(WorkOrder.id).label('repair_count')
        ).join(WorkOrder).filter(
            WorkOrder.type == WorkOrderType.CORRECTIVE,
            WorkOrder.status == WorkOrderStatus.COMPLETED,
            WorkOrder.start_time.isnot(None),
            WorkOrder.end_time.isnot(None)
        )

        if equipment_id:
            query = query.filter(Equipment.id == equipment_id)
        if start_date:
            query = query.filter(WorkOrder.created_at >= start_date)
        if end_date:
            query = query.filter(WorkOrder.created_at <= end_date)

        query = query.group_by(Equipment.id, Equipment.name)

        results = []
        for eq_id, eq_name, avg_time, count in query.all():
            mttr_hours = (avg_time * 24) if avg_time else 0
            results.append({
                'equipment_id': eq_id,
                'equipment_name': eq_name,
                'mttr_hours': round(mttr_hours, 2),
                'repair_count': count
            })

        return results

    # KPI 4: Preventive vs Corrective Maintenance Ratio
    def get_pm_cm_ratio(self, start_date=None, end_date=None):
        """PM/CM Ratio - Higher is better"""
        query = self.session.query(
            WorkOrder.type,
            func.count(WorkOrder.id).label('count')
        ).filter(WorkOrder.status == WorkOrderStatus.COMPLETED)

        if start_date:
            query = query.filter(WorkOrder.created_at >= start_date)
        if end_date:
            query = query.filter(WorkOrder.created_at <= end_date)

        query = query.group_by(WorkOrder.type)

        counts = {wt.name: 0 for wt in WorkOrderType}
        for wo_type, count in query.all():
            counts[wo_type.name] = count

        pm_count = counts.get('PREVENTIVE', 0) + counts.get('PM', 0)
        cm_count = counts.get('CORRECTIVE', 0)
        ratio = pm_count / cm_count if cm_count > 0 else pm_count

        return {
            'preventive_count': pm_count,
            'corrective_count': cm_count,
            'ratio': round(ratio, 2),
            'total': pm_count + cm_count
        }

    # KPI 5: Maintenance Cost Analysis
    def get_cost_analysis(self, start_date=None, end_date=None):
        """Total maintenance costs breakdown"""
        query = self.session.query(
            WorkOrder.type,
            func.count(WorkOrder.id).label('count')
        ).filter(WorkOrder.status == WorkOrderStatus.COMPLETED)

        if start_date:
            query = query.filter(WorkOrder.created_at >= start_date)
        if end_date:
            query = query.filter(WorkOrder.created_at <= end_date)

        query = query.group_by(WorkOrder.type)

        results = []
        total_cost = 0
        for wo_type, count in query.all():
            estimated_cost = count * 500
            total_cost += estimated_cost
            results.append({
                'type': wo_type.name,
                'total_cost': round(estimated_cost, 2),
                'count': count,
                'avg_cost': 500.0
            })

        for r in results:
            r['percentage'] = round((r['total_cost'] / total_cost * 100), 2) if total_cost > 0 else 0

        return {
            'breakdown': results,
            'total_cost': round(total_cost, 2)
        }

    # KPI 6: Schedule Compliance
    def get_schedule_compliance(self, start_date=None, end_date=None):
        """Percentage of PM tasks completed on time"""
        query = self.session.query(
            func.count(WorkOrder.id).label('total'),
            func.sum(
                case(
                    (WorkOrder.end_time <= WorkOrder.scheduled_date, 1),
                    else_=0
                )
            ).label('on_time')
        ).filter(
            WorkOrder.type.in_([WorkOrderType.PREVENTIVE, WorkOrderType.PM]),
            WorkOrder.status == WorkOrderStatus.COMPLETED,
            WorkOrder.scheduled_date.isnot(None),
            WorkOrder.end_time.isnot(None)
        )

        if start_date:
            query = query.filter(WorkOrder.created_at >= start_date)
        if end_date:
            query = query.filter(WorkOrder.created_at <= end_date)

        total, on_time = query.first()
        total = total or 0
        on_time = on_time or 0
        compliance = (on_time / total * 100) if total > 0 else 0

        return {
            'total_tasks': total,
            'on_time': on_time,
            'late': total - on_time,
            'compliance_rate': round(compliance, 2)
        }

    # KPI 7: Equipment Criticality & Risk Score
    def get_equipment_risk_score(self):
        """Risk = Failure Frequency × Downtime Impact × Cost Impact"""
        results = []
        equipments = self.session.query(Equipment).all()

        for eq in equipments:
            failures = self.session.query(func.count(WorkOrder.id)).filter(
                WorkOrder.equipment_id == eq.id,
                WorkOrder.type == WorkOrderType.CORRECTIVE,
                WorkOrder.created_at >= datetime.now() - timedelta(days=30)
            ).scalar() or 0

            avg_downtime = self.session.query(
                func.avg(
                    func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
                )
            ).filter(
                WorkOrder.equipment_id == eq.id,
                WorkOrder.start_time.isnot(None),
                WorkOrder.end_time.isnot(None)
            ).scalar() or 0

            risk_score = min(100, (failures * 10) + (avg_downtime * 24 * 5))

            results.append({
                'equipment_id': eq.id,
                'equipment_name': eq.name,
                'failure_count': failures,
                'avg_downtime_hours': round(avg_downtime * 24, 2),
                'avg_cost': 0.0,
                'risk_score': round(risk_score, 2),
                'risk_level': 'HIGH' if risk_score > 70 else 'MEDIUM' if risk_score > 40 else 'LOW'
            })

        return sorted(results, key=lambda x: x['risk_score'], reverse=True)

    # KPI 8: Technician Performance
    def get_technician_performance(self, start_date=None, end_date=None):
        """Analyze technician workload and efficiency"""
        from database.models import User

        query = self.session.query(
            User.id,
            User.full_name,
            func.count(WorkOrder.id).label('total_tasks'),
            func.sum(
                case(
                    (WorkOrder.status == WorkOrderStatus.COMPLETED, 1),
                    else_=0
                )
            ).label('completed_tasks'),
            func.avg(
                func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
            ).label('avg_completion_time')
        ).join(WorkOrder, User.id == WorkOrder.technician_id)

        if start_date:
            query = query.filter(WorkOrder.created_at >= start_date)
        if end_date:
            query = query.filter(WorkOrder.created_at <= end_date)

        query = query.group_by(User.id, User.full_name)

        results = []
        for user_id, name, total, completed, avg_time in query.all():
            completion_rate = (completed / total * 100) if total > 0 else 0
            avg_hours = (avg_time * 24) if avg_time else 0

            results.append({
                'technician_id': user_id,
                'technician_name': name,
                'total_tasks': total,
                'completed_tasks': completed,
                'completion_rate': round(completion_rate, 2),
                'avg_completion_hours': round(avg_hours, 2)
            })

        return results

    # KPI 9: Work Order Backlog
    def get_backlog_analysis(self):
        """Analyze pending and overdue work orders"""
        now = datetime.now()

        pending = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.status == WorkOrderStatus.PENDING
        ).scalar() or 0

        in_progress = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.status == WorkOrderStatus.IN_PROGRESS
        ).scalar() or 0

        overdue = self.session.query(func.count(WorkOrder.id)).filter(
            WorkOrder.status.in_([WorkOrderStatus.PENDING, WorkOrderStatus.IN_PROGRESS]),
            WorkOrder.scheduled_date < now
        ).scalar() or 0

        return {
            'pending': pending,
            'in_progress': in_progress,
            'overdue': overdue,
            'total_backlog': pending + in_progress
        }

    # KPI 10: Monthly Trend Analysis
    def get_monthly_trends(self, months=6):
        """Analyze maintenance trends over time"""
        start_date = datetime.now() - timedelta(days=months * 30)

        query = self.session.query(
            extract('year', WorkOrder.created_at).label('year'),
            extract('month', WorkOrder.created_at).label('month'),
            WorkOrder.type,
            func.count(WorkOrder.id).label('count')
        ).filter(
            WorkOrder.created_at >= start_date,
            WorkOrder.status == WorkOrderStatus.COMPLETED
        ).group_by('year', 'month', WorkOrder.type).order_by('year', 'month')

        results = []
        for year, month, wo_type, count in query.all():
            results.append({
                'year': int(year),
                'month': int(month),
                'type': wo_type.name,
                'count': count,
                'total_cost': 0.0
            })

        return results

    # Helper method
    def _get_downtime(self, equipment_id, start_date, end_date):
        """Calculate total downtime hours for equipment"""
        query = self.session.query(
            func.sum(
                func.julianday(WorkOrder.end_time) - func.julianday(WorkOrder.start_time)
            )
        ).filter(
            WorkOrder.equipment_id == equipment_id,
            WorkOrder.type == WorkOrderType.CORRECTIVE,
            WorkOrder.start_time.isnot(None),
            WorkOrder.end_time.isnot(None)
        )

        if start_date:
            query = query.filter(WorkOrder.created_at >= start_date)
        if end_date:
            query = query.filter(WorkOrder.created_at <= end_date)

        downtime_days = query.scalar() or 0
        return downtime_days * 24

"""
PM Service - Business logic for Preventive Maintenance
"""
from datetime import datetime, timedelta
from database.pm_repository import PMRepository
from database.work_order_repository import WorkOrderRepository


# How many days ahead to look for upcoming PMs
AUTO_GENERATE_DAYS_AHEAD = 7


class PMService:
    def __init__(self):
        self.pm_repo = PMRepository()
        self.wo_repo = WorkOrderRepository()

    def generate_due_work_orders(self) -> tuple[int, int, list[str]]:
        """
        Generate work orders for overdue and upcoming PM schedules.
        Returns: (created_count, skipped_count, error_messages)
        """
        created = 0
        skipped = 0
        errors  = []

        overdue  = self.pm_repo.get_overdue()
        upcoming = self.pm_repo.get_upcoming(days=AUTO_GENERATE_DAYS_AHEAD)

        # Deduplicate (a PM can appear in both lists if it's overdue and upcoming)
        seen_ids = set()
        all_due  = []
        for pm in overdue + upcoming:
            if pm["id"] not in seen_ids:
                seen_ids.add(pm["id"])
                all_due.append(pm)

        for pm in all_due:
            if not pm.get("is_active"):
                continue

            # next_due comes from _to_dict as a string "YYYY-MM-DD"
            # convert it back to datetime for the DB query and WO creation
            next_due_raw = pm.get("next_due_dt")  # use the raw datetime field
            if next_due_raw is None:
                # fallback: parse from the string field
                next_due_str = pm.get("next_due", "")
                if not next_due_str:
                    errors.append(f"PM #{pm['id']} ({pm['title']}): تاریخ سررسید موجود نیست")
                    continue
                try:
                    next_due_raw = datetime.strptime(next_due_str, "%Y-%m-%d")
                except ValueError:
                    errors.append(f"PM #{pm['id']} ({pm['title']}): فرمت تاریخ نامعتبر")
                    continue

            # Skip if a work order already exists for this PM + date
            existing = self.wo_repo.find_by_schedule_and_date(
                pm["id"],
                next_due_raw,
            )
            if existing:
                skipped += 1
                continue

            # create_work_order returns (bool, str) — unpack correctly
            ok, msg = self.wo_repo.create_work_order(
                title=f"PM: {pm['title']}",
                equipment_id=pm["equipment_id"],
                type_str="PREVENTIVE",
                priority="MEDIUM",
                technician_id=pm.get("technician_id"),
                scheduled_date=next_due_raw,
                description=f"برنامه نگهداری پیشگیرانه — دوره: {pm['frequency']}",
                parts_used=None,
                schedule_id=pm["id"],
            )

            if ok:
                created += 1
            else:
                errors.append(f"PM #{pm['id']} ({pm['title']}): {msg}")

        return created, skipped, errors
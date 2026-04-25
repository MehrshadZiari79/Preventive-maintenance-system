# services/pm_service.py
"""
PM Service - Business logic for Preventive Maintenance
"""
from datetime import datetime
from database.pm_repository import PMRepository
from database.work_order_repository import WorkOrderRepository


class PMService:
    def __init__(self):
        self.pm_repo = PMRepository()
        self.wo_repo = WorkOrderRepository()

    def generate_due_work_orders(self) -> tuple[int, int, list[str]]:
        """
        Generate work orders for all due PM schedules.
        Returns: (created_count, skipped_count, error_messages)
        """
        created = 0
        skipped = 0
        errors = []

        # Get all active schedules where next_due <= now
        due_schedules = self.pm_repo.get_due_schedules(datetime.now())

        for pm in due_schedules:
            # Check if a work order already exists for this PM and due date
            existing = self.wo_repo.find_by_schedule_and_date(pm.id, pm.next_due)
            if existing:
                skipped += 1
                continue

            # Create work order using the new dedicated method
            success, msg = self.wo_repo.create_from_pm(pm, pm.next_due)
            if success:
                created += 1
                # Update PM schedule: set last_done = due_date, calculate next_due
                self.pm_repo.update_next_due_date(pm.id, pm.next_due)
            else:
                errors.append(f"PM #{pm.id} ({pm.title}): {msg}")

        return created, skipped, errors
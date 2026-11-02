# services/pm_service.py
from database.pm_repository import PMRepository
from database.work_order_repository import WorkOrderRepository
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


class PMService:
    def __init__(self, session_factory):
        self.pm_repo = PMRepository(session_factory)
        self.wo_repo = WorkOrderRepository(session_factory)

    def generate_due_work_orders(self, days_ahead: int = 1) -> tuple[int, int, list[str]]:
        """
        Create work orders for all active PMs with next_due <= now + days_ahead.
        Returns (created, skipped, errors).
        """
        created = 0
        skipped = 0
        errors = []

        due_schedules = self.pm_repo.get_due_schedules_ahead(tehran_now(), days_ahead)

        for pm in due_schedules:
            existing = self.wo_repo.find_by_schedule_and_date(pm.id, pm.next_due)
            if existing:
                skipped += 1
                continue

            success, msg = self.wo_repo.create_from_pm(pm, pm.next_due)
            if success:
                created += 1
                # Do NOT advance next_due here!
                # The PM's next due date will be updated only when
                # the manager approves the completed work order.
            else:
                errors.append(f"PM #{pm.id} ({pm.title}): {msg}")

        return created, skipped, errors
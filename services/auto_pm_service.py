# services/auto_pm_service.py
import threading
import time
from datetime import datetime
from database.pm_repository import PMRepository
from database.work_order_repository import WorkOrderRepository


class AutoPMService:
    def __init__(self, check_interval_seconds: int = 3600):
        self.interval = check_interval_seconds
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("Auto PM Service started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("Auto PM Service stopped.")

    def _run(self):
        while self.running:
            try:
                self._check_and_generate()
            except Exception as e:
                print(f"Auto PM Service error: {e}")
            time.sleep(self.interval)

    def _check_and_generate(self):
        """Check all active PM schedules and create work orders for those that are due."""
        pm_repo = PMRepository()
        wo_repo = WorkOrderRepository()   # <-- no argument!

        due_schedules = pm_repo.get_due_schedules(datetime.now())
        for pm in due_schedules:
            # Check if a work order already exists for this PM and due date
            existing = wo_repo.find_by_schedule_and_date(pm.id, pm.next_due)
            if existing:
                continue
            success, msg = wo_repo.create_from_pm(pm, pm.next_due)
            if success:
                pm_repo.update_next_due_date(pm.id, pm.next_due)
            else:
                print(f"Auto PM: Failed to create WO for PM {pm.id}: {msg}")
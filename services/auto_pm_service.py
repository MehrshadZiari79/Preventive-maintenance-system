# services/auto_pm_service.py
import threading
import time
import uuid
from datetime import datetime
from database.db import SessionLocal
from database.pm_repository import PMRepository
from database.work_order_repository import WorkOrderRepository
from database.models import Settings


class AutoPMService:
    def __init__(self, check_interval_seconds: int = 3600):
        self.interval = check_interval_seconds
        self.running = False
        self.thread = None
        self.lock_key = "pm_generation_lock"
        self.last_run_key = "last_pm_generation"

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

    def _init_settings(self):
        """Ensure the settings table has the required rows."""
        db = SessionLocal()
        try:
            if not db.query(Settings).filter(Settings.key == self.lock_key).first():
                db.add(Settings(key=self.lock_key, value=""))
            if not db.query(Settings).filter(Settings.key == self.last_run_key).first():
                db.add(Settings(key=self.last_run_key, value=str(datetime.min)))
            db.commit()
        finally:
            db.close()

    def _check_and_generate(self):
        self._init_settings()

        lock_id = str(uuid.uuid4())
        lock_acquired = False
        db = SessionLocal()
        try:
            # Try to acquire lock with a timeout (only if lock is older than 60 sec)
            lock_record = db.query(Settings).filter(Settings.key == self.lock_key).with_for_update().first()
            current_lock = lock_record.value
            if current_lock:
                try:
                    lock_time = datetime.fromisoformat(current_lock.split('|')[1])  # lock_id|timestamp
                except:
                    lock_time = datetime.min
                if (datetime.now() - lock_time).total_seconds() < 60:
                    return  # lock still held by another client
            # Acquire lock
            lock_record.value = f"{lock_id}|{datetime.now().isoformat()}"
            db.commit()
            lock_acquired = True

            # Check if last generation was within 1 hour
            last_run_record = db.query(Settings).filter(Settings.key == self.last_run_key).first()
            last_run = datetime.fromisoformat(last_run_record.value) if last_run_record.value else datetime.min
            if (datetime.now() - last_run).total_seconds() < 3600:
                return

            # Perform generation (no need for new session – reuse db)
            pm_repo = PMRepository()
            wo_repo = WorkOrderRepository()
            due_schedules = pm_repo.get_due_schedules(datetime.now())
            for pm in due_schedules:
                existing = wo_repo.find_by_schedule_and_date(pm.id, pm.next_due)
                if existing:
                    continue
                success, msg = wo_repo.create_from_pm(pm, pm.next_due)
                if success:
                    pm_repo.update_next_due_date(pm.id, pm.next_due)
                else:
                    print(f"Auto PM: Failed to create WO for PM {pm.id}: {msg}")

            # Update last run timestamp
            last_run_record.value = datetime.now().isoformat()
            db.commit()

        except Exception as e:
            db.rollback()
            print(f"Auto PM service critical error: {e}")
        finally:
            if lock_acquired:
                # Release lock
                try:
                    db.query(Settings).filter(Settings.key == self.lock_key).update({Settings.value: ""})
                    db.commit()
                except:
                    pass
            db.close()
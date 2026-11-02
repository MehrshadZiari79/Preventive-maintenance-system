# database/equipment_repository.py
from sqlalchemy import func
from database.models import (
    Equipment, EquipmentStatus, PMSchedule,
    Inspection, InspectionTemplate, ProductionLog,
)
from database.work_order import WorkOrder
from utils.logger import log_action
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


class EquipmentRepository:
    def __init__(self, session_factory):
        self.Session = session_factory

    # ── GET methods ─────────────────────────────────────────────────
    def get_all_equipment(self) -> list[dict]:
        session = self.Session()
        try:
            equipment = session.query(Equipment).order_by(Equipment.code).all()
            return [self._to_dict(eq) for eq in equipment]
        finally:
            session.close()

    def get_equipment_by_id(self, equipment_id: int) -> dict:
        session = self.Session()
        try:
            eq = session.query(Equipment).filter(Equipment.id == equipment_id).first()
            return self._to_dict(eq) if eq else None
        finally:
            session.close()

    def get_equipment_by_code(self, code: str) -> dict:
        session = self.Session()
        try:
            eq = session.query(Equipment).filter(Equipment.code == code).first()
            return self._to_dict(eq) if eq else None
        finally:
            session.close()

    def search_equipment(self, keyword: str) -> list[dict]:
        session = self.Session()
        try:
            q = session.query(Equipment).filter(
                Equipment.name.contains(keyword) |
                Equipment.code.contains(keyword) |
                Equipment.category.contains(keyword) |
                Equipment.location.contains(keyword)
            ).order_by(Equipment.code).all()
            return [self._to_dict(eq) for eq in q]
        finally:
            session.close()

    def get_stats(self) -> dict:
        session = self.Session()
        try:
            total = session.query(func.count(Equipment.id)).scalar() or 0
            operational = session.query(func.count(Equipment.id)).filter(
                Equipment.status == EquipmentStatus.OPERATIONAL.value).scalar() or 0
            maintenance = session.query(func.count(Equipment.id)).filter(
                Equipment.status == EquipmentStatus.MAINTENANCE.value).scalar() or 0
            breakdown = session.query(func.count(Equipment.id)).filter(
                Equipment.status == EquipmentStatus.BREAKDOWN.value).scalar() or 0
            inactive = session.query(func.count(Equipment.id)).filter(
                Equipment.status == EquipmentStatus.INACTIVE.value).scalar() or 0
            return {
                "total": total,
                "operational": operational,
                "maintenance": maintenance,
                "breakdown": breakdown,
                "inactive": inactive,
            }
        finally:
            session.close()

    # ── CRUD methods ────────────────────────────────────────────────
    def create_equipment(self, code, name, category, manufacturer, model,
                         serial_number, location, installation_date, status,
                         specifications, notes,
                         length=None, width=None, diameter=None,
                         height=None, volume=None, weight=None):
        session = self.Session()
        try:
            eq = Equipment(
                code=code, name=name, category=category,
                manufacturer=manufacturer, model=model,
                serial_number=serial_number, location=location,
                installation_date=installation_date, status=status,
                specifications=specifications, notes=notes,
                length=length, width=width, diameter=diameter,
                height=height, volume=volume, weight=weight,
            )
            session.add(eq)
            session.commit()
            log_action("CREATE", "equipment", eq.id, f"کد: {code}, نام: {name}")
            return True, "تجهیز با موفقیت ثبت شد."
        except Exception as e:
            session.rollback()
            return False, f"خطا: {str(e)}"
        finally:
            session.close()

    def update_equipment(self, equipment_id, code, name, category, manufacturer,
                         model, serial_number, location, installation_date,
                         status, specifications, notes,
                         length=None, width=None, diameter=None,
                         height=None, volume=None, weight=None):
        session = self.Session()
        try:
            eq = session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if not eq:
                return False, "تجهیز یافت نشد."
            eq.code = code
            eq.name = name
            eq.category = category
            eq.manufacturer = manufacturer
            eq.model = model
            eq.serial_number = serial_number
            eq.location = location
            eq.installation_date = installation_date
            eq.status = status
            eq.specifications = specifications
            eq.notes = notes
            eq.length = length
            eq.width = width
            eq.diameter = diameter
            eq.height = height
            eq.volume = volume
            eq.weight = weight
            eq.updated_at = tehran_now()
            session.commit()
            log_action("UPDATE", "equipment", equipment_id, f"کد: {code}")
            return True, "تجهیز بروزرسانی شد."
        except Exception as e:
            session.rollback()
            return False, f"خطا: {str(e)}"
        finally:
            session.close()

    def get_history_counts(self, equipment_id) -> dict:
        """Work history recorded for this equipment."""
        session = self.Session()
        try:
            counts = {
                "work_orders": session.query(func.count(WorkOrder.id)).filter(
                    WorkOrder.equipment_id == equipment_id).scalar() or 0,
                "inspections": session.query(func.count(Inspection.id)).filter(
                    Inspection.equipment_id == equipment_id).scalar() or 0,
                "production_logs": session.query(func.count(ProductionLog.id)).filter(
                    ProductionLog.equipment_id == equipment_id).scalar() or 0,
                "shift_logs": 0,
            }
            try:
                from database.machine_shift_repository import MachineShiftRepository
                if MachineShiftRepository(self.Session).shift_tables_available():
                    from database.machine_shift import MachineShiftLog
                    counts["shift_logs"] = session.query(func.count(MachineShiftLog.id)).filter(
                        MachineShiftLog.equipment_id == equipment_id).scalar() or 0
            except ImportError:
                pass
            return counts
        finally:
            session.close()

    def delete_equipment(self, equipment_id):
        """
        Delete equipment only when it has no work history.

        Equipment with work orders, inspections or machine-hour records is
        kept so that reports (MTBF, MTTR, costs, OEE) stay correct; set its
        status to «غیرفعال» instead.  Configuration that belongs only to the
        equipment (PM schedules) is removed with it, and inspection templates
        are detached.
        """
        try:
            counts = self.get_history_counts(equipment_id)
        except Exception as e:
            return False, f"خطای پایگاه داده: {str(e)}"
        labels = {
            "work_orders": "دستور کار",
            "inspections": "بازرسی",
            "production_logs": "ثبت ساعت کار",
            "shift_logs": "برگه شیفت",
        }
        used = [f"{n} {labels[k]}" for k, n in counts.items() if n]
        if used:
            return False, (
                "این تجهیز سابقه دارد ("
                + "، ".join(used)
                + ") و برای درست ماندن گزارش‌ها قابل حذف نیست.\n"
                "به‌جای حذف، وضعیت آن را «غیرفعال» کنید."
            )

        session = self.Session()
        try:
            equipment = session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if not equipment:
                return False, "تجهیز یافت نشد."
            code, name = equipment.code, equipment.name

            session.query(PMSchedule).filter(
                PMSchedule.equipment_id == equipment_id
            ).delete(synchronize_session=False)
            session.query(InspectionTemplate).filter(
                InspectionTemplate.equipment_id == equipment_id
            ).update({InspectionTemplate.equipment_id: None}, synchronize_session=False)

            session.delete(equipment)
            session.commit()

            log_action("DELETE", "equipment", equipment_id, f"کد: {code}, نام: {name}")
            return True, "تجهیز حذف شد."
        except Exception as e:
            session.rollback()
            return False, f"خطای پایگاه داده: {str(e)}"
        finally:
            session.close()

    # ── Other helpers ───────────────────────────────────────────────
    def update_status(self, equipment_id, new_status):
        session = self.Session()
        try:
            eq = session.query(Equipment).filter(Equipment.id == equipment_id).first()
            if not eq:
                return False, "تجهیز یافت نشد."
            eq.status = new_status
            eq.updated_at = tehran_now()
            session.commit()
            log_action("STATUS", "equipment", equipment_id, new_status)
            return True, "وضعیت با موفقیت تغییر کرد."
        except Exception as e:
            session.rollback()
            return False, f"خطا: {str(e)}"
        finally:
            session.close()

    def get_categories(self) -> list[str]:
        session = self.Session()
        try:
            rows = session.query(Equipment.category).distinct().all()
            return [row[0] for row in rows if row[0]]
        finally:
            session.close()

    def is_category_used(self, category):
        session = self.Session()
        try:
            count = session.query(Equipment).filter(Equipment.category == category).count()
            return count > 0
        finally:
            session.close()

    def delete_category(self, category):
        session = self.Session()
        try:
            if self.is_category_used(category):
                return False, f"دسته‌بندی '{category}' در حال استفاده است."
            session.query(Equipment).filter(Equipment.category == category).delete()
            session.commit()
            return True, f"دسته‌بندی '{category}' حذف شد."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def rename_category(self, old_name: str, new_name: str) -> tuple[bool, str]:
        """Rename a category in all equipment rows that use it."""
        session = self.Session()
        try:
            if old_name == new_name:
                return True, "نام تغییری نکرد."
            session.query(Equipment).filter(Equipment.category == old_name).update(
                {Equipment.category: new_name}, synchronize_session=False)
            session.commit()
            log_action("RENAME_CATEGORY", "equipment", 0, f"{old_name} → {new_name}")
            return True, f"دسته‌بندی '{old_name}' به '{new_name}' تغییر یافت."
        except Exception as e:
            session.rollback()
            return False, f"خطا: {str(e)}"
        finally:
            session.close()

    # ── Location management ─────────────────────────────────────────
    def get_locations(self) -> list[str]:
        session = self.Session()
        try:
            rows = session.query(Equipment.location).distinct().all()
            return [row[0] for row in rows if row[0]]
        finally:
            session.close()

    def is_location_used(self, location: str) -> bool:
        session = self.Session()
        try:
            count = session.query(Equipment).filter(Equipment.location == location).count()
            return count > 0
        finally:
            session.close()

    def delete_location(self, location: str) -> tuple[bool, str]:
        session = self.Session()
        try:
            if self.is_location_used(location):
                return False, f"موقعیت '{location}' در حال استفاده است."
            return True, f"موقعیت '{location}' حذف شد."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def rename_location(self, old_name: str, new_name: str) -> tuple[bool, str]:
        """Rename a location in all equipment rows that use it."""
        session = self.Session()
        try:
            if old_name == new_name:
                return True, "نام تغییری نکرد."
            session.query(Equipment).filter(Equipment.location == old_name).update(
                {Equipment.location: new_name}, synchronize_session=False)
            session.commit()
            log_action("RENAME_LOCATION", "equipment", 0, f"{old_name} → {new_name}")
            return True, f"موقعیت '{old_name}' به '{new_name}' تغییر یافت."
        except Exception as e:
            session.rollback()
            return False, f"خطا: {str(e)}"
        finally:
            session.close()

    @staticmethod
    def _to_dict(eq: Equipment):
        return {
            "id": eq.id,
            "code": eq.code,
            "name": eq.name,
            "category": eq.category,
            "manufacturer": eq.manufacturer or "",
            "model": eq.model or "",
            "serial_number": eq.serial_number or "",
            "location": eq.location or "",
            "installation_date": eq.installation_date.strftime("%Y-%m-%d") if eq.installation_date else "",
            "status": eq.status,
            "specifications": eq.specifications or "",
            "notes": eq.notes or "",
            "criticality_level": eq.criticality_level or "",
            "length": eq.length,
            "width": eq.width,
            "diameter": eq.diameter,
            "height": eq.height,
            "volume": eq.volume,
            "weight": eq.weight,
            "created_at": eq.created_at.strftime("%Y-%m-%d %H:%M:%S") if eq.created_at else "",
            "updated_at": eq.updated_at.strftime("%Y-%m-%d %H:%M:%S") if eq.updated_at else "",
        }
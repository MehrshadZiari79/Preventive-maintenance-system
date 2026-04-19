"""
Equipment Repository - Data Access Layer for Equipment Management
"""
from typing import Optional
from datetime import datetime
from sqlalchemy import func, case
from database.db import SessionLocal
from database.models import Equipment


class EquipmentRepository:
    def __init__(self):
        pass

    def _session(self):
        return SessionLocal()

    # ─────────────────────────── READ ───────────────────────────

    def get_all_equipment(self) -> list[dict]:
        with self._session() as session:
            equipment = session.query(Equipment).order_by(Equipment.code).all()
            return [self._to_dict(e) for e in equipment]

    def get_equipment_by_id(self, equipment_id: int) -> Optional[dict]:
        with self._session() as session:
            e = session.query(Equipment).filter(Equipment.id == equipment_id).first()
            return self._to_dict(e) if e else None

    def get_equipment_by_code(self, code: str) -> Optional[dict]:
        with self._session() as session:
            e = session.query(Equipment).filter(Equipment.code == code).first()
            return self._to_dict(e) if e else None

    def search_equipment(self, keyword: str) -> list[dict]:
        with self._session() as session:
            pattern = f"%{keyword}%"
            equipment = session.query(Equipment).filter(
                (Equipment.code.like(pattern)) |
                (Equipment.name.like(pattern)) |
                (Equipment.location.like(pattern))
            ).order_by(Equipment.code).all()
            return [self._to_dict(e) for e in equipment]

    def filter_by_category(self, category: str) -> list[dict]:
        with self._session() as session:
            equipment = session.query(Equipment).filter(
                Equipment.category == category
            ).order_by(Equipment.code).all()
            return [self._to_dict(e) for e in equipment]

    def filter_by_status(self, status: str) -> list[dict]:
        with self._session() as session:
            equipment = session.query(Equipment).filter(
                Equipment.status == status
            ).order_by(Equipment.code).all()
            return [self._to_dict(e) for e in equipment]

    def code_exists(self, code: str, exclude_id: Optional[int] = None) -> bool:
        with self._session() as session:
            q = session.query(Equipment).filter(Equipment.code == code)
            if exclude_id:
                q = q.filter(Equipment.id != exclude_id)
            return q.first() is not None

    def get_categories(self) -> list[str]:
        with self._session() as session:
            result = session.query(Equipment.category).distinct().all()
            return sorted([r[0] for r in result if r[0]])

    def get_stats(self) -> dict:
        """
        Fixed: was 4 separate COUNT queries.
        Now: 1 query using conditional aggregation.
        """
        with self._session() as session:
            row = session.query(
                func.count(Equipment.id).label("total"),
                func.sum(case((Equipment.status == "operational", 1), else_=0)).label("operational"),
                func.sum(case((Equipment.status == "maintenance", 1), else_=0)).label("maintenance"),
                func.sum(case((Equipment.status == "breakdown",  1), else_=0)).label("breakdown"),
                func.sum(case((Equipment.status == "inactive",   1), else_=0)).label("inactive"),
            ).one()

            return {
                "total":       row.total       or 0,
                "operational": row.operational or 0,
                "maintenance": row.maintenance or 0,
                "breakdown":   row.breakdown   or 0,
                "inactive":    row.inactive    or 0,
            }

    # ─────────────────────────── WRITE ──────────────────────────

    def create_equipment(self, code: str, name: str, category: str,
                         manufacturer: str, model: str, serial_number: str,
                         location: str, installation_date: Optional[datetime],
                         status: str, specifications: str, notes: str) -> tuple[bool, str]:
        if self.code_exists(code):
            return False, "این کد تجهیز قبلاً ثبت شده است."
        try:
            with self._session() as session:
                equipment = Equipment(
                    code=code,
                    name=name,
                    category=category,
                    manufacturer=manufacturer or None,
                    model=model or None,
                    serial_number=serial_number or None,
                    location=location,
                    installation_date=installation_date,
                    status=status,
                    specifications=specifications or None,
                    notes=notes or None
                )
                session.add(equipment)
                session.commit()
            return True, "تجهیز با موفقیت ثبت شد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    def update_equipment(self, equipment_id: int, code: str, name: str,
                         category: str, manufacturer: str, model: str,
                         serial_number: str, location: str,
                         installation_date: Optional[datetime], status: str,
                         specifications: str, notes: str) -> tuple[bool, str]:
        if self.code_exists(code, exclude_id=equipment_id):
            return False, "این کد تجهیز قبلاً ثبت شده است."
        try:
            with self._session() as session:
                equipment = session.query(Equipment).filter(
                    Equipment.id == equipment_id
                ).first()
                if not equipment:
                    return False, "تجهیز یافت نشد."

                equipment.code             = code
                equipment.name             = name
                equipment.category         = category
                equipment.manufacturer     = manufacturer or None
                equipment.model            = model or None
                equipment.serial_number    = serial_number or None
                equipment.location         = location
                equipment.installation_date = installation_date
                equipment.status           = status
                equipment.specifications   = specifications or None
                equipment.notes            = notes or None
                equipment.updated_at       = datetime.utcnow()

                session.commit()
            return True, "اطلاعات تجهیز بروزرسانی شد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    def update_status(self, equipment_id: int, new_status: str) -> tuple[bool, str]:
        try:
            with self._session() as session:
                equipment = session.query(Equipment).filter(
                    Equipment.id == equipment_id
                ).first()
                if not equipment:
                    return False, "تجهیز یافت نشد."
                equipment.status     = new_status
                equipment.updated_at = datetime.utcnow()
                session.commit()
            return True, "وضعیت تجهیز تغییر کرد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    def delete_equipment(self, equipment_id: int) -> tuple[bool, str]:
        try:
            with self._session() as session:
                equipment = session.query(Equipment).filter(
                    Equipment.id == equipment_id
                ).first()
                if not equipment:
                    return False, "تجهیز یافت نشد."
                session.delete(equipment)
                session.commit()
            return True, "تجهیز حذف شد."
        except Exception as e:
            return False, f"خطای پایگاه داده: {e}"

    # ─────────────────────────── HELPER ─────────────────────────

    @staticmethod
    def _to_dict(e: Equipment) -> dict:
        return {
            "id":                e.id,
            "code":              e.code,
            "name":              e.name,
            "category":          e.category,
            "manufacturer":      e.manufacturer or "",
            "model":             e.model or "",
            "serial_number":     e.serial_number or "",
            "location":          e.location,
            "installation_date": e.installation_date.strftime("%Y-%m-%d") if e.installation_date else "",
            "status":            e.status,
            "specifications":    e.specifications or "",
            "notes":             e.notes or "",
            "created_at":        e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
            "updated_at":        e.updated_at.strftime("%Y-%m-%d %H:%M") if e.updated_at else "",
        }
# database/spare_parts_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List, Optional, Dict, Any
from database.db import SessionLocal
from database.models import SparePart, SparePartTransaction


class SparePartsRepository:
    def __init__(self, session=None):
        self._external_session = session

    def _session(self):
        if self._external_session:
            return self._external_session
        return SessionLocal()

    # ==================== Part CRUD ====================
    def get_all(self) -> List[SparePart]:
        with self._session() as session:
            return session.query(SparePart).order_by(SparePart.part_number).all()

    def get_by_id(self, part_id: int) -> Optional[SparePart]:
        with self._session() as session:
            return session.query(SparePart).filter(SparePart.id == part_id).first()

    def get_by_part_number(self, part_number: str) -> Optional[SparePart]:
        with self._session() as session:
            return session.query(SparePart).filter(SparePart.part_number == part_number).first()

    def create(self, data: Dict[str, Any]) -> SparePart:
        with self._session() as session:
            part = SparePart(
                part_number=data['part_number'],
                name=data['name'],
                description=data.get('description', ''),
                category=data.get('category', ''),
                unit=data.get('unit', ''),
                min_stock=int(data.get('min_stock', 0)),
                current_stock=int(data.get('current_stock', 0)),
                unit_price=float(data.get('unit_price', 0.0)),
                location=data.get('location', ''),
                supplier=data.get('supplier', ''),
                equipment_codes=data.get('equipment_codes', ''),
                notes=data.get('notes', '')
            )
            session.add(part)
            session.commit()
            session.refresh(part)
            return part

    def update(self, part_id: int, data: Dict[str, Any]) -> Optional[SparePart]:
        with self._session() as session:
            part = session.query(SparePart).filter(SparePart.id == part_id).first()
            if not part:
                return None
            for key, value in data.items():
                if hasattr(part, key) and value is not None:
                    if key in ('min_stock', 'current_stock'):
                        value = int(value) if value else 0
                    elif key == 'unit_price':
                        value = float(value) if value else 0.0
                    setattr(part, key, value)
            part.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(part)
            return part

    def delete(self, part_id: int) -> bool:
        with self._session() as session:
            part = session.query(SparePart).filter(SparePart.id == part_id).first()
            if not part:
                return False
            session.delete(part)
            session.commit()
            return True

    def search(self, keyword: str) -> List[SparePart]:
        pattern = f"%{keyword}%"
        with self._session() as session:
            return session.query(SparePart).filter(
                (SparePart.part_number.like(pattern)) |
                (SparePart.name.like(pattern)) |
                (SparePart.category.like(pattern)) |
                (SparePart.supplier.like(pattern))
            ).order_by(SparePart.part_number).all()

    def get_low_stock(self) -> List[SparePart]:
        with self._session() as session:
            return session.query(SparePart).filter(
                SparePart.current_stock <= SparePart.min_stock
            ).order_by(SparePart.current_stock).all()

    def get_stats(self) -> Dict[str, Any]:
        with self._session() as session:
            total_parts = session.query(func.count(SparePart.id)).scalar() or 0
            low_stock_count = session.query(SparePart).filter(
                SparePart.current_stock <= SparePart.min_stock
            ).count()
            total_inventory_value = session.query(
                func.sum(SparePart.unit_price * SparePart.current_stock)
            ).scalar() or 0.0
            return {
                'total_parts': total_parts,
                'low_stock_count': low_stock_count,
                'total_inventory_value': total_inventory_value
            }

    # ==================== Transaction Methods ====================
    def add_transaction(self, data: Dict[str, Any]) -> SparePartTransaction:
        with self._session() as session:
            part = session.query(SparePart).filter(SparePart.id == data['part_id']).first()
            if not part:
                raise ValueError("Part not found")
            qty = int(data['quantity'])
            trans_type = data['transaction_type']
            if trans_type == 'IN':
                part.current_stock += qty
            elif trans_type == 'OUT':
                if part.current_stock < qty:
                    raise ValueError(f"Insufficient stock. Available: {part.current_stock}")
                part.current_stock -= qty
            else:
                raise ValueError("Invalid transaction type")
            transaction = SparePartTransaction(
                part_id=part.id,
                transaction_type=trans_type,
                quantity=qty,
                reference=data.get('reference', ''),
                notes=data.get('notes', '')
            )
            session.add(transaction)
            session.commit()
            session.refresh(transaction)
            return transaction

    def get_transactions_for_part(self, part_id: int) -> List[SparePartTransaction]:
        with self._session() as session:
            return session.query(SparePartTransaction).filter(
                SparePartTransaction.part_id == part_id
            ).order_by(SparePartTransaction.created_at.desc()).all()

    def get_all_transactions(self, limit: int = 100) -> List[SparePartTransaction]:
        with self._session() as session:
            return session.query(SparePartTransaction).order_by(
                SparePartTransaction.created_at.desc()
            ).limit(limit).all()
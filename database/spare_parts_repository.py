# database/spare_parts_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime
from typing import List, Optional, Dict, Any
from database.models import SparePart, SparePartTransaction


class SparePartsRepository:
    def __init__(self, session: Session):
        self.session = session

    # ==================== Part CRUD ====================
    def get_all(self) -> List[SparePart]:
        """Get all spare parts"""
        return self.session.query(SparePart).order_by(SparePart.part_number).all()

    def get_by_id(self, part_id: int) -> Optional[SparePart]:
        """Get part by ID"""
        return self.session.query(SparePart).filter(SparePart.id == part_id).first()

    def get_by_part_number(self, part_number: str) -> Optional[SparePart]:
        """Get part by part number"""
        return self.session.query(SparePart).filter(SparePart.part_number == part_number).first()

    def create(self, data: Dict[str, Any]) -> SparePart:
        """Create new spare part"""
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
        self.session.add(part)
        self.session.commit()
        self.session.refresh(part)
        return part

    def update(self, part_id: int, data: Dict[str, Any]) -> Optional[SparePart]:
        """Update spare part"""
        part = self.get_by_id(part_id)
        if not part:
            return None

        for key, value in data.items():
            if hasattr(part, key) and value is not None:
                # Handle numeric conversions
                if key in ('min_stock', 'current_stock'):
                    value = int(value) if value else 0
                elif key == 'unit_price':
                    value = float(value) if value else 0.0
                setattr(part, key, value)

        part.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(part)
        return part

    def delete(self, part_id: int) -> bool:
        """Delete spare part (cascade deletes transactions)"""
        part = self.get_by_id(part_id)
        if not part:
            return False
        self.session.delete(part)
        self.session.commit()
        return True

    def search(self, keyword: str) -> List[SparePart]:
        """Search parts by part number, name, category, or supplier"""
        pattern = f"%{keyword}%"
        return self.session.query(SparePart).filter(
            (SparePart.part_number.like(pattern)) |
            (SparePart.name.like(pattern)) |
            (SparePart.category.like(pattern)) |
            (SparePart.supplier.like(pattern))
        ).order_by(SparePart.part_number).all()

    def get_low_stock(self) -> List[SparePart]:
        """Get parts where current stock <= min stock"""
        return self.session.query(SparePart).filter(
            SparePart.current_stock <= SparePart.min_stock
        ).order_by(SparePart.current_stock).all()

    def get_stats(self) -> Dict[str, Any]:
        """Get inventory statistics"""
        total_parts = self.session.query(func.count(SparePart.id)).scalar() or 0
        low_stock_count = self.session.query(SparePart).filter(
            SparePart.current_stock <= SparePart.min_stock
        ).count()
        total_inventory_value = self.session.query(
            func.sum(SparePart.unit_price * SparePart.current_stock)
        ).scalar() or 0.0

        return {
            'total_parts': total_parts,
            'low_stock_count': low_stock_count,
            'total_inventory_value': total_inventory_value
        }

    # ==================== Transaction Methods ====================
    def add_transaction(self, data: Dict[str, Any]) -> SparePartTransaction:
        """Add stock transaction and update part stock"""
        part = self.get_by_id(data['part_id'])
        if not part:
            raise ValueError("Part not found")

        qty = int(data['quantity'])
        trans_type = data['transaction_type']  # 'IN' or 'OUT'

        # Update part stock
        if trans_type == 'IN':
            part.current_stock += qty
        elif trans_type == 'OUT':
            if part.current_stock < qty:
                raise ValueError(f"Insufficient stock. Available: {part.current_stock}")
            part.current_stock -= qty
        else:
            raise ValueError("Invalid transaction type")

        # Create transaction record
        transaction = SparePartTransaction(
            part_id=part.id,
            transaction_type=trans_type,
            quantity=qty,
            reference=data.get('reference', ''),
            notes=data.get('notes', '')
        )
        self.session.add(transaction)
        self.session.commit()
        self.session.refresh(transaction)
        return transaction

    def get_transactions_for_part(self, part_id: int) -> List[SparePartTransaction]:
        """Get all transactions for a specific part, ordered by date descending"""
        return self.session.query(SparePartTransaction).filter(
            SparePartTransaction.part_id == part_id
        ).order_by(SparePartTransaction.created_at.desc()).all()

    def get_all_transactions(self, limit: int = 100) -> List[SparePartTransaction]:
        """Get recent transactions across all parts"""
        return self.session.query(SparePartTransaction).order_by(
            SparePartTransaction.created_at.desc()
        ).limit(limit).all()
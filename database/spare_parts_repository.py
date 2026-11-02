# database/spare_parts_repository.py
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from database.models import SparePart, SparePartTransaction
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


class SparePartsRepository:
    def __init__(self, session_factory):
        self.Session = session_factory

    def get_all(self) -> List[SparePart]:
        session = self.Session()
        try:
            return session.query(SparePart).order_by(SparePart.part_number).all()
        finally:
            session.close()

    def get_by_id(self, part_id: int) -> Optional[SparePart]:
        session = self.Session()
        try:
            return session.query(SparePart).filter(SparePart.id == part_id).first()
        finally:
            session.close()

    def get_by_part_number(self, part_number: str) -> Optional[SparePart]:
        session = self.Session()
        try:
            return session.query(SparePart).filter(SparePart.part_number == part_number).first()
        finally:
            session.close()

    def create(self, data: Dict[str, Any]) -> SparePart:
        session = self.Session()
        try:
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
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def update(self, part_id: int, data: Dict[str, Any]) -> Optional[SparePart]:
        session = self.Session()
        try:
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
            part.updated_at = tehran_now()
            session.commit()
            session.refresh(part)
            return part
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def delete(self, part_id: int) -> bool:
        session = self.Session()
        try:
            part = session.query(SparePart).filter(SparePart.id == part_id).first()
            if not part:
                return False
            session.delete(part)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

    def search(self, keyword: str) -> List[SparePart]:
        session = self.Session()
        try:
            pattern = f"%{keyword}%"
            return session.query(SparePart).filter(
                (SparePart.part_number.like(pattern)) |
                (SparePart.name.like(pattern)) |
                (SparePart.category.like(pattern)) |
                (SparePart.supplier.like(pattern))
            ).order_by(SparePart.part_number).all()
        finally:
            session.close()

    def get_low_stock(self) -> List[SparePart]:
        session = self.Session()
        try:
            return session.query(SparePart).filter(
                SparePart.current_stock <= SparePart.min_stock
            ).order_by(SparePart.current_stock).all()
        finally:
            session.close()

    def get_stats(self) -> Dict[str, Any]:
        session = self.Session()
        try:
            total_parts = session.query(func.count(SparePart.id)).scalar() or 0
            low_stock_count = session.query(SparePart).filter(
                SparePart.current_stock <= SparePart.min_stock
            ).count()
            total_value = 0.0
            # Weighted average purchase price per part:
            #   sum(quantity * batch_price) / sum(quantity) over IN transactions
            avg_prices = {}
            rows = session.query(
                SparePartTransaction.part_id,
                func.sum(SparePartTransaction.quantity * SparePartTransaction.batch_price),
                func.sum(SparePartTransaction.quantity),
            ).filter(
                SparePartTransaction.transaction_type == 'IN',
                SparePartTransaction.batch_price.isnot(None),
            ).group_by(SparePartTransaction.part_id).all()
            for part_id, total_cost, total_qty in rows:
                if total_qty:
                    avg_prices[part_id] = float(total_cost or 0) / float(total_qty)
            for part_id, stock in session.query(SparePart.id, SparePart.current_stock).all():
                avg_price = avg_prices.get(part_id)
                if avg_price is not None:
                    total_value += (stock or 0) * float(avg_price)
            return {
                'total_parts': total_parts,
                'low_stock_count': low_stock_count,
                'total_inventory_value': total_value
            }
        finally:
            session.close()

    def add_transaction(self, data: Dict[str, Any]) -> SparePartTransaction:
        session = self.Session()
        try:
            part = session.query(SparePart).filter(SparePart.id == data['part_id']).first()
            if not part:
                raise ValueError("Part not found")
            qty = int(data['quantity'])
            trans_type = data['transaction_type']
            batch_price = data.get('batch_price', None)
            reference = data.get('reference', '')
            notes = data.get('notes', '')

            if trans_type == 'IN':
                # Use provided batch_price or current unit_price
                price = float(batch_price) if batch_price is not None else part.unit_price
                part.current_stock += qty
                # Update part's current unit_price to the latest purchase price (optional)
                if batch_price is not None:
                    part.unit_price = price
            elif trans_type == 'OUT':
                if part.current_stock < qty:
                    raise ValueError(f"Insufficient stock. Available: {part.current_stock}")
                part.current_stock -= qty
                price = None  # OUT transactions do not have a batch price
            else:
                raise ValueError("Invalid transaction type")

            transaction = SparePartTransaction(
                part_id=part.id,
                transaction_type=trans_type,
                quantity=qty,
                batch_price=price if trans_type == 'IN' else None,
                reference=reference,
                notes=notes
            )
            session.add(transaction)
            session.commit()
            session.refresh(transaction)
            return transaction
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_transactions_for_part(self, part_id: int) -> List[SparePartTransaction]:
        session = self.Session()
        try:
            return session.query(SparePartTransaction).filter(
                SparePartTransaction.part_id == part_id
            ).order_by(SparePartTransaction.created_at.desc()).all()
        finally:
            session.close()

    def get_all_transactions(self, limit: int = 100) -> List[SparePartTransaction]:
        session = self.Session()
        try:
            return session.query(SparePartTransaction).order_by(
                SparePartTransaction.created_at.desc()
            ).limit(limit).all()
        finally:
            session.close()

    def get_price_history(self, part_id: int) -> List[dict]:
        session = self.Session()
        try:
            trans = session.query(SparePartTransaction).filter(
                SparePartTransaction.part_id == part_id,
                SparePartTransaction.transaction_type == 'IN'
            ).order_by(SparePartTransaction.created_at.desc()).all()
            return [{'date': t.created_at, 'price': t.batch_price, 'quantity': t.quantity, 'reference': t.reference} for t in trans]
        finally:
            session.close()
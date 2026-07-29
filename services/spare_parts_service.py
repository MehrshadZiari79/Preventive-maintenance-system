# services/spare_parts_service.py
from typing import List, Optional, Dict, Any
from database.spare_parts_repository import SparePartsRepository
from database.models import SparePart, SparePartTransaction


class SparePartsService:
    def __init__(self, session_factory):
        self.repo = SparePartsRepository(session_factory)

    def get_all_parts(self) -> List[SparePart]:
        return self.repo.get_all()

    def get_part_by_id(self, part_id: int) -> Optional[SparePart]:
        return self.repo.get_by_id(part_id)

    def get_part_by_part_number(self, part_number: str) -> Optional[SparePart]:
        return self.repo.get_by_part_number(part_number)

    def create_part(self, data: Dict[str, Any]) -> SparePart:
        if not data.get('part_number') or not data.get('name'):
            raise ValueError("Part number and name are required")
        if self.repo.get_by_part_number(data['part_number']):
            raise ValueError(f"Part number {data['part_number']} already exists")
        return self.repo.create(data)

    def update_part(self, part_id: int, data: Dict[str, Any]) -> SparePart:
        if 'part_number' in data and data['part_number']:
            existing = self.repo.get_by_part_number(data['part_number'])
            if existing and existing.id != part_id:
                raise ValueError(f"Part number {data['part_number']} already exists")
        part = self.repo.update(part_id, data)
        if not part:
            raise ValueError("Part not found")
        return part

    def delete_part(self, part_id: int) -> None:
        if not self.repo.delete(part_id):
            raise ValueError("Part not found")

    def search_parts(self, keyword: str) -> List[SparePart]:
        if not keyword.strip():
            return self.get_all_parts()
        return self.repo.search(keyword)

    def get_low_stock_parts(self) -> List[SparePart]:
        return self.repo.get_low_stock()

    def get_stats(self) -> Dict[str, Any]:
        return self.repo.get_stats()

    def add_stock_transaction(self, data: Dict[str, Any], work_order_id: Optional[int] = None, batch_price: Optional[float] = None) -> SparePartTransaction:
        if work_order_id:
            data['reference'] = f"WO-{work_order_id}"
        if batch_price is not None:
            data['batch_price'] = batch_price
        return self.repo.add_transaction(data)

    def get_part_transactions(self, part_id: int) -> List[SparePartTransaction]:
        return self.repo.get_transactions_for_part(part_id)

    def get_all_transactions(self, limit: int = 100) -> List[SparePartTransaction]:
        return self.repo.get_all_transactions(limit)

    def get_price_history(self, part_id: int) -> List[dict]:
        return self.repo.get_price_history(part_id)
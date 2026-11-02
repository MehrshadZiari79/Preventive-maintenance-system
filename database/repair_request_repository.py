# -*- coding: utf-8 -*-
"""
Repair Request Repository
=========================

Business workflow
-----------------
1) A repair request is created with an executing Department.
2) No Personnel is assigned at creation time.
3) When the repair is actually completed, one or more Personnel from that
   request's Department are selected and stored on RepairRequestCompletion.
4) The request and its completion record can later be edited as one logical
   record.

Legacy compatibility
--------------------
The existing repair_request_documents table contains an older
assigned_personnel_id column. It is intentionally NOT removed or rewritten.
The repository simply stops using it for the new workflow. Historical data is
preserved.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from database.models import (
    Department,
    Personnel,
    RepairRequestCompletion,
    RepairRequestDocument,
)
from utils.logger import log_action
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


class RepairRequestRepository:
    ENTITY_TYPE = "repair_request_document"

    def __init__(self, session_factory):
        self.Session = session_factory

    # ======================================================================
    # NORMALIZATION
    # ======================================================================

    @staticmethod
    def _clean_text(value: Any, preserve_newlines: bool = False) -> str:
        if value is None:
            return ""

        value = str(value)

        if preserve_newlines:
            value = value.replace("\r\n", "\n").replace("\r", "\n")
            return "\n".join(line.strip() for line in value.split("\n")).strip()

        return " ".join(value.split())

    @staticmethod
    def _normalize_ids(personnel_ids=None, personnel_id=None) -> list[int]:
        values = []
        if personnel_ids is not None:
            if isinstance(personnel_ids, (list, tuple, set)):
                values.extend(personnel_ids)
            else:
                values.append(personnel_ids)
        if personnel_id is not None:
            values.append(personnel_id)

        result = []
        seen = set()
        for value in values:
            try:
                pid = int(value)
            except (TypeError, ValueError):
                continue
            if pid <= 0 or pid in seen:
                continue
            seen.add(pid)
            result.append(pid)
        return result

    # ======================================================================
    # VALIDATION
    # ======================================================================

    @staticmethod
    def _validate(
        requesting_unit: str,
        equipment_name: str,
        breakdown_datetime: Any,
        requester_name: str,
        department_id: Any,
    ) -> Optional[str]:
        if not requesting_unit:
            return "لطفاً «واحد متقاضی» را وارد کنید."
        if len(requesting_unit) > 150:
            return "طول «واحد متقاضی» نباید بیشتر از ۱۵۰ کاراکتر باشد."

        if not equipment_name:
            return "لطفاً «نام دستگاه/وسیله» را وارد کنید."
        if len(equipment_name) > 200:
            return "طول «نام دستگاه/وسیله» نباید بیشتر از ۲۰۰ کاراکتر باشد."

        if not isinstance(breakdown_datetime, datetime):
            return "«ساعت و تاریخ اعلام خرابی» معتبر نیست."

        if not requester_name:
            return "لطفاً «نام درخواست‌دهنده» را وارد کنید."
        if len(requester_name) > 150:
            return "طول «نام درخواست‌دهنده» نباید بیشتر از ۱۵۰ کاراکتر باشد."

        try:
            did = int(department_id)
            if did <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return "انتخاب «دپارتمان انجام‌دهنده» الزامی است."

        return None

    @staticmethod
    def _normalize_department_id(value) -> Optional[int]:
        try:
            result = int(value)
        except (TypeError, ValueError):
            return None
        return result if result > 0 else None

    # ======================================================================
    # REFERENCE DATA
    # ======================================================================

    def get_departments(self) -> list[Department]:
        session = self.Session()
        try:
            records = (
                session.query(Department)
                .order_by(Department.name.asc())
                .all()
            )
            session.expunge_all()
            return records
        finally:
            session.close()

    def get_personnel_for_assignment(self):
        """Legacy compatibility helper; no longer used by creation UI."""
        session = self.Session()
        try:
            records = (
                session.query(Personnel)
                .options(joinedload(Personnel.department))
                .order_by(Personnel.full_name.asc(), Personnel.personnel_code.asc())
                .all()
            )
            session.expunge_all()
            return records
        finally:
            session.close()

    def get_personnel_for_department(self, department_id: int):
        department_id = self._normalize_department_id(department_id)
        if department_id is None:
            return []

        session = self.Session()
        try:
            records = (
                session.query(Personnel)
                .options(joinedload(Personnel.department))
                .filter(Personnel.department_id == department_id)
                .order_by(Personnel.full_name.asc(), Personnel.personnel_code.asc())
                .all()
            )
            session.expunge_all()
            return records
        finally:
            session.close()

    def get_personnel_for_finish(self, document_id: int):
        """Return only Personnel belonging to the request's Department."""
        session = self.Session()
        try:
            department_id = (
                session.query(RepairRequestDocument.department_id)
                .filter(RepairRequestDocument.id == document_id)
                .scalar()
            )
        finally:
            session.close()

        if department_id is None:
            return []

        return self.get_personnel_for_department(department_id)

    # ======================================================================
    # EAGER-LOAD HELPERS
    # ======================================================================

    @staticmethod
    def _query_options(query):
        return query.options(
            joinedload(RepairRequestDocument.department),
            joinedload(RepairRequestDocument.assigned_personnel)
            .joinedload(Personnel.department),
            joinedload(RepairRequestDocument.completion)
            .joinedload(RepairRequestCompletion.personnel)
            .joinedload(Personnel.department),
            joinedload(RepairRequestDocument.created_by),
        )

    @staticmethod
    def _completion_options(query):
        return query.options(
            joinedload(RepairRequestCompletion.personnel)
            .joinedload(Personnel.department)
        )

    # ======================================================================
    # CREATE
    # ======================================================================

    def create(
        self,
        requesting_unit: str,
        equipment_name: str,
        breakdown_datetime: datetime,
        assigned_personnel_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        requester_name: str = "",
        request_description: Optional[str] = None,
        created_by_user_id: Optional[int] = None,
        department_id: Optional[int] = None,
    ) -> tuple[bool, str, Optional[RepairRequestDocument]]:
        """
        Create a repair request.

        assigned_personnel_id is accepted only for backwards compatibility;
        it is deliberately ignored by the new workflow.
        """
        requesting_unit = self._clean_text(requesting_unit)
        equipment_name = self._clean_text(equipment_name)
        operator_name = self._clean_text(operator_name)
        requester_name = self._clean_text(requester_name)
        request_description = self._clean_text(request_description, preserve_newlines=True)

        department_id = self._normalize_department_id(department_id)
        error = self._validate(
            requesting_unit=requesting_unit,
            equipment_name=equipment_name,
            breakdown_datetime=breakdown_datetime,
            requester_name=requester_name,
            department_id=department_id,
        )
        if error:
            return False, error, None

        session = self.Session()
        try:
            department = (
                session.query(Department)
                .filter(Department.id == department_id)
                .first()
            )
            if not department:
                return False, "دپارتمان انتخاب‌شده در فهرست دپارتمان‌ها یافت نشد.", None

            document = RepairRequestDocument(
                requesting_unit=requesting_unit,
                equipment_name=equipment_name,
                breakdown_datetime=breakdown_datetime,
                operator_name=operator_name or None,
                requester_name=requester_name,
                request_description=request_description or None,
                department_id=department_id,
                # IMPORTANT: old field is intentionally left untouched/null.
                assigned_personnel_id=None,
                created_by_user_id=created_by_user_id,
                created_at=tehran_now(),
                updated_at=None,
            )
            session.add(document)
            session.commit()
            session.refresh(document)
            document_id = document.id
            session.expunge(document)

            try:
                log_action(
                    "CREATE",
                    self.ENTITY_TYPE,
                    document_id,
                    f"واحد: {requesting_unit}, تجهیز: {equipment_name}, دپارتمان: {department.name}",
                )
            except Exception:
                pass

            return True, "درخواست تعمیرات با موفقیت ثبت شد.", document

        except SQLAlchemyError as exc:
            session.rollback()
            return False, f"خطای پایگاه داده: {exc}", None
        except Exception as exc:
            session.rollback()
            return False, f"خطا در ثبت درخواست تعمیرات: {exc}", None
        finally:
            session.close()

    # ======================================================================
    # UPDATE
    # ======================================================================

    def update(
        self,
        document_id: int,
        requesting_unit: str,
        equipment_name: str,
        breakdown_datetime: datetime,
        assigned_personnel_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        requester_name: str = "",
        request_description: Optional[str] = None,
        department_id: Optional[int] = None,
    ) -> tuple[bool, str]:
        """Update request information only; completion history is preserved."""
        requesting_unit = self._clean_text(requesting_unit)
        equipment_name = self._clean_text(equipment_name)
        operator_name = self._clean_text(operator_name)
        requester_name = self._clean_text(requester_name)
        request_description = self._clean_text(request_description, preserve_newlines=True)
        department_id = self._normalize_department_id(department_id)

        error = self._validate(
            requesting_unit=requesting_unit,
            equipment_name=equipment_name,
            breakdown_datetime=breakdown_datetime,
            requester_name=requester_name,
            department_id=department_id,
        )
        if error:
            return False, error

        session = self.Session()
        try:
            document = (
                session.query(RepairRequestDocument)
                .options(
                    joinedload(RepairRequestDocument.completion)
                    .joinedload(RepairRequestCompletion.personnel),
                )
                .filter(RepairRequestDocument.id == document_id)
                .first()
            )
            if not document:
                return False, "رکورد درخواست تعمیرات پیدا نشد."

            department = (
                session.query(Department)
                .filter(Department.id == department_id)
                .first()
            )
            if not department:
                return False, "دپارتمان انتخاب‌شده در فهرست دپارتمان‌ها یافت نشد."

            document.requesting_unit = requesting_unit
            document.equipment_name = equipment_name
            document.breakdown_datetime = breakdown_datetime
            document.operator_name = operator_name or None
            document.requester_name = requester_name
            document.request_description = request_description or None
            document.department_id = department_id
            document.updated_at = tehran_now()

            # Legacy assigned_personnel_id is intentionally not used or changed.
            session.commit()

            try:
                log_action(
                    "UPDATE",
                    self.ENTITY_TYPE,
                    document_id,
                    f"ویرایش درخواست: {requester_name} / {equipment_name} / {department.name}",
                )
            except Exception:
                pass

            return True, "درخواست تعمیرات با موفقیت ویرایش شد."

        except SQLAlchemyError as exc:
            session.rollback()
            return False, f"خطای پایگاه داده: {exc}"
        except Exception as exc:
            session.rollback()
            return False, f"خطا در ویرایش درخواست تعمیرات: {exc}"
        finally:
            session.close()

    # ======================================================================
    # DELETE
    # ======================================================================

    def delete(self, document_id: int) -> tuple[bool, str]:
        session = self.Session()
        try:
            document = (
                self._query_options(session.query(RepairRequestDocument))
                .filter(RepairRequestDocument.id == document_id)
                .first()
            )
            if not document:
                return False, "رکورد درخواست تعمیرات پیدا نشد."

            completion = document.completion
            if completion is not None:
                completion.personnel = []

            session.delete(document)
            session.commit()

            try:
                log_action(
                    "DELETE",
                    self.ENTITY_TYPE,
                    document_id,
                    f"تجهیز: {document.equipment_name or ''}, درخواست‌دهنده: {document.requester_name or ''}",
                )
            except Exception:
                pass

            return True, "درخواست تعمیرات با موفقیت حذف شد."

        except SQLAlchemyError as exc:
            session.rollback()
            return False, f"خطای پایگاه داده: {exc}"
        except Exception as exc:
            session.rollback()
            return False, f"خطا در حذف درخواست تعمیرات: {exc}"
        finally:
            session.close()

    # ======================================================================
    # READ
    # ======================================================================

    def get_by_id(self, document_id: int) -> Optional[RepairRequestDocument]:
        session = self.Session()
        try:
            document = (
                self._query_options(session.query(RepairRequestDocument))
                .filter(RepairRequestDocument.id == document_id)
                .first()
            )
            if document:
                session.expunge(document)
            return document
        finally:
            session.close()

    def get_all(self) -> list[RepairRequestDocument]:
        session = self.Session()
        try:
            records = (
                self._query_options(session.query(RepairRequestDocument))
                .order_by(
                    RepairRequestDocument.created_at.desc(),
                    RepairRequestDocument.id.desc(),
                )
                .all()
            )
            session.expunge_all()
            return records
        finally:
            session.close()

    # ======================================================================
    # SEARCH / FILTER
    # ======================================================================

    @staticmethod
    def _record_search_text(record) -> str:
        values = [
            getattr(record, "id", ""),
            getattr(record, "requesting_unit", ""),
            getattr(record, "equipment_name", ""),
            getattr(record, "operator_name", ""),
            getattr(record, "requester_name", ""),
            getattr(record, "request_description", ""),
            getattr(getattr(record, "department", None), "name", ""),
            getattr(getattr(record, "assigned_personnel", None), "full_name", ""),
            getattr(getattr(record, "assigned_personnel", None), "personnel_code", ""),
        ]
        completion = getattr(record, "completion", None)
        if completion:
            values.extend([
                getattr(completion, "finish_notes", ""),
                getattr(completion, "cost_description", ""),
                getattr(completion, "delay_minutes", ""),
                getattr(completion, "delay_reason", ""),
                getattr(completion, "completion_datetime", ""),
            ])
            for person in (getattr(completion, "personnel", None) or []):
                values.extend([
                    getattr(person, "full_name", ""),
                    getattr(person, "personnel_code", ""),
                    getattr(getattr(person, "department", None), "name", ""),
                ])
        return " ".join(str(value or "") for value in values).casefold()

    def search(self, keyword: Optional[str] = None) -> list[RepairRequestDocument]:
        keyword = self._clean_text(keyword).casefold()
        records = self.get_all()
        if not keyword:
            return records
        parts = [part for part in keyword.split() if part]
        return [
            record
            for record in records
            if all(part in self._record_search_text(record) for part in parts)
        ]

    def get_by_date_range(
        self,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> list[RepairRequestDocument]:
        if not start_date and not end_date:
            return self.get_all()

        if start_date and end_date and start_date > end_date:
            start_date, end_date = end_date, start_date

        records = self.get_all()
        result = []
        for record in records:
            value = getattr(record, "breakdown_datetime", None)
            if not isinstance(value, datetime):
                continue
            record_date = value.date()
            if start_date and record_date < start_date:
                continue
            if end_date and record_date > end_date:
                continue
            result.append(record)
        return result

    def search_with_date_range(
        self,
        keyword: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[RepairRequestDocument]:
        records = self.get_by_date_range(start_date, end_date)
        keyword = self._clean_text(keyword).casefold()
        if not keyword:
            return records
        parts = [part for part in keyword.split() if part]
        return [
            record
            for record in records
            if all(part in self._record_search_text(record) for part in parts)
        ]

    # ======================================================================
    # FULL EDIT
    # ======================================================================

    def update_full(
        self,
        document_id: int,
        requesting_unit: str,
        equipment_name: str,
        breakdown_datetime: datetime,
        assigned_personnel_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        requester_name: str = "",
        request_description: Optional[str] = None,
        department_id: Optional[int] = None,
        completion: Optional[dict] = None,
    ) -> tuple[bool, str]:
        """
        Update the complete logical repair-request record.

        assigned_personnel_id is retained only for backwards compatibility;
        it is not used for the new workflow.

        completion=None:
            request fields only; an existing completion remains unchanged.

        completion=dict:
            completion fields and one-or-more completion personnel are replaced
            in the existing completion row, or a completion row is created.
        """
        requesting_unit = self._clean_text(requesting_unit)
        equipment_name = self._clean_text(equipment_name)
        operator_name = self._clean_text(operator_name)
        requester_name = self._clean_text(requester_name)
        request_description = self._clean_text(request_description, preserve_newlines=True)
        department_id = self._normalize_department_id(department_id)

        error = self._validate(
            requesting_unit=requesting_unit,
            equipment_name=equipment_name,
            breakdown_datetime=breakdown_datetime,
            requester_name=requester_name,
            department_id=department_id,
        )
        if error:
            return False, error

        session = self.Session()
        try:
            document = (
                self._query_options(session.query(RepairRequestDocument))
                .filter(RepairRequestDocument.id == document_id)
                .first()
            )
            if not document:
                return False, "رکورد درخواست تعمیرات پیدا نشد."

            department = (
                session.query(Department)
                .filter(Department.id == department_id)
                .first()
            )
            if not department:
                return False, "دپارتمان انتخاب‌شده در فهرست دپارتمان‌ها یافت نشد."

            document.requesting_unit = requesting_unit
            document.equipment_name = equipment_name
            document.breakdown_datetime = breakdown_datetime
            document.operator_name = operator_name or None
            document.requester_name = requester_name
            document.request_description = request_description or None
            document.department_id = department_id
            document.updated_at = tehran_now()

            if completion is not None:
                personnel_ids = self._normalize_ids(completion.get("personnel_ids"))
                if not personnel_ids:
                    return False, "برای اطلاعات اتمام، حداقل یک پرسنل انجام‌دهنده انتخاب کنید."

                completion_datetime = completion.get("completion_datetime")
                if not isinstance(completion_datetime, datetime):
                    return False, "تاریخ و ساعت اتمام نامعتبر است."

                try:
                    numeric_cost = float(completion.get("manual_cost") or 0)
                except (TypeError, ValueError):
                    return False, "هزینه اتمام نامعتبر است."
                if numeric_cost < 0:
                    return False, "هزینه اتمام نمی‌تواند منفی باشد."

                raw_delay = completion.get("delay_minutes")
                if raw_delay in (None, ""):
                    normalized_delay = None
                else:
                    try:
                        normalized_delay = int(raw_delay)
                    except (TypeError, ValueError):
                        return False, "مدت تأخیر نامعتبر است."
                    if normalized_delay < 0:
                        return False, "مدت تأخیر نمی‌تواند منفی باشد."

                personnel = (
                    session.query(Personnel)
                    .options(joinedload(Personnel.department))
                    .filter(Personnel.id.in_(personnel_ids))
                    .all()
                )
                personnel_by_id = {int(person.id): person for person in personnel}
                if len(personnel_by_id) != len(set(personnel_ids)):
                    return False, "یک یا چند پرسنل انجام‌دهنده در فهرست پرسنل یافت نشدند."

                wrong_department = [
                    pid
                    for pid in personnel_ids
                    if int(personnel_by_id[pid].department_id or 0) != int(department_id)
                ]
                if wrong_department:
                    return False, "تمام پرسنل انجام‌دهنده باید متعلق به دپارتمان انتخاب‌شده درخواست باشند."

                ordered_personnel = [personnel_by_id[pid] for pid in personnel_ids]

                completion_row = document.completion
                if completion_row is None:
                    completion_row = RepairRequestCompletion(
                        repair_request_id=document.id,
                        created_at=tehran_now(),
                    )
                    session.add(completion_row)

                completion_row.completion_datetime = completion_datetime
                completion_row.finish_notes = self._clean_text(
                    completion.get("finish_notes"), preserve_newlines=True
                ) or None
                completion_row.manual_cost = numeric_cost
                completion_row.cost_description = self._clean_text(
                    completion.get("cost_description"), preserve_newlines=True
                ) or None
                completion_row.delay_minutes = normalized_delay
                completion_row.delay_reason = self._clean_text(
                    completion.get("delay_reason"), preserve_newlines=True
                ) or None
                completion_row.personnel = ordered_personnel
                completion_row.completed_by_user_id = completion.get("completed_by_user_id") or completion_row.completed_by_user_id

            session.commit()

            try:
                log_action(
                    "UPDATE",
                    self.ENTITY_TYPE,
                    document_id,
                    f"ویرایش کامل درخواست تعمیرات: {requester_name} / {equipment_name}",
                )
            except Exception:
                pass

            return True, "اطلاعات درخواست تعمیرات با موفقیت ویرایش شد."

        except SQLAlchemyError as exc:
            session.rollback()
            return False, f"خطای پایگاه داده: {exc}"
        except Exception as exc:
            session.rollback()
            return False, f"خطا در ویرایش کامل درخواست تعمیرات: {exc}"
        finally:
            session.close()

    # ======================================================================
    # COMPLETION WORKFLOW
    # ======================================================================

    def request_finish(
        self,
        document_id: int,
        personnel_id=None,
        personnel_ids=None,
        completion_datetime: Optional[datetime] = None,
        finish_notes: Optional[str] = None,
        manual_cost=None,
        cost_description: Optional[str] = None,
        delay_minutes=None,
        delay_reason: Optional[str] = None,
        completed_by_user_id: Optional[int] = None,
    ) -> tuple[bool, str, Optional[RepairRequestCompletion]]:
        normalized_ids = self._normalize_ids(
            personnel_ids=personnel_ids,
            personnel_id=personnel_id,
        )
        if not normalized_ids:
            return False, "انتخاب حداقل یک پرسنل انجام‌دهنده الزامی است.", None

        completion_datetime = completion_datetime or tehran_now()
        if not isinstance(completion_datetime, datetime):
            return False, "تاریخ و ساعت اتمام نامعتبر است.", None

        try:
            numeric_cost = float(manual_cost or 0)
        except (TypeError, ValueError):
            return False, "هزینه واردشده نامعتبر است.", None
        if numeric_cost < 0:
            return False, "هزینه نمی‌تواند منفی باشد.", None

        if delay_minutes in (None, ""):
            normalized_delay = None
        else:
            try:
                normalized_delay = int(delay_minutes)
            except (TypeError, ValueError):
                return False, "مدت تأخیر نامعتبر است.", None
            if normalized_delay < 0:
                return False, "مدت تأخیر نمی‌تواند منفی باشد.", None

        session = self.Session()
        try:
            document = (
                self._query_options(session.query(RepairRequestDocument))
                .filter(RepairRequestDocument.id == document_id)
                .first()
            )
            if not document:
                return False, "رکورد درخواست تعمیرات پیدا نشد.", None

            if document.completion is not None:
                return False, "این درخواست تعمیرات قبلاً به عنوان انجام‌شده ثبت شده است.", None

            department_id = int(document.department_id or 0)
            if department_id <= 0:
                return False, "برای این درخواست هنوز دپارتمان انجام‌دهنده تعیین نشده است.", None

            personnel = (
                session.query(Personnel)
                .options(joinedload(Personnel.department))
                .filter(Personnel.id.in_(normalized_ids))
                .all()
            )
            personnel_by_id = {int(person.id): person for person in personnel}
            if len(personnel_by_id) != len(set(normalized_ids)):
                return False, "یک یا چند پرسنل انجام‌دهنده در فهرست پرسنل یافت نشدند.", None

            wrong_department = [
                pid
                for pid in normalized_ids
                if int(personnel_by_id[pid].department_id or 0) != department_id
            ]
            if wrong_department:
                return False, "تمام پرسنل انجام‌دهنده باید از همان دپارتمان درخواست باشند.", None

            ordered_personnel = [personnel_by_id[pid] for pid in normalized_ids]
            completion = RepairRequestCompletion(
                repair_request_id=document.id,
                completion_datetime=completion_datetime,
                finish_notes=self._clean_text(finish_notes, preserve_newlines=True) or None,
                manual_cost=numeric_cost,
                cost_description=self._clean_text(cost_description, preserve_newlines=True) or None,
                delay_minutes=normalized_delay,
                delay_reason=self._clean_text(delay_reason, preserve_newlines=True) or None,
                completed_by_user_id=completed_by_user_id,
                created_at=tehran_now(),
            )
            completion.personnel = ordered_personnel
            session.add(completion)
            session.commit()
            session.refresh(completion)
            session.expunge(completion)

            try:
                log_action(
                    "COMPLETE",
                    self.ENTITY_TYPE,
                    document.id,
                    f"پرسنل انجام‌دهنده: {[p.full_name for p in ordered_personnel]}",
                )
            except Exception:
                pass

            return True, "اتمام کار درخواست تعمیرات با موفقیت ثبت شد.", completion

        except SQLAlchemyError as exc:
            session.rollback()
            return False, f"خطای پایگاه داده: {exc}", None
        except Exception as exc:
            session.rollback()
            return False, f"خطا در ثبت اتمام کار: {exc}", None
        finally:
            session.close()

    def get_completion(self, document_id: int):
        session = self.Session()
        try:
            completion = (
                self._completion_options(session.query(RepairRequestCompletion))
                .filter(RepairRequestCompletion.repair_request_id == document_id)
                .first()
            )
            if completion:
                session.expunge(completion)
            return completion
        finally:
            session.close()

    # ======================================================================
    # COUNT / COMPATIBILITY
    # ======================================================================

    def count(self) -> int:
        session = self.Session()
        try:
            return session.query(RepairRequestDocument).count()
        finally:
            session.close()

    def get_all_documents(self):
        return self.get_all()

    def get_document_by_id(self, document_id):
        return self.get_by_id(document_id)

    def create_document(self, **kwargs):
        return self.create(**kwargs)

    def update_document(self, document_id, **kwargs):
        return self.update(document_id, **kwargs)

    def delete_document(self, document_id):
        return self.delete(document_id)

    def search_documents(self, keyword=None):
        return self.search(keyword)

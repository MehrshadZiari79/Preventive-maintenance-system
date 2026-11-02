# database/personnel_repository.py
"""
PM System - Personnel Repository
================================

Personnel are real maintenance workers.

Final fields:
    id
    personnel_code
    full_name
    department_id

Personnel are NOT application Users.

Workflow:
    PM / Work Order creation
        -> Department selected

    Work performed
        -> Personnel selected from that exact Department

This repository provides:
    - Personnel CRUD
    - Department assignment
    - Department-filtered Personnel lookup
    - Validation for finish/completion workflow
    - Safe deletion that preserves historical completion data

No database migration is performed here.
"""

from typing import Optional, List, Dict, Tuple

from sqlalchemy.orm import joinedload
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from database.models import (
    Personnel,
    Department,
    work_order_completers,
    repair_request_completers,
)

from utils.logger import log_action


class PersonnelRepository:

    # =========================================================================
    # INIT
    # =========================================================================

    def __init__(self, session_factory):
        self.Session = session_factory

    # =========================================================================
    # NORMALIZATION
    # =========================================================================

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        if value is None:
            return ""

        return str(value).strip()

    # =========================================================================
    # READ - ALL
    # =========================================================================

    def get_all(
        self,
    ) -> List[Personnel]:
        """
        Return all Personnel with Department eagerly loaded.
        """

        session = self.Session()

        try:

            return (
                session.query(
                    Personnel
                )
                .options(
                    joinedload(
                        Personnel.department
                    )
                )
                .order_by(
                    Personnel.full_name.asc()
                )
                .all()
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def get_all_personnel(
        self,
    ) -> List[Personnel]:
        """
        Compatibility alias.
        """

        return self.get_all()

    # =========================================================================
    # READ - BY ID
    # =========================================================================

    def get_by_id(
        self,
        personnel_id: int,
    ) -> Optional[Personnel]:

        if personnel_id is None:
            return None

        session = self.Session()

        try:

            return (
                session.query(
                    Personnel
                )
                .options(
                    joinedload(
                        Personnel.department
                    )
                )
                .filter(
                    Personnel.id
                    == personnel_id
                )
                .first()
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def get_personnel_by_id(
        self,
        personnel_id: int,
    ) -> Optional[Personnel]:
        """
        Compatibility alias.
        """

        return self.get_by_id(
            personnel_id
        )

    # =========================================================================
    # READ - BY CODE
    # =========================================================================

    def get_by_code(
        self,
        personnel_code: str,
    ) -> Optional[Personnel]:

        code = (
            self._normalize_text(
                personnel_code
            )
        )

        if not code:
            return None

        session = self.Session()

        try:

            return (
                session.query(
                    Personnel
                )
                .options(
                    joinedload(
                        Personnel.department
                    )
                )
                .filter(
                    Personnel.personnel_code
                    == code
                )
                .first()
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def get_personnel_by_code(
        self,
        personnel_code: str,
    ) -> Optional[Personnel]:
        """
        Compatibility alias.
        """

        return self.get_by_code(
            personnel_code
        )

    # =========================================================================
    # READ - BY DEPARTMENT
    # =========================================================================

    def get_by_department(
        self,
        department_id: int,
    ) -> List[Personnel]:
        """
        Return Personnel belonging ONLY to department_id.

        This is the key method used by the completion workflow.
        """

        if department_id is None:
            return []

        session = self.Session()

        try:

            return (
                session.query(
                    Personnel
                )
                .options(
                    joinedload(
                        Personnel.department
                    )
                )
                .filter(
                    Personnel.department_id
                    == department_id
                )
                .order_by(
                    Personnel.full_name.asc()
                )
                .all()
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def get_personnel_by_department(
        self,
        department_id: int,
    ) -> List[Personnel]:
        """
        Compatibility alias.
        """

        return self.get_by_department(
            department_id
        )

    # -------------------------------------------------------------------------

    def get_for_department(
        self,
        department_id: int,
    ) -> List[Personnel]:
        """
        Explicitly named completion-workflow helper.
        """

        return self.get_by_department(
            department_id
        )

    # =========================================================================
    # READ - ACTIVE DEPARTMENT WORKER LOOKUP
    # =========================================================================

    def get_personnel_for_completion(
        self,
        department_id: int,
    ) -> List[dict]:
        """
        Return a lightweight list suitable for a Personnel combobox.

        Result:

            [
                {
                    "id": 1,
                    "personnel_code": "...",
                    "full_name": "...",
                    "department_id": 2,
                    "department_name": "..."
                }
            ]
        """

        personnel = (
            self.get_by_department(
                department_id
            )
        )

        result = []

        for person in personnel:

            result.append(
                {
                    "id": person.id,
                    "personnel_code": (
                        person.personnel_code
                        or ""
                    ),
                    "full_name": (
                        person.full_name
                        or ""
                    ),
                    "department_id": (
                        person.department_id
                    ),
                    "department_name": (
                        person.department.name
                        if person.department
                        else ""
                    ),
                }
            )

        return result

    # =========================================================================
    # DEPARTMENTS
    # =========================================================================

    def get_departments(
        self,
    ) -> List[Department]:
        """
        Return Department objects.

        The previous temporary implementation returned only strings.
        The final repository returns the actual Department objects because
        the new workflow needs Department IDs.
        """

        session = self.Session()

        try:

            return (
                session.query(
                    Department
                )
                .order_by(
                    Department.name.asc()
                )
                .all()
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def get_department_names(
        self,
    ) -> List[str]:
        """
        Return names only for simple comboboxes.
        """

        return [
            department.name
            for department
            in self.get_departments()
            if department.name
        ]

    # -------------------------------------------------------------------------

    def get_department_map(
        self,
    ) -> Dict[str, int]:

        return {
            department.name: department.id
            for department
            in self.get_departments()
            if department.name
        }

    # =========================================================================
    # SEARCH
    # =========================================================================

    def search(
        self,
        keyword: str,
    ) -> List[Personnel]:

        keyword = (
            self._normalize_text(
                keyword
            )
        )

        session = self.Session()

        try:

            if not keyword:

                return (
                    session.query(
                        Personnel
                    )
                    .options(
                        joinedload(
                            Personnel.department
                        )
                    )
                    .order_by(
                        Personnel.full_name.asc()
                    )
                    .all()
                )

            pattern = (
                f"%{keyword}%"
            )

            return (
                session.query(
                    Personnel
                )
                .options(
                    joinedload(
                        Personnel.department
                    )
                )
                .filter(
                    (
                        Personnel.full_name.like(
                            pattern
                        )
                    )
                    |
                    (
                        Personnel.personnel_code.like(
                            pattern
                        )
                    )
                )
                .order_by(
                    Personnel.full_name.asc()
                )
                .all()
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def search_personnel(
        self,
        keyword: str,
    ) -> List[Personnel]:
        """
        Compatibility alias.
        """

        return self.search(
            keyword
        )

    # =========================================================================
    # EXISTENCE / VALIDATION
    # =========================================================================

    def personnel_code_exists(
        self,
        personnel_code: str,
        exclude_id: int = None,
    ) -> bool:

        code = (
            self._normalize_text(
                personnel_code
            )
        )

        if not code:
            return False

        session = self.Session()

        try:

            query = (
                session.query(
                    Personnel
                )
                .filter(
                    Personnel.personnel_code
                    == code
                )
            )

            if exclude_id is not None:

                query = query.filter(
                    Personnel.id
                    != exclude_id
                )

            return (
                query.first()
                is not None
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def validate_department(
        self,
        department_id: int,
    ) -> Tuple[
        bool,
        str,
    ]:

        if department_id is None:
            return (
                False,
                "دپارتمان مشخص نشده است.",
            )

        session = self.Session()

        try:

            department = (
                session.query(
                    Department
                )
                .filter(
                    Department.id
                    == department_id
                )
                .first()
            )

            if not department:

                return (
                    False,
                    "دپارتمان انتخاب‌شده وجود ندارد.",
                )

            return (
                True,
                "دپارتمان معتبر است.",
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def validate_personnel_for_department(
        self,
        personnel_id: int,
        department_id: int,
    ) -> Tuple[
        bool,
        str,
    ]:
        """
        Critical completion validation.

        A Personnel is valid for a Work Order/PM ONLY when:

            Personnel.department_id == department_id
        """

        if personnel_id is None:
            return (
                False,
                "پرسنل انجام‌دهنده انتخاب نشده است.",
            )

        if department_id is None:
            return (
                False,
                "دپارتمان دستور کار مشخص نشده است.",
            )

        session = self.Session()

        try:

            person = (
                session.query(
                    Personnel
                )
                .filter(
                    Personnel.id
                    == personnel_id
                )
                .first()
            )

            if not person:

                return (
                    False,
                    "پرسنل انتخاب‌شده یافت نشد.",
                )

            if (
                person.department_id
                != department_id
            ):

                return (
                    False,
                    (
                        "این پرسنل متعلق به دپارتمان "
                        "دستور کار نیست."
                    ),
                )

            return (
                True,
                "پرسنل برای این دستور کار معتبر است.",
            )

        finally:
            session.close()

    # =========================================================================
    # CREATE
    # =========================================================================

    def create(
        self,
        personnel_code: str,
        full_name: str,
        department_id: int,
    ) -> Tuple[
        bool,
        str,
        Optional[Personnel],
    ]:
        """
        Create Personnel.
        """

        code = (
            self._normalize_text(
                personnel_code
            )
        )

        name = (
            self._normalize_text(
                full_name
            )
        )

        # ---------------------------------------------------------------------
        # Required fields
        # ---------------------------------------------------------------------

        if not code:

            return (
                False,
                "شماره پرسنلی الزامی است.",
                None,
            )

        if not name:

            return (
                False,
                "نام کامل پرسنل الزامی است.",
                None,
            )

        if department_id is None:

            return (
                False,
                "انتخاب دپارتمان الزامی است.",
                None,
            )

        # ---------------------------------------------------------------------
        # Duplicate code
        # ---------------------------------------------------------------------

        if self.personnel_code_exists(
            code
        ):

            return (
                False,
                "این شماره پرسنلی قبلاً ثبت شده است.",
                None,
            )

        # ---------------------------------------------------------------------
        # Department
        # ---------------------------------------------------------------------

        valid_department, message = (
            self.validate_department(
                department_id
            )
        )

        if not valid_department:

            return (
                False,
                message,
                None,
            )

        # ---------------------------------------------------------------------
        # Insert
        # ---------------------------------------------------------------------

        session = self.Session()

        try:

            person = Personnel(
                personnel_code=code,
                full_name=name,
                department_id=department_id,
            )

            session.add(
                person
            )

            session.commit()
            session.refresh(
                person
            )

            try:
                log_action(
                    "CREATE",
                    "personnel",
                    person.id,
                    (
                        f"کد: {code}, "
                        f"نام: {name}, "
                        f"دپارتمان: {department_id}"
                    ),
                )
            except Exception:
                pass

            return (
                True,
                "پرسنل با موفقیت ثبت شد.",
                person,
            )

        except IntegrityError:

            session.rollback()

            return (
                False,
                "شماره پرسنلی تکراری است.",
                None,
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                f"خطای پایگاه داده: {exc}",
                None,
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def create_personnel(
        self,
        personnel_code: str,
        full_name: str,
        department_id: int,
    ) -> Tuple[
        bool,
        str,
        Optional[Personnel],
    ]:
        """
        Compatibility alias.
        """

        return self.create(
            personnel_code,
            full_name,
            department_id,
        )

    # =========================================================================
    # UPDATE
    # =========================================================================

    def update(
        self,
        personnel_id: int,
        personnel_code: str,
        full_name: str,
        department_id: int,
    ) -> Tuple[
        bool,
        str,
    ]:
        """
        Update Personnel.

        Changing the department is safe because historical completion
        records remain attached to the Personnel ID.

        The new department becomes the Personnel's current department.
        """

        if personnel_id is None:

            return (
                False,
                "شناسه پرسنل نامعتبر است.",
            )

        code = (
            self._normalize_text(
                personnel_code
            )
        )

        name = (
            self._normalize_text(
                full_name
            )
        )

        if not code:

            return (
                False,
                "شماره پرسنلی الزامی است.",
            )

        if not name:

            return (
                False,
                "نام کامل پرسنل الزامی است.",
            )

        if department_id is None:

            return (
                False,
                "انتخاب دپارتمان الزامی است.",
            )

        if self.personnel_code_exists(
            code,
            exclude_id=personnel_id,
        ):

            return (
                False,
                "این شماره پرسنلی قبلاً برای شخص دیگری ثبت شده است.",
            )

        valid_department, message = (
            self.validate_department(
                department_id
            )
        )

        if not valid_department:

            return (
                False,
                message,
            )

        session = self.Session()

        try:

            person = (
                session.query(
                    Personnel
                )
                .filter(
                    Personnel.id
                    == personnel_id
                )
                .first()
            )

            if not person:

                return (
                    False,
                    "پرسنل یافت نشد.",
                )

            old_code = (
                person.personnel_code
                or ""
            )

            old_name = (
                person.full_name
            )

            old_department_id = (
                person.department_id
            )

            person.personnel_code = (
                code
            )

            person.full_name = (
                name
            )

            person.department_id = (
                department_id
            )

            session.commit()

            try:
                log_action(
                    "UPDATE",
                    "personnel",
                    personnel_id,
                    (
                        f"کد قبلی: {old_code}, "
                        f"نام قبلی: {old_name}, "
                        f"دپارتمان قبلی: "
                        f"{old_department_id}, "
                        f"دپارتمان جدید: "
                        f"{department_id}"
                    ),
                )
            except Exception:
                pass

            return (
                True,
                "اطلاعات پرسنل با موفقیت بروزرسانی شد.",
            )

        except IntegrityError:

            session.rollback()

            return (
                False,
                "شماره پرسنلی تکراری است.",
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                f"خطای پایگاه داده: {exc}",
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def update_personnel(
        self,
        personnel_id: int,
        personnel_code: str,
        full_name: str,
        department_id: int,
    ) -> Tuple[
        bool,
        str,
    ]:
        """
        Compatibility alias.
        """

        return self.update(
            personnel_id,
            personnel_code,
            full_name,
            department_id,
        )

    # =========================================================================
    # DELETE
    # =========================================================================

    def has_completion_history(
        self,
        personnel_id: int,
    ) -> bool:
        """
        True when the Personnel has been recorded as a worker
        who completed a Work Order.
        """

        if personnel_id is None:
            return False

        session = self.Session()

        try:

            wo_history = (
                session.query(work_order_completers)
                .filter(
                    work_order_completers.c.personnel_id == personnel_id
                )
                .first()
                is not None
            )

            repair_history = (
                session.query(repair_request_completers)
                .filter(
                    repair_request_completers.c.personnel_id == personnel_id
                )
                .first()
                is not None
            )

            return wo_history or repair_history

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def delete(
        self,
        personnel_id: int,
    ) -> Tuple[
        bool,
        str,
    ]:
        """
        Delete Personnel only when there is no completion history.

        We never delete historical completion information automatically.
        """

        if personnel_id is None:

            return (
                False,
                "شناسه پرسنل نامعتبر است.",
            )

        session = self.Session()

        try:

            person = (
                session.query(
                    Personnel
                )
                .filter(
                    Personnel.id
                    == personnel_id
                )
                .first()
            )

            if not person:

                return (
                    False,
                    "پرسنل یافت نشد.",
                )

            # ------------------------------------------------------------
            # Completion history
            # ------------------------------------------------------------

            wo_history = (
                session.query(work_order_completers)
                .filter(
                    work_order_completers.c.personnel_id == personnel_id
                )
                .first()
                is not None
            )

            repair_history = (
                session.query(repair_request_completers)
                .filter(
                    repair_request_completers.c.personnel_id == personnel_id
                )
                .first()
                is not None
            )

            if wo_history or repair_history:

                return (
                    False,
                    (
                        "این پرسنل دارای سابقه انجام کار تعمیراتی است "
                        "و قابل حذف نیست.\n\n"
                        "برای حفظ سابقه تعمیرات، حذف این پرسنل "
                        "انجام نمی‌شود."
                    ),
                )

            old_code = (
                person.personnel_code
                or ""
            )

            old_name = (
                person.full_name
            )

            old_department_id = (
                person.department_id
            )

            session.delete(
                person
            )

            session.commit()

            try:
                log_action(
                    "DELETE",
                    "personnel",
                    personnel_id,
                    (
                        f"کد: {old_code}, "
                        f"نام: {old_name}, "
                        f"دپارتمان: "
                        f"{old_department_id}"
                    ),
                )
            except Exception:
                pass

            return (
                True,
                "پرسنل با موفقیت حذف شد.",
            )

        except IntegrityError:

            session.rollback()

            return (
                False,
                (
                    "پرسنل به دلیل وجود "
                    "اطلاعات مرتبط قابل حذف نیست."
                ),
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                f"خطای پایگاه داده: {exc}",
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def delete_personnel(
        self,
        personnel_id: int,
    ) -> Tuple[
        bool,
        str,
    ]:
        """
        Compatibility alias.
        """

        return self.delete(
            personnel_id
        )

    # =========================================================================
    # DICTIONARY HELPERS
    # =========================================================================

    # =========================================================================
    # COMPLETION COUNTS
    # =========================================================================

    def get_completed_work_counts(self, personnel_ids=None) -> Dict[int, int]:
        """Return combined completed Work Order + Repair Request counts."""
        if personnel_ids is None:
            personnel_ids = []
        ids = []
        seen = set()
        for value in personnel_ids:
            try:
                pid = int(value)
            except (TypeError, ValueError):
                continue
            if pid > 0 and pid not in seen:
                seen.add(pid)
                ids.append(pid)
        result = {pid: 0 for pid in ids}
        if not ids:
            return result

        session = self.Session()
        try:
            wo_rows = (
                session.query(
                    work_order_completers.c.personnel_id,
                    func.count().label("cnt"),
                )
                .filter(work_order_completers.c.personnel_id.in_(ids))
                .group_by(work_order_completers.c.personnel_id)
                .all()
            )
            rr_rows = (
                session.query(
                    repair_request_completers.c.personnel_id,
                    func.count().label("cnt"),
                )
                .filter(repair_request_completers.c.personnel_id.in_(ids))
                .group_by(repair_request_completers.c.personnel_id)
                .all()
            )
            for pid, cnt in wo_rows:
                result[int(pid)] = result.get(int(pid), 0) + int(cnt)
            for pid, cnt in rr_rows:
                result[int(pid)] = result.get(int(pid), 0) + int(cnt)
            return result
        finally:
            session.close()

    # -------------------------------------------------------------------------

    def get_completed_work_count(self, personnel_id: int) -> int:
        return self.get_completed_work_counts([personnel_id]).get(int(personnel_id), 0) if personnel_id is not None else 0

    @staticmethod
    def to_dict(
        person: Personnel,
    ) -> dict:

        return {
            "id": person.id,

            "personnel_code": (
                person.personnel_code
                or ""
            ),

            "full_name": (
                person.full_name
                or ""
            ),

            "department_id": (
                person.department_id
            ),

            "department_name": (
                person.department.name
                if person.department
                else ""
            ),
        }

    # -------------------------------------------------------------------------

    def get_all_dict(
        self,
    ) -> List[dict]:

        return [
            self.to_dict(person)
            for person in self.get_all()
        ]

    # -------------------------------------------------------------------------

    def get_by_department_dict(
        self,
        department_id: int,
    ) -> List[dict]:

        return [
            self.to_dict(person)
            for person
            in self.get_by_department(
                department_id
            )
        ]
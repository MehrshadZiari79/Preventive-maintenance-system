# database/department_repository.py
"""
PM System - Department Repository
==================================

Departments contain only:

    id
    name

Used by:
    - Personnel management
    - PM creation
    - Work Order creation
    - Work Order completion filtering

This repository does NOT perform migrations.

Important:
    A department must not be deleted while it is referenced by
    Personnel, PM Schedules, or Work Orders.
"""

from typing import Optional, List, Tuple

from sqlalchemy.exc import IntegrityError

from database.models import (
    Department,
    Personnel,
    PMSchedule,
)
from database.work_order import WorkOrder

from utils.logger import log_action


class DepartmentRepository:
    """
    CRUD repository for Department records.

    Constructor follows the same pattern as the existing repositories:

        DepartmentRepository(SessionLocal)
    """

    def __init__(self, session_factory):
        self.Session = session_factory

    # =========================================================================
    # NORMALIZATION
    # =========================================================================

    @staticmethod
    def _normalize_name(
        name: str,
    ) -> str:
        if name is None:
            return ""

        return str(name).strip()

    # =========================================================================
    # READ
    # =========================================================================

    def get_all(
        self,
    ) -> List[Department]:
        """
        Return all departments alphabetically.
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

    def get_all_departments(
        self,
    ) -> List[Department]:
        """
        Compatibility alias.
        """

        return self.get_all()

    # -------------------------------------------------------------------------

    def get_by_id(
        self,
        department_id: int,
    ) -> Optional[Department]:
        """
        Get a department by ID.
        """

        if department_id is None:
            return None

        session = self.Session()

        try:
            return (
                session.query(
                    Department
                )
                .filter(
                    Department.id
                    == department_id
                )
                .first()
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def get_department_by_id(
        self,
        department_id: int,
    ) -> Optional[Department]:
        """
        Compatibility alias used by the management dialog.
        """

        return self.get_by_id(
            department_id
        )

    # -------------------------------------------------------------------------

    def get_by_name(
        self,
        name: str,
    ) -> Optional[Department]:
        """
        Find a department by exact normalized name.
        """

        normalized = (
            self._normalize_name(
                name
            )
        )

        if not normalized:
            return None

        session = self.Session()

        try:
            return (
                session.query(
                    Department
                )
                .filter(
                    Department.name
                    == normalized
                )
                .first()
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def exists(
        self,
        name: str,
        exclude_id: int = None,
    ) -> bool:
        """
        Check whether a department name already exists.
        """

        normalized = (
            self._normalize_name(
                name
            )
        )

        if not normalized:
            return False

        session = self.Session()

        try:
            query = (
                session.query(
                    Department
                )
                .filter(
                    Department.name
                    == normalized
                )
            )

            if exclude_id is not None:

                query = query.filter(
                    Department.id
                    != exclude_id
                )

            return (
                query.first()
                is not None
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def search(
        self,
        keyword: str,
    ) -> List[Department]:
        """
        Search departments by name.
        """

        keyword = (
            self._normalize_name(
                keyword
            )
        )

        session = self.Session()

        try:

            if not keyword:
                return (
                    session.query(
                        Department
                    )
                    .order_by(
                        Department.name.asc()
                    )
                    .all()
                )

            pattern = (
                f"%{keyword}%"
            )

            return (
                session.query(
                    Department
                )
                .filter(
                    Department.name.like(
                        pattern
                    )
                )
                .order_by(
                    Department.name.asc()
                )
                .all()
            )

        finally:
            session.close()

    # =========================================================================
    # PERSONNEL / USAGE COUNTS
    # =========================================================================

    def count_personnel(
        self,
        department_id: int,
    ) -> int:
        """
        Number of personnel assigned to the department.
        """

        if department_id is None:
            return 0

        session = self.Session()

        try:
            return (
                session.query(
                    Personnel
                )
                .filter(
                    Personnel.department_id
                    == department_id
                )
                .count()
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def count_pm_schedules(
        self,
        department_id: int,
    ) -> int:
        """
        Number of PM schedules assigned to the department.
        """

        if department_id is None:
            return 0

        session = self.Session()

        try:
            return (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.department_id
                    == department_id
                )
                .count()
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def count_work_orders(
        self,
        department_id: int,
    ) -> int:
        """
        Number of Work Orders assigned to the department.
        """

        if department_id is None:
            return 0

        session = self.Session()

        try:
            return (
                session.query(
                    WorkOrder
                )
                .filter(
                    WorkOrder.department_id
                    == department_id
                )
                .count()
            )

        finally:
            session.close()

    # -------------------------------------------------------------------------

    def get_usage(
        self,
        department_id: int,
    ) -> dict:
        """
        Return all reference counts.
        """

        return {
            "personnel": self.count_personnel(
                department_id
            ),
            "pm_schedules": self.count_pm_schedules(
                department_id
            ),
            "work_orders": self.count_work_orders(
                department_id
            ),
        }

    # =========================================================================
    # CREATE
    # =========================================================================

    def create(
        self,
        name: str,
    ) -> Tuple[
        bool,
        str,
        Optional[Department],
    ]:
        """
        Create a Department.

        Returns:
            (success, message, department)
        """

        normalized = (
            self._normalize_name(
                name
            )
        )

        if not normalized:
            return (
                False,
                "نام دپارتمان الزامی است.",
                None,
            )

        if self.exists(
            normalized
        ):
            return (
                False,
                "این دپارتمان قبلاً ثبت شده است.",
                None,
            )

        session = self.Session()

        try:

            department = Department(
                name=normalized
            )

            session.add(
                department
            )

            session.commit()
            session.refresh(
                department
            )

            try:
                log_action(
                    "CREATE",
                    "department",
                    department.id,
                    f"نام دپارتمان: {normalized}",
                )
            except Exception:
                pass

            return (
                True,
                "دپارتمان با موفقیت ایجاد شد.",
                department,
            )

        except IntegrityError:

            session.rollback()

            return (
                False,
                "این دپارتمان قبلاً ثبت شده است.",
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

    def create_department(
        self,
        name: str,
    ) -> Tuple[
        bool,
        str,
        Optional[Department],
    ]:
        """
        Compatibility alias.
        """

        return self.create(
            name
        )

    # =========================================================================
    # UPDATE
    # =========================================================================

    def update(
        self,
        department_id: int,
        name: str,
    ) -> Tuple[
        bool,
        str,
    ]:
        """
        Rename a department.

        Existing Personnel / PM / Work Orders remain linked because
        they reference the department ID, not the department name.
        """

        if department_id is None:
            return (
                False,
                "شناسه دپارتمان نامعتبر است.",
            )

        normalized = (
            self._normalize_name(
                name
            )
        )

        if not normalized:
            return (
                False,
                "نام دپارتمان الزامی است.",
            )

        if self.exists(
            normalized,
            exclude_id=department_id,
        ):
            return (
                False,
                "دپارتمان دیگری با این نام وجود دارد.",
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
                    "دپارتمان یافت نشد.",
                )

            old_name = (
                department.name
            )

            department.name = (
                normalized
            )

            session.commit()

            try:
                log_action(
                    "UPDATE",
                    "department",
                    department_id,
                    (
                        f"نام قبلی: {old_name}, "
                        f"نام جدید: {normalized}"
                    ),
                )
            except Exception:
                pass

            return (
                True,
                "دپارتمان با موفقیت بروزرسانی شد.",
            )

        except IntegrityError:

            session.rollback()

            return (
                False,
                "این نام دپارتمان قبلاً استفاده شده است.",
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

    def update_department(
        self,
        department_id: int,
        name: str,
    ) -> Tuple[
        bool,
        str,
    ]:
        """
        Compatibility alias.
        """

        return self.update(
            department_id,
            name,
        )

    # =========================================================================
    # DELETE
    # =========================================================================

    def delete(
        self,
        department_id: int,
    ) -> Tuple[
        bool,
        str,
    ]:
        """
        Delete a department only when it is unused.

        We deliberately do NOT cascade-delete Personnel, PMs, or Work Orders.
        """

        if department_id is None:
            return (
                False,
                "شناسه دپارتمان نامعتبر است.",
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
                    "دپارتمان یافت نشد.",
                )

            # ------------------------------------------------------------
            # Personnel reference check
            # ------------------------------------------------------------

            personnel_count = (
                session.query(
                    Personnel
                )
                .filter(
                    Personnel.department_id
                    == department_id
                )
                .count()
            )

            if personnel_count > 0:

                return (
                    False,
                    (
                        "این دپارتمان قابل حذف نیست.\n\n"
                        f"{personnel_count} پرسنل به آن اختصاص داده شده‌اند.\n"
                        "ابتدا تکلیف پرسنل را مشخص کنید."
                    ),
                )

            # ------------------------------------------------------------
            # PM reference check
            # ------------------------------------------------------------

            pm_count = (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.department_id
                    == department_id
                )
                .count()
            )

            if pm_count > 0:

                return (
                    False,
                    (
                        "این دپارتمان قابل حذف نیست.\n\n"
                        f"{pm_count} برنامه PM به آن اختصاص داده شده‌اند."
                    ),
                )

            # ------------------------------------------------------------
            # Work Order reference check
            # ------------------------------------------------------------

            work_order_count = (
                session.query(
                    WorkOrder
                )
                .filter(
                    WorkOrder.department_id
                    == department_id
                )
                .count()
            )

            if work_order_count > 0:

                return (
                    False,
                    (
                        "این دپارتمان قابل حذف نیست.\n\n"
                        f"{work_order_count} دستورکار به آن اختصاص داده شده‌اند."
                    ),
                )

            old_name = (
                department.name
            )

            session.delete(
                department
            )

            session.commit()

            try:
                log_action(
                    "DELETE",
                    "department",
                    department_id,
                    f"نام دپارتمان: {old_name}",
                )
            except Exception:
                pass

            return (
                True,
                "دپارتمان با موفقیت حذف شد.",
            )

        except IntegrityError:

            session.rollback()

            return (
                False,
                (
                    "دپارتمان به دلیل وجود "
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

    def delete_department(
        self,
        department_id: int,
    ) -> Tuple[
        bool,
        str,
    ]:
        """
        Compatibility alias.
        """

        return self.delete(
            department_id
        )

    # =========================================================================
    # COMBOBOX HELPERS
    # =========================================================================

    def get_name_id_map(
        self,
    ) -> dict:
        """
        Return:

            {
                "دپارتمان تعمیرات": 1,
                "دپارتمان برق": 2,
            }
        """

        departments = self.get_all()

        return {
            department.name: department.id
            for department in departments
            if department.name
        }

    # -------------------------------------------------------------------------

    def get_names(
        self,
    ) -> List[str]:
        """
        Return department names only.
        """

        return [
            department.name
            for department in self.get_all()
            if department.name
        ]

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def validate_department(
        self,
        department_id: int,
    ) -> Tuple[
        bool,
        str,
    ]:
        """
        Validate that a department exists.
        """

        department = (
            self.get_by_id(
                department_id
            )
        )

        if not department:
            return (
                False,
                "دپارتمان یافت نشد.",
            )

        return (
            True,
            "دپارتمان معتبر است.",
        )
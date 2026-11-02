# database/work_order_repository.py
"""
PM System - Work Order Repository
=================================

FINAL WORKFLOW
--------------

WORK ORDER CREATION
-------------------
A new Work Order requires:

    - title
    - equipment
    - department
    - scheduled date/time

No Personnel is selected during creation.

Legacy User technician fields remain available for historical records
and old application compatibility.

PM GENERATED WORK ORDER
-----------------------
A Work Order generated from a PM inherits:

    PMSchedule.department_id
            ->
    WorkOrder.department_id

No User technician is automatically assigned.

FINISH REQUEST
--------------
When the actual maintenance is finished:

    WorkOrder.department_id
            ->
    Personnel belonging to that department
            ->
    selected Personnel
            ->
    work_order_completers
            ->
    FINISH_REQUESTED

The normal Finish workflow may restrict Personnel by department.
Administrative editing of an existing completion uses the organization-wide
Personnel list so historical completion records can be corrected safely.

FINAL APPROVAL
--------------
Manager approval requires at least one valid completion Personnel.

IMPORTANT
---------
This repository does NOT perform database migrations.

Existing production data is preserved.
Legacy User assignments are preserved.
New Personnel completion records use work_order_completers.
"""

import json

from datetime import (
    datetime,
    timedelta,
)

from typing import (
    Optional,
)

from sqlalchemy.orm import joinedload

from database.work_order import (
    WorkOrder,
    WorkOrderStatus,
    WorkOrderType,
    WorkOrderPriority,
)

from database.models import (
    Personnel,
    Department,
    SparePart,
    SparePartTransaction,
    work_order_technicians,
)

from utils.logger import log_action
from utils.date_helpers import tehran_now, to_jalali_date_str  # Iranian (Asia/Tehran) clock


# ============================================================================
# REPOSITORY
# ============================================================================

class WorkOrderRepository:

    def __init__(
        self,
        session_factory,
    ):
        self.Session = session_factory

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _text(
        value,
    ):
        if value is None:
            return ""

        return str(
            value
        ).strip()

    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_personnel_ids(personnel_ids=None, personnel_id=None):
        candidates = []
        if personnel_ids is not None:
            if isinstance(personnel_ids, (list, tuple, set)):
                candidates.extend(personnel_ids)
            else:
                candidates.append(personnel_ids)
        if personnel_id is not None:
            candidates.append(personnel_id)

        normalized = []
        seen = set()
        for value in candidates:
            if value is None:
                continue
            try:
                pid = int(value)
            except (TypeError, ValueError):
                continue
            if pid <= 0 or pid in seen:
                continue
            seen.add(pid)
            normalized.append(pid)
        return normalized

    # -------------------------------------------------------------------------

    @staticmethod
    def _as_int(value, field_name, allow_none=True):
        if value is None and allow_none:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} نامعتبر است.")

    # -------------------------------------------------------------------------
    # BACKWARD WORKFLOW
    # -------------------------------------------------------------------------

    @staticmethod
    def _coerce_status(status):
        """Normalize enum instances, enum names, and enum values."""
        if isinstance(status, WorkOrderStatus):
            return status

        raw = str(status or "").strip()
        if not raw:
            return None

        try:
            return WorkOrderStatus[raw]
        except Exception:
            pass

        try:
            return WorkOrderStatus(raw)
        except Exception:
            return None

    @classmethod
    def backward_status_options(cls, status):
        """
        Return the earlier workflow stages that are safe to reopen.

        Final APPROVED / REJECTED records are intentionally excluded here.
        APPROVED can advance a PM schedule, while REJECTED creates a new
        corrective Work Order, so silently rewinding either state would make
        related records inconsistent.
        """
        current = cls._coerce_status(status)
        if current is None:
            return []

        order = [
            WorkOrderStatus.PENDING_APPROVAL,
            WorkOrderStatus.PENDING,
            WorkOrderStatus.IN_PROGRESS,
            WorkOrderStatus.FINISH_REQUESTED,
        ]

        try:
            index = order.index(current)
        except ValueError:
            return []

        return list(reversed(order[:index]))

    @classmethod
    def status_label(cls, status):
        labels = {
            WorkOrderStatus.PENDING_APPROVAL: "در انتظار تأیید",
            WorkOrderStatus.PENDING: "در انتظار",
            WorkOrderStatus.IN_PROGRESS: "در حال انجام",
            WorkOrderStatus.FINISH_REQUESTED: "درخواست اتمام",
            WorkOrderStatus.APPROVED: "تایید شده",
            WorkOrderStatus.REJECTED: "رد شده",
            WorkOrderStatus.COMPLETED: "تکمیل شده",
        }
        key = cls._coerce_status(status)
        if key is None:
            return str(status or "")
        return labels.get(key, str(key.value))

    # -------------------------------------------------------------------------

    @staticmethod
    def _as_datetime(value, field_name, allow_none=True):
        if value is None and allow_none:
            return None
        from datetime import date as _date
        if isinstance(value, datetime):
            return value
        if isinstance(value, _date):
            return datetime(value.year, value.month, value.day)
        raise ValueError(f"{field_name} نامعتبر است.")

    @staticmethod
    def _personnel_dict(
        personnel,
        department_name=None,
    ):
        if personnel is None:
            return None

        return {
            "id": getattr(
                personnel,
                "id",
                None,
            ),
            "personnel_code": (
                getattr(
                    personnel,
                    "personnel_code",
                    "",
                )
                or ""
            ),
            "full_name": (
                getattr(
                    personnel,
                    "full_name",
                    "",
                )
                or ""
            ),
            "department_id": getattr(
                personnel,
                "department_id",
                None,
            ),
            "department_name": (
                department_name
                or ""
            ),
        }

    # -------------------------------------------------------------------------

    @staticmethod
    def _clear_completion_personnel(
        wo,
    ):
        """
        Remove completion Personnel from the ORM collection.

        This only affects the selected Work Order.
        Historical User technician information is untouched.
        """

        try:
            wo.completers.clear()
        except Exception:
            pass

    # -------------------------------------------------------------------------

    def _set_completion_personnel(
        self,
        wo,
        personnel_list,
    ):
        """
        Replace the completion Personnel collection with the supplied list.

        ``personnel_list`` must contain ORM Personnel objects.
        The collection is many-to-many, so multiple workers can be recorded
        for one Work Order.
        """
        self._clear_completion_personnel(wo)

        if not personnel_list:
            return

        for person in personnel_list:
            if person is not None:
                wo.completers.append(person)

    # -------------------------------------------------------------------------

    def _get_completion_personnel(
        self,
        wo,
    ):
        """Return the stored completion Personnel collection."""
        try:
            return list(wo.completers or [])
        except Exception:
            return []

    # -------------------------------------------------------------------------

    def _validate_creation(
        self,
        title,
        equipment_id,
        scheduled_date,
        department_id,
    ):
        """
        Validate all required Work Order creation information.
        """

        if not self._text(title):

            return (
                False,
                "عنوان دستور کار الزامی است.",
            )

        if not equipment_id:

            return (
                False,
                "انتخاب تجهیز الزامی است.",
            )

        if not department_id:

            return (
                False,
                "انتخاب دپارتمان مسئول الزامی است.",
            )

        if not scheduled_date:

            return (
                False,
                "تاریخ و ساعت برنامه‌ریزی الزامی است.",
            )

        return (
            True,
            "",
        )

    # =========================================================================
    # DUPLICATE
    # =========================================================================

    def duplicate_exists(
        self,
        equipment_id: int,
        title: str,
        scheduled_date: datetime,
        exclude_id: int = None,
    ) -> bool:

        session = self.Session()

        try:

            query = (
                session.query(
                    WorkOrder
                )
                .filter(
                    WorkOrder.equipment_id
                    == equipment_id,

                    WorkOrder.title
                    == title,

                    WorkOrder.scheduled_date
                    == scheduled_date,
                )
            )

            if exclude_id:

                query = query.filter(
                    WorkOrder.id
                    != exclude_id
                )

            return (
                query.first()
                is not None
            )

        finally:

            session.close()

    # =========================================================================
    # CREATE WORK ORDER
    # =========================================================================

    def create_work_order(
        self,
        title,
        equipment_id,
        type_str,
        priority,
        technician_id=None,
        scheduled_date=None,
        description=None,
        parts_used=None,
        schedule_id=None,
        operator_id=None,
        failure_report_time=None,
        operator_notes=None,
        operator_signature=None,
        manual_cost=0.0,
        cost_description=None,
        deadline=None,
        additional_technician_ids=None,
        department_id=None,
        completion_personnel_ids=None,
    ):
        """
        Create a Work Order.

        technician_id and additional_technician_ids remain in the signature
        only for compatibility with older callers.

        New Work Orders NEVER assign a User technician.

        department_id is mandatory for all new Work Orders.
        """

        try:
            equipment_id = self._as_int(equipment_id, "شناسه تجهیز", allow_none=False)
            department_id = self._as_int(department_id, "شناسه دپارتمان", allow_none=False)
            schedule_id = self._as_int(schedule_id, "شناسه برنامه PM")
            scheduled_date = self._as_datetime(scheduled_date, "تاریخ برنامه‌ریزی", allow_none=False)
            failure_report_time = self._as_datetime(failure_report_time, "زمان اعلام خرابی")
            deadline = self._as_datetime(deadline, "مهلت انجام")
            if manual_cost is None:
                manual_cost = 0.0
            manual_cost = float(manual_cost)
        except ValueError as exc:
            return False, str(exc)

        valid, message = (
            self._validate_creation(
                title=title,
                equipment_id=equipment_id,
                scheduled_date=scheduled_date,
                department_id=department_id,
            )
        )

        if not valid:
            return False, message

        session = self.Session()

        try:

            # ------------------------------------------------------------
            # Department validation
            # ------------------------------------------------------------

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
                    "دپارتمان انتخاب‌شده یافت نشد.",
                )

            # ------------------------------------------------------------
            # Duplicate
            # ------------------------------------------------------------

            if self.duplicate_exists(
                equipment_id,
                self._text(title),
                scheduled_date,
            ):

                return (
                    False,
                    (
                        "یک دستور کار با همین عنوان و تاریخ "
                        "برای این تجهیز قبلاً ثبت شده است."
                    ),
                )

            # ------------------------------------------------------------
            # Work Order type
            # ------------------------------------------------------------

            type_name = (
                str(
                    type_str
                    or ""
                ).upper()
            )

            if (
                type_name
                in WorkOrderType.__members__
            ):

                wo_type = (
                    WorkOrderType[
                        type_name
                    ]
                )

            else:

                wo_type = (
                    WorkOrderType.CORRECTIVE
                )

            # ------------------------------------------------------------
            # Priority
            # ------------------------------------------------------------

            priority_name = (
                str(
                    priority
                    or ""
                ).upper()
            )

            if (
                priority_name
                in WorkOrderPriority.__members__
            ):

                wo_priority = (
                    WorkOrderPriority[
                        priority_name
                    ]
                )

            else:

                wo_priority = (
                    WorkOrderPriority.MEDIUM
                )

            # ------------------------------------------------------------
            # Create
            # ------------------------------------------------------------

            wo = WorkOrder(
                equipment_id=(
                    equipment_id
                ),

                schedule_id=(
                    schedule_id
                ),

                department_id=(
                    department_id
                ),

                type=(
                    wo_type.name
                ),

                priority=(
                    wo_priority.name
                ),

                # New workflow:
                # no User technician is assigned.
                technician_id=None,
                operator_id=None,

                failure_report_time=(
                    failure_report_time
                ),
                operator_notes=None,
                operator_signature=None,

                title=(
                    self._text(
                        title
                    )
                ),

                description=(
                    self._text(
                        description
                    )
                    or None
                ),

                parts_used=(
                    self._text(
                        parts_used
                    )
                    or None
                ),

                scheduled_date=(
                    scheduled_date
                ),

                deadline=(
                    deadline
                ),

                status=(
                    WorkOrderStatus.PENDING.name
                ),

                manual_cost=(
                    manual_cost
                    or 0.0
                ),

                cost_description=(
                    self._text(
                        cost_description
                    )
                    or None
                ),
            )

            session.add(
                wo
            )

            session.flush()

            # No completion Personnel during creation.
            self._clear_completion_personnel(
                wo
            )

            session.commit()

            session.refresh(
                wo
            )

            try:

                log_action(
                    "CREATE",
                    "work_order",
                    wo.id,
                    (
                        f"عنوان: {title}, "
                        f"تجهیز: {equipment_id}, "
                        f"دپارتمان: {department_id}"
                    ),
                )

            except Exception:
                pass

            return (
                True,
                "دستور کار با موفقیت ثبت شد.",
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                f"خطا در ثبت دستور کار: {exc}",
            )

        finally:

            session.close()

    # =========================================================================
    # CREATE FROM PM
    # =========================================================================

    def create_from_pm(
        self,
        pm_schedule,
        due_date: datetime,
        created_by_user_id: int = None,
    ) -> tuple[bool, str]:
        """
        Automatically create a Work Order from a PM schedule.

        PM department becomes Work Order department.

        No User technician is assigned.

        No Personnel is assigned until actual completion.
        """

        if not pm_schedule:

            return (
                False,
                "برنامه PM نامعتبر است.",
            )

        if not due_date:

            return (
                False,
                "تاریخ سررسید PM مشخص نشده است.",
            )

        equipment_id = getattr(
            pm_schedule,
            "equipment_id",
            None,
        )

        department_id = getattr(
            pm_schedule,
            "department_id",
            None,
        )

        if not equipment_id:

            return (
                False,
                "تجهیز برنامه PM مشخص نشده است.",
            )

        if not department_id:

            return (
                False,
                (
                    "برای این برنامه PM "
                    "دپارتمان مسئول تعیین نشده است."
                ),
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
                    "دپارتمان برنامه PM یافت نشد.",
                )

            existing = (
                session.query(
                    WorkOrder
                )
                .filter(
                    WorkOrder.schedule_id
                    == pm_schedule.id,

                    WorkOrder.scheduled_date
                    == due_date,
                )
                .first()
            )

            if existing:

                return (
                    False,
                    (
                        "برای این برنامه PM و این تاریخ "
                        "قبلاً دستور کار ایجاد شده است."
                    ),
                )

            deadline = (
                due_date
            )

            try:

                duration = getattr(
                    pm_schedule,
                    "estimated_duration",
                    None,
                )

                if duration:

                    duration = int(
                        duration
                    )

                    if duration > 0:

                        deadline = (
                            due_date
                            + timedelta(
                                days=duration
                            )
                        )

            except (
                TypeError,
                ValueError,
            ):

                pass

            pm_title = (
                getattr(
                    pm_schedule,
                    "title",
                    None,
                )
                or "برنامه PM"
            )

            title = (
                f"[A-PM] "
                f"{pm_title} "
                f"{to_jalali_date_str(due_date) or due_date.strftime('%Y-%m-%d')}"
            )

            checklist = (
                getattr(
                    pm_schedule,
                    "checklist",
                    None,
                )
                or "ندارد"
            )

            parts_required = (
                getattr(
                    pm_schedule,
                    "parts_required",
                    None,
                )
                or "ندارد"
            )

            description = (
                "کار پیشگیرانه خودکار بر اساس برنامه PM: "
                f"{pm_title}\n"
                f"چک‌لیست: {checklist}\n"
                f"قطعات مورد نیاز: {parts_required}"
            )

            wo = WorkOrder(
                equipment_id=(
                    equipment_id
                ),

                schedule_id=(
                    pm_schedule.id
                ),

                department_id=(
                    department_id
                ),

                type=(
                    WorkOrderType.PREVENTIVE.name
                ),

                status=(
                    WorkOrderStatus.PENDING_APPROVAL.name
                ),

                priority=(
                    WorkOrderPriority.MEDIUM.name
                ),

                technician_id=None,

                title=title,

                description=description,

                scheduled_date=(
                    due_date
                ),

                deadline=deadline,

                created_at=(
                    tehran_now()
                ),

                manual_cost=0.0,
            )

            session.add(
                wo
            )

            session.flush()

            self._clear_completion_personnel(
                wo
            )

            session.commit()

            session.refresh(
                wo
            )

            try:

                log_action(
                    "CREATE_FROM_PM",
                    "work_order",
                    wo.id,
                    (
                        f"PM: {pm_schedule.id}, "
                        f"دپارتمان: {department_id}"
                    ),
                )

            except Exception:
                pass

            return (
                True,
                (
                    "دستور کار از برنامه PM "
                    "با موفقیت ایجاد شد."
                ),
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                f"خطا در ایجاد دستورکار از PM: {exc}",
            )

        finally:

            session.close()

    # =========================================================================
    # UPDATE
    # =========================================================================

    def update_work_order(
        self,
        work_order_id,
        title,
        equipment_id,
        type_str,
        priority,
        technician_id=None,
        scheduled_date=None,
        description=None,
        parts_used=None,
        operator_id=None,
        failure_report_time=None,
        operator_notes=None,
        operator_signature=None,
        manual_cost=None,
        cost_description=None,
        deadline=None,
        additional_technician_ids=None,
        department_id=None,
        completion_personnel_ids=None,
    ):
        """
        Update a Work Order.

        New workflow:
            department is editable.
            Personnel is NOT selected during normal creation.

        For an existing completion-stage Work Order,
        completion_personnel_ids may be supplied to explicitly edit the
        actual Personnel who performed the work.

        If completion_personnel_ids is None, existing completion Personnel
        is preserved unchanged.
        """

        try:
            work_order_id = self._as_int(work_order_id, "شناسه دستور کار", allow_none=False)
            equipment_id = self._as_int(equipment_id, "شناسه تجهیز", allow_none=False)
            department_id = self._as_int(department_id, "شناسه دپارتمان", allow_none=False)
            scheduled_date = self._as_datetime(scheduled_date, "تاریخ برنامه‌ریزی", allow_none=False)
            failure_report_time = self._as_datetime(failure_report_time, "زمان اعلام خرابی")
            deadline = self._as_datetime(deadline, "مهلت انجام")
            if manual_cost is not None:
                manual_cost = float(manual_cost)
        except ValueError as exc:
            return False, str(exc)

        valid, message = (
            self._validate_creation(
                title=title,
                equipment_id=equipment_id,
                scheduled_date=scheduled_date,
                department_id=department_id,
            )
        )

        if not valid:
            return False, message

        session = self.Session()

        try:

            wo = (
                session.query(
                    WorkOrder
                )
                .filter(
                    WorkOrder.id
                    == work_order_id
                )
                .first()
            )

            if not wo:

                return (
                    False,
                    "دستور کار یافت نشد.",
                )

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
                    "دپارتمان انتخاب‌شده یافت نشد.",
                )

            if (
                title
                != wo.title
                or scheduled_date
                != wo.scheduled_date
                or equipment_id
                != wo.equipment_id
            ):

                if self.duplicate_exists(
                    equipment_id,
                    self._text(
                        title
                    ),
                    scheduled_date,
                    exclude_id=(
                        work_order_id
                    ),
                ):

                    return (
                        False,
                        (
                            "یک دستور کار دیگر با همین عنوان "
                            "و تاریخ برای این تجهیز وجود دارد."
                        ),
                    )

            type_name = (
                str(
                    type_str
                    or ""
                ).upper()
            )

            if (
                type_name
                in WorkOrderType.__members__
            ):

                wo_type = (
                    WorkOrderType[
                        type_name
                    ]
                )

            else:

                wo_type = (
                    WorkOrderType.CORRECTIVE
                )

            priority_name = (
                str(
                    priority
                    or ""
                ).upper()
            )

            if (
                priority_name
                in WorkOrderPriority.__members__
            ):

                wo_priority = (
                    WorkOrderPriority[
                        priority_name
                    ]
                )

            else:

                wo_priority = (
                    WorkOrderPriority.MEDIUM
                )

            wo.title = (
                self._text(
                    title
                )
            )

            wo.equipment_id = (
                equipment_id
            )

            wo.department_id = (
                department_id
            )

            wo.type = (
                wo_type.name
            )

            wo.priority = (
                wo_priority.name
            )

            # New workflow:
            # don't assign new User technicians.
            wo.technician_id = None

            wo.failure_report_time = (
                failure_report_time
            )

            wo.scheduled_date = (
                scheduled_date
            )

            if deadline is not None:

                wo.deadline = (
                    deadline
                )

            wo.description = (
                self._text(
                    description
                )
                or None
            )

            wo.parts_used = (
                self._text(
                    parts_used
                )
                or None
            )

            if manual_cost is not None:

                wo.manual_cost = (
                    manual_cost
                )

            if cost_description is not None:

                wo.cost_description = (
                    self._text(
                        cost_description
                    )
                    or None
                )

            wo.updated_at = (
                tehran_now()
            )

            # Legacy additional User technician assignments are only removed
            # when the caller explicitly supplies a new list.
            if (
                additional_technician_ids
                is not None
            ):

                session.execute(
                    work_order_technicians.delete()
                    .where(
                        work_order_technicians.c.work_order_id
                        == work_order_id
                    )
                )

                for user_id in (
                    additional_technician_ids
                    or []
                ):

                    if not user_id:
                        continue

                    session.execute(
                        work_order_technicians.insert().values(
                            work_order_id=(
                                work_order_id
                            ),
                            user_id=(
                                int(user_id)
                            ),
                        )
                    )

            # ------------------------------------------------------------
            # Completion Personnel — explicit edit only
            # ------------------------------------------------------------
            if completion_personnel_ids is not None:
                normalized_ids = self._normalize_personnel_ids(
                    personnel_ids=completion_personnel_ids
                )

                if not normalized_ids:
                    return (
                        False,
                        "برای ویرایش اطلاعات اتمام، حداقل یک پرسنل انجام‌دهنده انتخاب کنید.",
                    )

                status_name = str(
                    getattr(getattr(wo, "status", None), "name", None)
                    or getattr(getattr(wo, "status", None), "value", None)
                    or getattr(wo, "status", None)
                    or ""
                ).upper()

                if status_name not in {
                    "FINISH_REQUESTED",
                    "COMPLETED",
                    "APPROVED",
                } and getattr(wo, "end_time", None) is None:
                    return (
                        False,
                        "پرسنل انجام‌دهنده فقط برای دستور کارهای واردشده به مرحله اتمام قابل ویرایش است.",
                    )

                people = (
                    session.query(Personnel)
                    .filter(Personnel.id.in_(normalized_ids))
                    .all()
                )

                found_ids = {int(getattr(person, "id")) for person in people}
                missing_ids = [pid for pid in normalized_ids if pid not in found_ids]
                if missing_ids:
                    return (
                        False,
                        "یک یا چند پرسنل انتخاب‌شده در سیستم یافت نشد.",
                    )

                # Completion Personnel editing is intentionally organization-wide.
                # The Finish workflow may apply its own operational department
                # rule, but an existing completion record can be corrected from
                # the full Personnel list during administrative editing.

                # Preserve the canonical many-to-many completion storage.
                ordered_people = sorted(
                    people,
                    key=lambda person: normalized_ids.index(int(person.id)),
                )
                self._set_completion_personnel(wo, ordered_people)

            session.commit()

            try:

                log_action(
                    "UPDATE",
                    "work_order",
                    work_order_id,
                    (
                        f"عنوان: {title}, "
                        f"دپارتمان: {department_id}"
                    ),
                )

            except Exception:
                pass

            return (
                True,
                "دستور کار با موفقیت ویرایش شد.",
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                f"خطا در ویرایش دستور کار: {exc}",
            )

        finally:

            session.close()

    # =========================================================================
    # GET ALL
    # =========================================================================

    def get_all(
        self,
        status_filter=None,
        type_filter=None,
        technician_id=None,
        department_id=None,
        limit=None,
    ):
        """``limit`` (optional) returns only the newest N work orders."""

        session = self.Session()

        try:

            query = (
                session.query(
                    WorkOrder
                )
                .options(
                    joinedload(
                        WorkOrder.equipment
                    ),

                    joinedload(
                        WorkOrder.department
                    ),

                    joinedload(
                        WorkOrder.completers
                    ),

                    joinedload(
                        WorkOrder.technician
                    ),

                    joinedload(
                        WorkOrder.supervisor
                    ),

                    joinedload(
                        WorkOrder.operator
                    ),

                    joinedload(
                        WorkOrder.technicians
                    ),
                )
            )

            if status_filter:

                query = query.filter(
                    WorkOrder.status
                    == status_filter
                )

            if type_filter:

                query = query.filter(
                    WorkOrder.type
                    == type_filter
                )

            if technician_id is not None:

                query = query.filter(
                    (
                        WorkOrder.technician_id
                        == technician_id
                    )
                    |
                    (
                        WorkOrder.technician_id
                        .is_(None)
                    )
                )

            if department_id is not None:

                query = query.filter(
                    WorkOrder.department_id
                    == department_id
                )

            query = query.order_by(
                WorkOrder.created_at.desc()
            )
            if limit:
                query = query.limit(int(limit))
            results = query.all()

            session.expunge_all()

            return results

        finally:

            session.close()

    # =========================================================================
    # GET BY ID
    # =========================================================================

    def get_by_id(
        self,
        work_order_id,
    ):

        session = self.Session()

        try:

            wo = (
                session.query(
                    WorkOrder
                )
                .options(
                    joinedload(
                        WorkOrder.equipment
                    ),

                    joinedload(
                        WorkOrder.department
                    ),

                    joinedload(
                        WorkOrder.completers
                    ),

                    joinedload(
                        WorkOrder.technician
                    ),

                    joinedload(
                        WorkOrder.supervisor
                    ),

                    joinedload(
                        WorkOrder.operator
                    ),

                    joinedload(
                        WorkOrder.technicians
                    ),
                )
                .filter(
                    WorkOrder.id
                    == work_order_id
                )
                .first()
            )

            if wo:

                session.expunge(
                    wo
                )

            return wo

        finally:

            session.close()

    # =========================================================================
    # APPROVE CREATION
    # =========================================================================

    def approve_creation(
        self,
        work_order_id,
        supervisor_id,
    ):

        session = self.Session()

        try:

            wo = (
                session.query(
                    WorkOrder
                )
                .filter(
                    WorkOrder.id
                    == work_order_id
                )
                .first()
            )

            if not wo:

                return (
                    False,
                    "دستور کار یافت نشد.",
                )

            if (
                wo.status
                != WorkOrderStatus.PENDING_APPROVAL
            ):

                return (
                    False,
                    (
                        "فقط دستورکارهای "
                        "در انتظار تأیید قابل تأیید هستند."
                    ),
                )

            if not wo.department_id:

                return (
                    False,
                    (
                        "دپارتمان مسئول این "
                        "دستورکار مشخص نشده است."
                    ),
                )

            wo.status = (
                WorkOrderStatus.PENDING
            )

            wo.supervisor_id = (
                supervisor_id
            )

            session.commit()

            try:

                log_action(
                    "APPROVE_CREATION",
                    "work_order",
                    work_order_id,
                    "",
                )

            except Exception:
                pass

            return (
                True,
                "دستور کار تأیید و آماده شروع شد.",
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                str(exc),
            )

        finally:

            session.close()

    # =========================================================================
    # START WORK
    # =========================================================================

    def start_work(
        self,
        work_order_id,
    ):

        session = self.Session()

        try:

            wo = (
                session.query(
                    WorkOrder
                )
                .filter(
                    WorkOrder.id
                    == work_order_id
                )
                .first()
            )

            if not wo:

                return (
                    False,
                    "دستور کار یافت نشد.",
                )

            if (
                wo.status
                != WorkOrderStatus.PENDING
            ):

                return (
                    False,
                    (
                        "فقط دستورکارهای "
                        "در انتظار قابل شروع هستند."
                    ),
                )

            if not wo.department_id:

                return (
                    False,
                    (
                        "دپارتمان مسئول "
                        "مشخص نشده است."
                    ),
                )

            wo.status = (
                WorkOrderStatus.IN_PROGRESS
            )

            wo.start_time = (
                tehran_now()
            )

            session.commit()

            try:

                log_action(
                    "START",
                    "work_order",
                    work_order_id,
                    (
                        f"دپارتمان: "
                        f"{wo.department_id}"
                    ),
                )

            except Exception:
                pass

            return (
                True,
                "دستور کار شروع شد.",
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                str(exc),
            )

        finally:

            session.close()

    # =========================================================================
    # CHANGE STATUS / REOPEN EARLIER WORKFLOW STAGE
    # =========================================================================

    def change_status(
        self,
        work_order_id,
        target_status,
        changed_by_user_id=None,
        reason=None,
    ):
        """
        Reopen a Work Order at an earlier workflow stage.

        This is intentionally a *workflow* operation, not a raw status edit.
        Stage-dependent fields are synchronized with the selected target:

            PENDING_APPROVAL
                -> no start/end time, no completion Personnel

            PENDING
                -> no start/end time, no completion Personnel

            IN_PROGRESS
                -> start time preserved, end time cleared,
                   completion Personnel cleared

        Physical spare-part consumption is not reversed. It represents a real
        inventory movement already recorded in the stock transaction ledger.
        Its stored `parts_used` history is preserved, while later finish
        requests consume only any additional quantity.
        """
        try:
            work_order_id = self._as_int(
                work_order_id,
                "شناسه دستور کار",
                allow_none=False,
            )
        except ValueError as exc:
            return False, str(exc)

        try:
            if isinstance(target_status, WorkOrderStatus):
                target = target_status
            else:
                raw = str(target_status or "").strip()
                try:
                    target = WorkOrderStatus[raw]
                except Exception:
                    target = WorkOrderStatus(raw)
        except Exception:
            return False, "وضعیت مقصد نامعتبر است."

        session = self.Session()
        try:
            wo = (
                session.query(WorkOrder)
                .options(joinedload(WorkOrder.completers))
                .filter(WorkOrder.id == work_order_id)
                .first()
            )
            if not wo:
                return False, "دستور کار یافت نشد."

            current = self._coerce_status(wo.status)
            if current is None:
                return False, "وضعیت فعلی دستور کار نامعتبر است."

            allowed = self.backward_status_options(current)
            if target not in allowed:
                current_label = self.status_label(current)
                return (
                    False,
                    f"بازگردانی از وضعیت «{current_label}» به وضعیت انتخاب‌شده مجاز نیست.",
                )

            target_label = self.status_label(target)

            # Only clear data belonging to the later workflow stage.
            wo.end_time = None
            wo.delay_minutes = None
            wo.delay_reason = None
            wo.supervisor_notes = None
            self._clear_completion_personnel(wo)

            if target == WorkOrderStatus.PENDING_APPROVAL:
                # The approval gate is being reopened.
                wo.start_time = None
                wo.supervisor_id = None
            elif target == WorkOrderStatus.PENDING:
                # Work has not started yet.
                wo.start_time = None
                # Existing creation approval remains valid.
            elif target == WorkOrderStatus.IN_PROGRESS:
                # Keep the original start timestamp: the work is being
                # reopened in-progress rather than recreated from scratch.
                if not wo.start_time:
                    wo.start_time = tehran_now()

            wo.status = target
            wo.updated_at = tehran_now()

            session.commit()

            try:
                actor = ""
                if changed_by_user_id:
                    actor = f"user_id={changed_by_user_id}; "
                log_action(
                    "CHANGE_STATUS",
                    "work_order",
                    work_order_id,
                    (
                        f"{actor}"
                        f"from={self.status_label(current)}; "
                        f"to={target_label}; "
                        f"reason={self._text(reason) or 'بدون توضیح'}"
                    ),
                )
            except Exception:
                pass

            return (
                True,
                f"وضعیت دستور کار به «{target_label}» بازگردانده شد و گردش کار نیز همگام شد.",
            )

        except Exception as exc:
            session.rollback()
            return False, f"خطا در تغییر مرحله گردش کار: {exc}"
        finally:
            session.close()

    # =========================================================================
    # PERSONNEL FOR FINISH
    # =========================================================================

    def get_personnel_for_finish(
        self,
        work_order_id: int,
    ):
        """
        Return only Personnel belonging to the Work Order department.
        """

        session = self.Session()

        try:

            wo = (
                session.query(
                    WorkOrder
                )
                .options(
                    joinedload(
                        WorkOrder.department
                    )
                )
                .filter(
                    WorkOrder.id
                    == work_order_id
                )
                .first()
            )

            if not wo:
                return []

            if not wo.department_id:
                return []

            personnel = (
                session.query(
                    Personnel
                )
                .filter(
                    Personnel.department_id
                    == wo.department_id
                )
                .order_by(
                    Personnel.full_name.asc()
                )
                .all()
            )

            department_name = ""

            if wo.department:

                department_name = (
                    wo.department.name
                    or ""
                )

            return [
                self._personnel_dict(
                    person,
                    department_name,
                )
                for person in personnel
            ]

        finally:

            session.close()

    # =========================================================================
    # DEDUCT SPARE PARTS
    # =========================================================================

    def deduct_spare_parts(
        self,
        work_order_id: int,
        parts_list: list,
        session=None,
    ):
        """
        Consume spare parts for a Work Order.

        All parts are validated first and then deducted together, so a
        shortage on one part never leaves an earlier part half-deducted.
        When ``session`` is given the changes join that transaction and the
        caller commits; otherwise this method commits on its own.
        """

        if not parts_list:
            return (
                True,
                "قطعه‌ای برای مصرف ثبت نشده است.",
                [],
            )

        own_session = session is None
        if own_session:
            session = self.Session()

        try:
            # ---- 1) validate every line and merge duplicates
            wanted = {}
            for item in parts_list or []:
                if not isinstance(item, dict):
                    return False, "اطلاعات قطعه نامعتبر است.", []
                part_id = item.get("part_id")
                try:
                    qty = float(item.get("quantity"))
                except (TypeError, ValueError):
                    return False, f"مقدار قطعه {part_id} نامعتبر است.", []
                if qty <= 0:
                    return (
                        False,
                        f"مقدار قطعه {part_id} باید بیشتر از صفر باشد.",
                        [],
                    )
                if qty != int(qty):
                    return (
                        False,
                        f"مقدار قطعه {part_id} باید عدد صحیح باشد.",
                        [],
                    )
                try:
                    part_id = int(part_id)
                except (TypeError, ValueError):
                    return False, "اطلاعات قطعه نامعتبر است.", []
                wanted[part_id] = wanted.get(part_id, 0) + int(qty)

            # ---- 2) check stock for all parts before touching anything
            parts = {}
            for part_id, qty in wanted.items():
                part = (
                    session.query(SparePart)
                    .filter(SparePart.id == part_id)
                    .first()
                )
                if not part:
                    return False, f"قطعه با ID {part_id} یافت نشد.", []
                if (part.current_stock or 0) < qty:
                    return (
                        False,
                        (
                            f"موجودی قطعه {part.part_number} کافی نیست. "
                            f"موجودی: {part.current_stock}"
                        ),
                        [],
                    )
                parts[part_id] = part

            # ---- 3) deduct and write the stock ledger
            low_stock_parts = []
            for part_id, qty in wanted.items():
                part = parts[part_id]
                part.current_stock = (part.current_stock or 0) - qty
                session.add(
                    SparePartTransaction(
                        part_id=part.id,
                        transaction_type="OUT",
                        quantity=qty,
                        batch_price=None,
                        reference=str(work_order_id),
                        notes=f"مصرف در دستور کار {work_order_id}",
                    )
                )
                if part.current_stock <= (part.min_stock or 0):
                    low_stock_parts.append(part.part_number)

            if own_session:
                session.commit()

            return (
                True,
                "قطعات با موفقیت کسر شدند.",
                low_stock_parts,
            )

        except Exception as exc:
            if own_session:
                session.rollback()
            return (
                False,
                f"خطا در کسر قطعات: {exc}",
                [],
            )

        finally:
            if own_session:
                session.close()

    # =========================================================================
    # REQUEST FINISH
    # =========================================================================

    @staticmethod
    def _decode_parts_used(value):
        if not value:
            return {}
        try:
            raw = json.loads(value) if isinstance(value, str) else value
        except Exception:
            return {}
        if not isinstance(raw, list):
            return {}

        result = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                part_id = int(item.get("part_id"))
                qty = float(item.get("quantity") or 0)
            except (TypeError, ValueError):
                continue
            if part_id <= 0 or qty <= 0:
                continue
            result[part_id] = dict(item, part_id=part_id, quantity=qty)
        return result

    @classmethod
    def _parts_delta_and_merged(cls, existing_json, requested_items):
        """
        Compare new finish input with already consumed parts.

        Rollback does not reverse physical stock movement. Therefore, when the
        same Work Order is finished again, the previously consumed quantity is
        not deducted twice. Only newly increased quantities are consumed.
        """
        old = cls._decode_parts_used(existing_json)
        merged = {pid: dict(item) for pid, item in old.items()}
        delta = {}

        for item in requested_items or []:
            if not isinstance(item, dict):
                continue
            try:
                part_id = int(item.get("part_id"))
                qty = float(item.get("quantity") or 0)
            except (TypeError, ValueError):
                continue
            if part_id <= 0 or qty <= 0:
                continue

            previous = float(old.get(part_id, {}).get("quantity", 0) or 0)
            if qty > previous:
                delta[part_id] = dict(item, part_id=part_id, quantity=qty - previous)

            # Preserve the greatest consumed quantity ever recorded for this
            # Work Order/part. A rollback never fabricates stock back into the
            # warehouse.
            if qty >= previous or part_id not in merged:
                merged[part_id] = dict(item, part_id=part_id, quantity=max(previous, qty))

        merged_list = [merged[k] for k in sorted(merged)]
        delta_list = [delta[k] for k in sorted(delta)]
        return delta_list, merged_list

    def request_finish(
        self,
        work_order_id,
        personnel_id=None,
        technician_notes=None,
        used_parts_list=None,
        manual_cost=None,
        cost_description=None,
        end_time: datetime = None,
        delay_minutes=None,
        delay_reason=None,
        personnel_ids=None,
    ):
        """
        Submit a Work Order finish request.

        Personnel is REQUIRED.

        Personnel must belong to the exact Work Order department.

        The selected Personnel is stored in the
        work_order_completers association table through WorkOrder.completers.
        """

        normalized_personnel_ids = self._normalize_personnel_ids(
            personnel_ids=personnel_ids,
            personnel_id=personnel_id,
        )

        if not normalized_personnel_ids:
            return (
                False,
                (
                    "انتخاب حداقل یک پرسنل انجام‌دهنده "
                    "الزامی است."
                ),
            )

        session = self.Session()

        try:

            wo = (
                session.query(
                    WorkOrder
                )
                .options(
                    joinedload(
                        WorkOrder.department
                    ),
                    joinedload(
                        WorkOrder.completers
                    ),
                )
                .filter(
                    WorkOrder.id
                    == work_order_id
                )
                .first()
            )

            if not wo:

                return (
                    False,
                    "دستور کار یافت نشد.",
                )

            if (
                wo.status
                != WorkOrderStatus.IN_PROGRESS
            ):

                return (
                    False,
                    (
                        "فقط دستورکارهای "
                        "در حال انجام قابل ارسال هستند."
                    ),
                )

            if not wo.department_id:

                return (
                    False,
                    (
                        "دپارتمان مسئول این "
                        "دستورکار مشخص نشده است."
                    ),
                )

            # ------------------------------------------------------------
            # Personnel
            # ------------------------------------------------------------
            personnel = (
                session.query(Personnel)
                .filter(
                    Personnel.id.in_(
                        normalized_personnel_ids
                    )
                )
                .all()
            )

            personnel_by_id = {
                person.id: person
                for person in personnel
            }

            missing_ids = [
                pid
                for pid in normalized_personnel_ids
                if pid not in personnel_by_id
            ]

            if missing_ids:
                return (
                    False,
                    (
                        "برخی از پرسنل انتخاب‌شده یافت نشدند: "
                        + ", ".join(map(str, missing_ids))
                    ),
                )

            selected_personnel = [
                personnel_by_id[pid]
                for pid in normalized_personnel_ids
            ]

            wrong_department = [
                person
                for person in selected_personnel
                if person.department_id != wo.department_id
            ]

            if wrong_department:
                names = ", ".join(
                    person.full_name or str(person.id)
                    for person in wrong_department
                )
                return (
                    False,
                    (
                        "پرسنل زیر متعلق به دپارتمان این "
                        "دستورکار نیستند: "
                        f"{names}"
                    ),
                )

            # ------------------------------------------------------------
            # Finish time must not be before the start time
            # ------------------------------------------------------------

            if end_time and wo.start_time and end_time < wo.start_time:
                return (
                    False,
                    "زمان اتمام نمی‌تواند قبل از زمان شروع کار باشد.",
                )

            # ------------------------------------------------------------
            # Validate cost and delay BEFORE any stock movement
            # ------------------------------------------------------------

            if manual_cost is not None:
                try:
                    manual_cost = float(manual_cost)
                except (TypeError, ValueError):
                    return False, "هزینه واردشده نامعتبر است."
                if manual_cost < 0:
                    return False, "هزینه نمی‌تواند منفی باشد."

            if delay_minutes is not None:
                try:
                    delay_minutes = int(delay_minutes)
                except (TypeError, ValueError):
                    return False, "مقدار تأخیر نامعتبر است."
                if delay_minutes < 0:
                    return False, "مقدار تأخیر نمی‌تواند منفی باشد."

            # ------------------------------------------------------------
            # Spare parts (same transaction as the Work Order update)
            # ------------------------------------------------------------

            low_stock = []

            if used_parts_list:
                parts_to_consume, merged_parts = self._parts_delta_and_merged(
                    wo.parts_used,
                    used_parts_list,
                )

                if parts_to_consume:
                    success, msg, low_stock = self.deduct_spare_parts(
                        work_order_id,
                        parts_to_consume,
                        session=session,
                    )
                    if not success:
                        session.rollback()
                        return False, msg

                if merged_parts:
                    wo.parts_used = json.dumps(
                        merged_parts,
                        ensure_ascii=False,
                    )

            # ------------------------------------------------------------
            # Cost
            # ------------------------------------------------------------

            if manual_cost is not None:
                wo.manual_cost = manual_cost

            if cost_description:

                wo.cost_description = (
                    self._text(
                        cost_description
                    )
                    or None
                )

            # ------------------------------------------------------------
            # Finish notes
            # ------------------------------------------------------------

            if technician_notes:

                wo.description = (
                    self._text(
                        technician_notes
                    )
                )

            # ------------------------------------------------------------
            # Completion time
            # ------------------------------------------------------------

            if end_time:

                wo.end_time = (
                    end_time
                )

            else:

                wo.end_time = (
                    tehran_now()
                )

            # ------------------------------------------------------------
            # Delay (validated above)
            # ------------------------------------------------------------

            wo.delay_minutes = (
                delay_minutes
            )

            wo.delay_reason = (
                self._text(
                    delay_reason
                )
                or None
            )

            # ------------------------------------------------------------
            # ACTUAL PERSONNEL
            # ------------------------------------------------------------

            self._set_completion_personnel(
                wo,
                selected_personnel,
            )

            # ------------------------------------------------------------
            # Finish status
            # ------------------------------------------------------------

            wo.status = (
                WorkOrderStatus.FINISH_REQUESTED
            )

            wo.updated_at = (
                tehran_now()
            )

            session.commit()

            try:

                log_action(
                    "REQUEST_FINISH",
                    "work_order",
                    work_order_id,
                    (
                        f"personnel_ids: {normalized_personnel_ids}, "
                        f"personnel_names: "
                        f"{', '.join(p.full_name or '' for p in selected_personnel)}, "
                        f"department_id: "
                        f"{wo.department_id}, "
                        f"end_time: "
                        f"{wo.end_time}"
                    ),
                )

            except Exception:
                pass

            message = (
                "درخواست اتمام کار "
                "با موفقیت ارسال شد. "
                "منتظر تأیید مدیر باشید."
            )

            if low_stock:

                message += (
                    "\n⚠️ هشدار: قطعات "
                    + ", ".join(
                        low_stock
                    )
                    + " به حداقل موجودی رسیده‌اند."
                )

            return (
                True,
                message,
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                f"خطا در ثبت درخواست اتمام: {exc}",
            )

        finally:

            session.close()

    # =========================================================================
    # APPROVE FINISH
    # =========================================================================

    def approve(
        self,
        work_order_id,
        supervisor_id,
    ):

        session = self.Session()

        try:

            wo = (
                session.query(
                    WorkOrder
                )
                .options(
                    joinedload(
                        WorkOrder.department
                    ),

                    joinedload(
                        WorkOrder.completers
                    ),
                )
                .filter(
                    WorkOrder.id
                    == work_order_id
                )
                .first()
            )

            if not wo:

                return (
                    False,
                    "دستور کار یافت نشد.",
                )

            if (
                wo.status
                != WorkOrderStatus.FINISH_REQUESTED
            ):

                return (
                    False,
                    (
                        "فقط دستورکارهایی که "
                        "درخواست اتمام دارند "
                        "قابل تأیید هستند."
                    ),
                )

            if not wo.department_id:

                return (
                    False,
                    (
                        "دپارتمان دستورکار مشخص نشده است."
                    ),
                )

            # ------------------------------------------------------------
            # Completion Personnel
            # ------------------------------------------------------------
            personnel_list = self._get_completion_personnel(wo)

            if not personnel_list:
                return (
                    False,
                    (
                        "پرسنل انجام‌دهنده "
                        "مشخص نشده است."
                    ),
                )

            wrong_department = [
                person
                for person in personnel_list
                if person.department_id != wo.department_id
            ]

            if wrong_department:
                names = ", ".join(
                    person.full_name or str(person.id)
                    for person in wrong_department
                )
                return (
                    False,
                    (
                        "پرسنل انجام‌دهنده زیر متعلق "
                        "به دپارتمان این دستورکار نیستند: "
                        f"{names}"
                    ),
                )

            # ------------------------------------------------------------
            # Approve
            # ------------------------------------------------------------

            wo.status = (
                WorkOrderStatus.APPROVED
            )

            wo.supervisor_id = (
                supervisor_id
            )

            wo.updated_at = (
                tehran_now()
            )

            session.commit()

            # ------------------------------------------------------------
            # PM completion
            # ------------------------------------------------------------

            if wo.schedule_id:

                try:

                    from database.pm_repository import (
                        PMRepository,
                    )

                    pm_repo = PMRepository(
                        self.Session
                    )

                    pm_repo.update_after_completion(
                        wo.schedule_id,
                        wo.end_time
                        or tehran_now(),
                    )

                except Exception as exc:

                    print(
                        "PM completion update error:",
                        exc,
                    )

            try:

                log_action(
                    "APPROVE",
                    "work_order",
                    work_order_id,
                    (
                        f"personnel_ids: "
                        f"{[p.id for p in personnel_list]}, "
                        f"department_id: "
                        f"{wo.department_id}"
                    ),
                )

            except Exception:
                pass

            return (
                True,
                "دستور کار با موفقیت تأیید نهایی شد.",
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                str(exc),
            )

        finally:

            session.close()

    # =========================================================================
    # REJECT FINISH
    # =========================================================================

    def reject_finish(
        self,
        work_order_id,
        supervisor_id,
        notes,
    ):

        session = self.Session()

        try:

            wo = (
                session.query(
                    WorkOrder
                )
                .options(
                    joinedload(
                        WorkOrder.completers
                    )
                )
                .filter(
                    WorkOrder.id
                    == work_order_id
                )
                .first()
            )

            if not wo:

                return (
                    False,
                    "دستور کار یافت نشد.",
                )

            if (
                wo.status
                != WorkOrderStatus.FINISH_REQUESTED
            ):

                return (
                    False,
                    (
                        "فقط دستورکارهایی که "
                        "درخواست اتمام دارند "
                        "قابل رد هستند."
                    ),
                )

            wo.status = (
                WorkOrderStatus.REJECTED
            )

            wo.supervisor_id = (
                supervisor_id
            )

            wo.supervisor_notes = (
                self._text(
                    notes
                )
                or None
            )

            wo.updated_at = (
                tehran_now()
            )

            session.commit()

            success, new_id = (
                self._create_work_order_copy(
                    wo,
                    notes,
                )
            )

            if not success:

                return (
                    False,
                    (
                        "خطا در ایجاد "
                        "دستور کار جایگزین."
                    ),
                )

            try:

                log_action(
                    "REJECT_FINISH",
                    "work_order",
                    work_order_id,
                    (
                        f"نظر: {notes} - "
                        f"دستور کار جدید #{new_id}"
                    ),
                )

            except Exception:
                pass

            return (
                True,
                (
                    "درخواست اتمام رد شد. "
                    f"دستور کار جدید با شماره {new_id} "
                    "ایجاد شد."
                ),
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                str(exc),
            )

        finally:

            session.close()

    # =========================================================================
    # CREATE CORRECTIVE COPY
    # =========================================================================

    def _create_work_order_copy(
        self,
        original_wo,
        supervisor_notes,
    ):

        session = self.Session()

        try:

            if original_wo.root_parent_id:

                root_id = (
                    original_wo.root_parent_id
                )

            else:

                root_id = (
                    original_wo.id
                )

            base_title = (original_wo.title or "").strip()
            new_title = (
                base_title
                if base_title.endswith("(اصلاحی)")
                else f"{base_title} (اصلاحی)"
            )

            new_description = (
                "کار اصلاحی پس از رد درخواست اتمام:\n"
                f"{supervisor_notes or 'بدون توضیح'}\n\n"
                "شرح اصلی:\n"
                f"{original_wo.description or 'ندارد'}"
            )

            # The corrective copy gets a fresh deadline with the same
            # allowed duration as the original (at least one day), so it is
            # not counted as late from the moment it is created.
            new_scheduled = tehran_now() + timedelta(days=1)
            new_deadline = None
            if original_wo.deadline:
                allowed = timedelta(days=1)
                if original_wo.scheduled_date:
                    allowed = max(
                        allowed,
                        original_wo.deadline - original_wo.scheduled_date,
                    )
                new_deadline = new_scheduled + allowed

            new_wo = WorkOrder(
                equipment_id=(
                    original_wo.equipment_id
                ),

                schedule_id=(
                    original_wo.schedule_id
                ),

                department_id=(
                    original_wo.department_id
                ),

                parent_work_order_id=(
                    original_wo.id
                ),

                root_parent_id=(
                    root_id
                ),

                type=(
                    original_wo.type
                ),

                status=(
                    WorkOrderStatus.PENDING
                ),

                priority=(
                    original_wo.priority
                ),

                technician_id=None,

                title=new_title,

                description=new_description,

                scheduled_date=new_scheduled,

                deadline=new_deadline,

                created_at=(
                    tehran_now()
                ),

                manual_cost=0.0,
            )

            self._clear_completion_personnel(
                new_wo
            )

            session.add(
                new_wo
            )

            session.commit()

            session.refresh(
                new_wo
            )

            return (
                True,
                new_wo.id,
            )

        except Exception:

            session.rollback()

            return (
                False,
                None,
            )

        finally:

            session.close()

    # =========================================================================
    # DELETE
    # =========================================================================

    def delete(
        self,
        work_order_id,
    ):

        session = self.Session()

        try:

            wo = (
                session.query(
                    WorkOrder
                )
                .options(
                    joinedload(
                        WorkOrder.completers
                    )
                )
                .filter(
                    WorkOrder.id
                    == work_order_id
                )
                .first()
            )

            if not wo:

                return (
                    False,
                    "دستور کار یافت نشد.",
                )

            # ------------------------------------------------------------
            # Remove legacy User technician assignments.
            # ------------------------------------------------------------

            session.execute(
                work_order_technicians.delete()
                .where(
                    work_order_technicians.c.work_order_id
                    == work_order_id
                )
            )

            # ------------------------------------------------------------
            # Remove Personnel completion associations.
            #
            # Because work_order_completers uses an association table,
            # clearing the relationship removes only this Work Order's
            # completion associations.
            # ------------------------------------------------------------

            self._clear_completion_personnel(
                wo
            )

            session.delete(
                wo
            )

            session.commit()

            try:

                log_action(
                    "DELETE",
                    "work_order",
                    work_order_id,
                    "",
                )

            except Exception:
                pass

            return (
                True,
                "دستور کار حذف شد.",
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                str(exc),
            )

        finally:

            session.close()

    # =========================================================================
    # FIND BY PM SCHEDULE + DATE
    # =========================================================================

    def find_by_schedule_and_date(
        self,
        pm_schedule_id: int,
        scheduled_date: datetime,
    ) -> Optional[dict]:

        session = self.Session()

        try:

            wo = (
                session.query(
                    WorkOrder
                )
                .options(
                    joinedload(
                        WorkOrder.department
                    ),
                    joinedload(
                        WorkOrder.completers
                    ),
                )
                .filter(
                    WorkOrder.schedule_id
                    == pm_schedule_id,

                    WorkOrder.scheduled_date
                    == scheduled_date,
                )
                .first()
            )

            if not wo:
                return None

            personnel = (
                self._get_completion_personnel(
                    wo
                )
            )

            return {
                "id": (
                    wo.id
                ),

                "title": (
                    wo.title
                    or ""
                ),

                "status": (
                    wo.status.value
                    if wo.status
                    else ""
                ),

                "department_id": (
                    wo.department_id
                ),

                "completed_by_personnel_id": (
                    getattr(
                        personnel,
                        "id",
                        None,
                    )
                ),
            }

        finally:

            session.close()

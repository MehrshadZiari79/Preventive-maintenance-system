# database/pm_repository.py
"""
PM System - Preventive Maintenance Repository
==============================================

FINAL PM WORKFLOW
-----------------

PM CREATION / EDIT
------------------
A PM Schedule contains:

    - Title
    - Equipment
    - Department
    - Frequency
    - Interval
    - First Due Date
    - Checklist
    - Estimated Duration
    - Notes
    - Required Parts

No User technician is selected for a new PM.

The legacy technician_id column is intentionally preserved for
historical compatibility, but newly created/edited PM schedules
do not assign a User technician.

PM EXECUTION
------------
When a PM becomes due, the PM service can generate a Work Order.

The generated Work Order receives:

    PMSchedule.department_id
            ->
    WorkOrder.department_id

When the maintenance work is actually completed, the actual
Personnel is selected in the Work Order finish workflow.

The Work Order repository stores that Personnel in:

    completed_by_personnel_id

The PM schedule advances its next_due only after successful
completion/approval.

IMPORTANT
---------
This repository does NOT perform database migrations.

Existing PM data is preserved.
"""

from typing import (
    Optional,
)

from datetime import (
    datetime,
    timedelta,
)

from sqlalchemy.orm import (
    joinedload,
)

from sqlalchemy import (
    func,
    case,
    and_,
)


# case(): SQLAlchemy 1.4+/2.x take the WHEN tuples positionally; 2.x rejects
# the old list form that v2.3 used (every KPI query raised ArgumentError).
# Keep working on 1.3 too, just in case the build environment is older.
import sqlalchemy as _sa
from sqlalchemy import case as _sa_case

if tuple(int(x) for x in _sa.__version__.split(".")[:2]) < (1, 4):
    def case(*whens, **kw):
        return _sa_case(list(whens), **kw)
else:
    case = _sa_case

from database.models import (
    PMSchedule,
    Department,
)

from database.work_order import (
    WorkOrder,
)

from utils.logger import (
    log_action,
)
from utils.date_helpers import tehran_now  # Iranian (Asia/Tehran) clock


# ============================================================================
# REPOSITORY
# ============================================================================

class PMRepository:

    def __init__(
        self,
        session_factory,
    ):

        self.Session = (
            session_factory
        )

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
    def _frequency_value(
        frequency,
    ):

        if frequency is None:
            return ""

        value = getattr(
            frequency,
            "value",
            frequency,
        )

        return str(
            value
        ).strip()

    # -------------------------------------------------------------------------

    def _validate_department(
        self,
        session,
        department_id,
    ):

        if not department_id:

            return (
                False,
                "انتخاب دپارتمان مسئول الزامی است.",
                None,
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
                None,
            )

        return (
            True,
            "",
            department,
        )

    # =========================================================================
    # PM COMPLETION / NEXT DUE
    # =========================================================================

    def update_after_completion(
        self,
        schedule_id: int,
        completion_date: datetime,
    ):

        """
        Advance a PM after actual completion.

        This method is intentionally idempotent at the repository level:
        it only changes the selected PM schedule.

        Personnel is stored on the Work Order that represented the
        actual execution.
        """

        if not completion_date:

            raise ValueError(
                "تاریخ انجام PM مشخص نشده است."
            )

        session = self.Session()

        try:

            schedule = (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.id
                    == schedule_id
                )
                .first()
            )

            if not schedule:

                raise ValueError(
                    f"PM Schedule {schedule_id} not found"
                )

            interval_days = (
                getattr(
                    schedule,
                    "interval_days",
                    None,
                )
            )

            try:

                interval_days = int(
                    interval_days
                    or 0
                )

            except (
                TypeError,
                ValueError,
            ):

                interval_days = 0

            if interval_days <= 0:

                interval_days = 1

            schedule.last_done = (
                completion_date
            )

            schedule.next_due = (
                completion_date
                + timedelta(
                    days=interval_days
                )
            )

            if hasattr(
                schedule,
                "updated_at",
            ):

                schedule.updated_at = (
                    tehran_now()
                )

            session.commit()

            try:

                log_action(
                    "COMPLETE",
                    "pm_schedule",
                    schedule_id,
                    (
                        f"completion_date: "
                        f"{completion_date}"
                    ),
                )

            except Exception:
                pass

            return (
                self._to_dict(
                    schedule
                )
            )

        except Exception:

            session.rollback()

            raise

        finally:

            session.close()

    # =========================================================================
    # READ - ALL
    # =========================================================================

    def get_all(
        self,
    ) -> list[dict]:

        session = self.Session()

        try:

            options = [
                joinedload(
                    PMSchedule.equipment
                ),
            ]

            # -----------------------------------------------------------------
            # Legacy technician relationship
            # -----------------------------------------------------------------

            if hasattr(
                PMSchedule,
                "technician",
            ):

                options.append(
                    joinedload(
                        PMSchedule.technician
                    )
                )

            # -----------------------------------------------------------------
            # New department relationship
            # -----------------------------------------------------------------

            if hasattr(
                PMSchedule,
                "department",
            ):

                options.append(
                    joinedload(
                        PMSchedule.department
                    )
                )

            schedules = (
                session.query(
                    PMSchedule
                )
                .options(
                    *options
                )
                .order_by(
                    PMSchedule.next_due
                )
                .all()
            )

            return [
                self._to_dict(
                    schedule
                )
                for schedule in schedules
            ]

        finally:

            session.close()

    # =========================================================================
    # READ - BY ID
    # =========================================================================

    def get_by_id(
        self,
        schedule_id: int,
    ) -> Optional[dict]:

        session = self.Session()

        try:

            options = [
                joinedload(
                    PMSchedule.equipment
                ),
            ]

            if hasattr(
                PMSchedule,
                "technician",
            ):

                options.append(
                    joinedload(
                        PMSchedule.technician
                    )
                )

            if hasattr(
                PMSchedule,
                "department",
            ):

                options.append(
                    joinedload(
                        PMSchedule.department
                    )
                )

            schedule = (
                session.query(
                    PMSchedule
                )
                .options(
                    *options
                )
                .filter(
                    PMSchedule.id
                    == schedule_id
                )
                .first()
            )

            return (
                self._to_dict(
                    schedule
                )
                if schedule
                else None
            )

        finally:

            session.close()

    # =========================================================================
    # READ - BY EQUIPMENT
    # =========================================================================

    def get_by_equipment(
        self,
        equipment_id: int,
    ) -> list[dict]:

        session = self.Session()

        try:

            options = [
                joinedload(
                    PMSchedule.equipment
                ),
            ]

            if hasattr(
                PMSchedule,
                "technician",
            ):

                options.append(
                    joinedload(
                        PMSchedule.technician
                    )
                )

            if hasattr(
                PMSchedule,
                "department",
            ):

                options.append(
                    joinedload(
                        PMSchedule.department
                    )
                )

            schedules = (
                session.query(
                    PMSchedule
                )
                .options(
                    *options
                )
                .filter(
                    PMSchedule.equipment_id
                    == equipment_id
                )
                .order_by(
                    PMSchedule.next_due
                )
                .all()
            )

            return [
                self._to_dict(
                    schedule
                )
                for schedule in schedules
            ]

        finally:

            session.close()

    # =========================================================================
    # READ - OVERDUE
    # =========================================================================

    def get_overdue(
        self,
    ) -> list[dict]:

        session = self.Session()

        try:

            now = tehran_now()

            options = [
                joinedload(
                    PMSchedule.equipment
                ),
            ]

            if hasattr(
                PMSchedule,
                "technician",
            ):

                options.append(
                    joinedload(
                        PMSchedule.technician
                    )
                )

            if hasattr(
                PMSchedule,
                "department",
            ):

                options.append(
                    joinedload(
                        PMSchedule.department
                    )
                )

            schedules = (
                session.query(
                    PMSchedule
                )
                .options(
                    *options
                )
                .filter(
                    PMSchedule.next_due
                    <= now,

                    PMSchedule.is_active
                    == True,
                )
                .order_by(
                    PMSchedule.next_due
                )
                .all()
            )

            return [
                self._to_dict(
                    schedule
                )
                for schedule in schedules
            ]

        finally:

            session.close()

    # =========================================================================
    # READ - UPCOMING
    # =========================================================================

    def get_upcoming(
        self,
        days: int = 7,
    ) -> list[dict]:

        session = self.Session()

        try:

            now = tehran_now()

            future = (
                now
                + timedelta(
                    days=days
                )
            )

            options = [
                joinedload(
                    PMSchedule.equipment
                ),
            ]

            if hasattr(
                PMSchedule,
                "technician",
            ):

                options.append(
                    joinedload(
                        PMSchedule.technician
                    )
                )

            if hasattr(
                PMSchedule,
                "department",
            ):

                options.append(
                    joinedload(
                        PMSchedule.department
                    )
                )

            schedules = (
                session.query(
                    PMSchedule
                )
                .options(
                    *options
                )
                .filter(
                    PMSchedule.next_due
                    >= now,

                    PMSchedule.next_due
                    <= future,

                    PMSchedule.is_active
                    == True,
                )
                .order_by(
                    PMSchedule.next_due
                )
                .all()
            )

            return [
                self._to_dict(
                    schedule
                )
                for schedule in schedules
            ]

        finally:

            session.close()

    # =========================================================================
    # STATS
    # =========================================================================

    def get_stats(
        self,
    ) -> dict:

        session = self.Session()

        try:

            now = tehran_now()

            row = (
                session.query(

                    func.sum(
                        case(
                             
                                (
                                    PMSchedule.is_active
                                    == True,
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "total"
                    ),

                    func.sum(
                        case(
                             
                                (
                                    and_(
                                        PMSchedule.is_active
                                        == True,

                                        PMSchedule.next_due
                                        <= now,
                                    ),
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "overdue"
                    ),

                    func.sum(
                        case(
                             
                                (
                                    and_(
                                        PMSchedule.is_active
                                        == True,

                                        PMSchedule.next_due
                                        > now,

                                        PMSchedule.next_due
                                        <= (
                                            now
                                            + timedelta(
                                                days=7
                                            )
                                        ),
                                    ),
                                    1,
                                )
                             ,
                            else_=0,
                        )
                    ).label(
                        "upcoming"
                    ),
                )
                .one()
            )

            return {
                "total": (
                    row.total
                    or 0
                ),

                "overdue": (
                    row.overdue
                    or 0
                ),

                "upcoming": (
                    row.upcoming
                    or 0
                ),
            }

        finally:

            session.close()

    # =========================================================================
    # CREATE
    # =========================================================================

    def create(
        self,
        title: str,
        equipment_id: int,
        technician_id: Optional[int],
        frequency: str,
        interval_days: int,
        start_date: datetime,
        checklist: str,
        estimated_duration: Optional[int],
        notes: str,
        parts_required: Optional[str] = None,
        department_id: int = None,
    ) -> tuple[bool, str]:
        """
        Create a PM schedule.

        technician_id remains in the signature for compatibility,
        but is deliberately ignored for NEW PM records.

        department_id is mandatory.
        """

        # ---------------------------------------------------------------------
        # Required fields
        # ---------------------------------------------------------------------

        title = self._text(
            title
        )

        if not title:

            return (
                False,
                "عنوان برنامه PM الزامی است.",
            )

        if not equipment_id:

            return (
                False,
                "انتخاب تجهیز الزامی است.",
            )

        if not start_date:

            return (
                False,
                "تاریخ شروع / اولین سررسید الزامی است.",
            )

        if not department_id:

            return (
                False,
                "انتخاب دپارتمان مسئول الزامی است.",
            )

        frequency = (
            self._frequency_value(
                frequency
            )
        )

        if not frequency:

            return (
                False,
                "دوره تناوب PM الزامی است.",
            )

        try:

            interval_days = int(
                interval_days
            )

        except (
            TypeError,
            ValueError,
        ):

            return (
                False,
                "فاصله زمانی PM نامعتبر است.",
            )

        if interval_days <= 0:

            return (
                False,
                "فاصله زمانی PM باید بیشتر از صفر باشد.",
            )

        # ---------------------------------------------------------------------
        # Duplicate
        # ---------------------------------------------------------------------

        if self.duplicate_pm_exists(
            equipment_id,
            title,
            frequency,
        ):

            return (
                False,
                (
                    "یک برنامه PM مشابه "
                    "برای این تجهیز و دوره تناوب وجود دارد."
                ),
            )

        session = self.Session()

        try:

            # ---------------------------------------------------------------
            # Department
            # ---------------------------------------------------------------

            valid, message, department = (
                self._validate_department(
                    session,
                    department_id,
                )
            )

            if not valid:

                return (
                    False,
                    message,
                )

            # ---------------------------------------------------------------
            # PM schedule
            # ---------------------------------------------------------------

            schedule_kwargs = {
                "title": title,

                "equipment_id": (
                    equipment_id
                ),

                # New workflow:
                # no application User technician.
                "technician_id": None,

                "frequency": frequency,

                "interval_days": (
                    interval_days
                ),

                "last_done": None,

                "next_due": (
                    start_date
                ),

                "checklist": (
                    self._text(
                        checklist
                    )
                    or None
                ),

                "estimated_duration": (
                    estimated_duration
                    or None
                ),

                "is_active": True,

                "notes": (
                    self._text(
                        notes
                    )
                    or None
                ),

                "parts_required": (
                    self._text(
                        parts_required
                    )
                    or None
                ),
            }

            # ---------------------------------------------------------------
            # Department field
            #
            # The application model is being migrated separately.
            # Use the real ORM attribute when it exists.
            # ---------------------------------------------------------------

            if hasattr(
                PMSchedule,
                "department_id",
            ):

                schedule_kwargs[
                    "department_id"
                ] = department_id

            else:

                return (
                    False,
                    (
                        "مدل PMSchedule هنوز فیلد "
                        "دپارتمان را ندارد. "
                        "ابتدا کد مدل را به‌روزرسانی کنید."
                    ),
                )

            schedule = PMSchedule(
                **schedule_kwargs
            )

            session.add(
                schedule
            )

            session.commit()

            session.refresh(
                schedule
            )

            try:

                log_action(
                    "CREATE",
                    "pm_schedule",
                    schedule.id,
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
                "برنامه PM با موفقیت ثبت شد.",
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                f"خطای پایگاه داده: {exc}",
            )

        finally:

            session.close()

    # =========================================================================
    # UPDATE
    # =========================================================================

    def update(
        self,
        schedule_id: int,
        title: str,
        equipment_id: int,
        technician_id: Optional[int],
        frequency: str,
        interval_days: int,
        next_due: datetime,
        checklist: str,
        estimated_duration: Optional[int],
        notes: str,
        parts_required: Optional[str] = None,
        department_id: int = None,
    ) -> tuple[bool, str]:
        """
        Update a PM schedule.

        User technician remains unused.

        Department is required.
        """

        title = self._text(
            title
        )

        if not title:

            return (
                False,
                "عنوان برنامه PM الزامی است.",
            )

        if not equipment_id:

            return (
                False,
                "انتخاب تجهیز الزامی است.",
            )

        if not next_due:

            return (
                False,
                "تاریخ سررسید PM الزامی است.",
            )

        if not department_id:

            return (
                False,
                "انتخاب دپارتمان مسئول الزامی است.",
            )

        frequency = (
            self._frequency_value(
                frequency
            )
        )

        try:

            interval_days = int(
                interval_days
            )

        except (
            TypeError,
            ValueError,
        ):

            return (
                False,
                "فاصله زمانی PM نامعتبر است.",
            )

        if interval_days <= 0:

            return (
                False,
                "فاصله زمانی PM باید بیشتر از صفر باشد.",
            )

        if self.duplicate_pm_exists(
            equipment_id,
            title,
            frequency,
            exclude_id=schedule_id,
        ):

            return (
                False,
                (
                    "یک برنامه PM دیگر با همین عنوان "
                    "و دوره برای این تجهیز وجود دارد."
                ),
            )

        session = self.Session()

        try:

            schedule = (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.id
                    == schedule_id
                )
                .first()
            )

            if not schedule:

                return (
                    False,
                    "برنامه PM یافت نشد.",
                )

            valid, message, department = (
                self._validate_department(
                    session,
                    department_id,
                )
            )

            if not valid:

                return (
                    False,
                    message,
                )

            # ---------------------------------------------------------------
            # Update normal fields
            # ---------------------------------------------------------------

            schedule.title = title

            schedule.equipment_id = (
                equipment_id
            )

            # New workflow:
            schedule.technician_id = None

            schedule.frequency = (
                frequency
            )

            schedule.interval_days = (
                interval_days
            )

            schedule.next_due = (
                next_due
            )

            schedule.checklist = (
                self._text(
                    checklist
                )
                or None
            )

            schedule.estimated_duration = (
                estimated_duration
                or None
            )

            schedule.notes = (
                self._text(
                    notes
                )
                or None
            )

            schedule.parts_required = (
                self._text(
                    parts_required
                )
                or None
            )

            # ---------------------------------------------------------------
            # Department
            # ---------------------------------------------------------------

            if hasattr(
                PMSchedule,
                "department_id",
            ):

                schedule.department_id = (
                    department_id
                )

            else:

                return (
                    False,
                    (
                        "مدل PMSchedule هنوز فیلد "
                        "دپارتمان را ندارد."
                    ),
                )

            if hasattr(
                schedule,
                "updated_at",
            ):

                schedule.updated_at = (
                    tehran_now()
                )

            session.commit()

            try:

                log_action(
                    "UPDATE",
                    "pm_schedule",
                    schedule_id,
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
                "برنامه PM با موفقیت بروزرسانی شد.",
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                f"خطای پایگاه داده: {exc}",
            )

        finally:

            session.close()

    # =========================================================================
    # MARK DONE - LEGACY SAFE METHOD
    # =========================================================================

    def mark_done(
        self,
        schedule_id: int,
        done_date: datetime,
    ) -> tuple[bool, str]:
        """
        Legacy direct PM completion method.

        Kept for compatibility with old callers.

        IMPORTANT:
        New UI workflow should NOT use this method to select Personnel.
        Personnel belongs to the actual Work Order completion process.

        This method only advances the PM schedule.
        """

        if not done_date:

            return (
                False,
                "تاریخ انجام PM مشخص نشده است.",
            )

        session = self.Session()

        try:

            schedule = (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.id
                    == schedule_id
                )
                .first()
            )

            if not schedule:

                return (
                    False,
                    "برنامه PM یافت نشد.",
                )

            interval_days = (
                getattr(
                    schedule,
                    "interval_days",
                    0,
                )
                or 0
            )

            try:

                interval_days = int(
                    interval_days
                )

            except (
                TypeError,
                ValueError,
            ):

                interval_days = 0

            if interval_days <= 0:

                interval_days = 1

            schedule.last_done = (
                done_date
            )

            schedule.next_due = (
                done_date
                + timedelta(
                    days=interval_days
                )
            )

            if hasattr(
                schedule,
                "updated_at",
            ):

                schedule.updated_at = (
                    tehran_now()
                )

            session.commit()

            try:

                log_action(
                    "MARK_DONE",
                    "pm_schedule",
                    schedule_id,
                    (
                        f"done date: "
                        f"{done_date}"
                    ),
                )

            except Exception:
                pass

            return (
                True,
                (
                    "PM انجام‌شده ثبت شد "
                    "و تاریخ بعدی محاسبه گردید."
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

    # =========================================================================
    # TOGGLE ACTIVE
    # =========================================================================

    def toggle_active(
        self,
        schedule_id: int,
    ) -> tuple[bool, str]:

        session = self.Session()

        try:

            schedule = (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.id
                    == schedule_id
                )
                .first()
            )

            if not schedule:

                return (
                    False,
                    "برنامه PM یافت نشد.",
                )

            schedule.is_active = (
                not schedule.is_active
            )

            if hasattr(
                schedule,
                "updated_at",
            ):

                schedule.updated_at = (
                    tehran_now()
                )

            session.commit()

            state = (
                "فعال"
                if schedule.is_active
                else "غیرفعال"
            )

            try:

                log_action(
                    "TOGGLE",
                    "pm_schedule",
                    schedule_id,
                    (
                        f"active: "
                        f"{schedule.is_active}"
                    ),
                )

            except Exception:
                pass

            return (
                True,
                f"برنامه {state} شد.",
            )

        except Exception as exc:

            session.rollback()

            return (
                False,
                f"خطای پایگاه داده: {exc}",
            )

        finally:

            session.close()

    # =========================================================================
    # DELETE
    # =========================================================================

    def delete(
        self,
        schedule_id: int,
    ) -> tuple[bool, str]:

        session = self.Session()

        try:

            schedule = (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.id
                    == schedule_id
                )
                .first()
            )

            if not schedule:

                return (
                    False,
                    "برنامه PM یافت نشد.",
                )

            # ------------------------------------------------------------
            # Preserve Work Orders.
            #
            # They remain historical records and simply lose their
            # PM schedule link.
            # ------------------------------------------------------------

            session.query(
                WorkOrder
            ).filter(
                WorkOrder.schedule_id
                == schedule_id
            ).update(
                {
                    WorkOrder.schedule_id:
                    None
                },
                synchronize_session=False,
            )

            session.delete(
                schedule
            )

            session.commit()

            try:

                log_action(
                    "DELETE",
                    "pm_schedule",
                    schedule_id,
                    "",
                )

            except Exception:
                pass

            return (
                True,
                (
                    "برنامه PM و ارتباطات آن "
                    "با موفقیت حذف شد."
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

    # =========================================================================
    # DUPLICATE CHECK
    # =========================================================================

    def duplicate_pm_exists(
        self,
        equipment_id: int,
        title: str,
        frequency: str,
        exclude_id: int = None,
    ) -> bool:

        session = self.Session()

        try:

            frequency = (
                self._frequency_value(
                    frequency
                )
            )

            query = (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.equipment_id
                    == equipment_id,

                    PMSchedule.title
                    == title,

                    PMSchedule.frequency
                    == frequency,
                )
            )

            if exclude_id:

                query = query.filter(
                    PMSchedule.id
                    != exclude_id
                )

            return (
                query.first()
                is not None
            )

        finally:

            session.close()

    # =========================================================================
    # TO DICT
    # =========================================================================

    @staticmethod
    def _to_dict(
        schedule: PMSchedule,
    ) -> dict:

        if schedule is None:

            return {}

        now = tehran_now()

        next_due = getattr(
            schedule,
            "next_due",
            None,
        )

        is_active = bool(
            getattr(
                schedule,
                "is_active",
                False,
            )
        )

        is_overdue = (
            next_due is not None
            and next_due <= now
            and is_active
        )

        days_until = None

        if next_due:

            try:

                days_until = (
                    next_due.date()
                    - now.date()
                ).days

            except Exception:

                days_until = None

        # ---------------------------------------------------------------------
        # Legacy technician information
        # ---------------------------------------------------------------------

        technician_id = getattr(
            schedule,
            "technician_id",
            None,
        )

        technician = getattr(
            schedule,
            "technician",
            None,
        )

        technician_name = (
            getattr(
                technician,
                "full_name",
                None,
            )
            or "تعیین نشده"
        )

        # ---------------------------------------------------------------------
        # New Department information
        # ---------------------------------------------------------------------

        department_id = getattr(
            schedule,
            "department_id",
            None,
        )

        department = getattr(
            schedule,
            "department",
            None,
        )

        department_name = (
            getattr(
                department,
                "name",
                None,
            )
            or "تعیین نشده"
        )

        return {
            "id": (
                schedule.id
            ),

            "title": (
                schedule.title
            ),

            "equipment_id": (
                schedule.equipment_id
            ),

            "equipment_name": (
                schedule.equipment.name
                if schedule.equipment
                else ""
            ),

            "equipment_code": (
                schedule.equipment.code
                if schedule.equipment
                else ""
            ),

            # for the PM page filters (equipment category / location)
            "equipment_category": (
                (schedule.equipment.category or "")
                if schedule.equipment
                else ""
            ),

            "equipment_location": (
                (schedule.equipment.location or "")
                if schedule.equipment
                else ""
            ),

            # Legacy compatibility.
            # New records should have None.
            "technician_id": (
                technician_id
            ),

            "technician_name": (
                technician_name
            ),

            # New workflow.
            "department_id": (
                department_id
            ),

            "department_name": (
                department_name
            ),

            "frequency": (
                schedule.frequency
            ),

            "interval_days": (
                schedule.interval_days
            ),

            "last_done": (
                schedule.last_done.strftime(
                    "%Y-%m-%d"
                )
                if schedule.last_done
                else "انجام نشده"
            ),

            "next_due": (
                next_due.strftime(
                    "%Y-%m-%d"
                )
                if next_due
                else ""
            ),

            "next_due_dt": (
                next_due
            ),

            "checklist": (
                schedule.checklist
                or ""
            ),

            "estimated_duration": (
                schedule.estimated_duration
                or 0
            ),

            "is_active": (
                schedule.is_active
            ),

            "is_overdue": (
                is_overdue
            ),

            "days_until": (
                days_until
            ),

            "notes": (
                schedule.notes
                or ""
            ),

            "parts_required": (
                schedule.parts_required
                or ""
            ),

            "created_at": (
                schedule.created_at.strftime(
                    "%Y-%m-%d"
                )
                if schedule.created_at
                else ""
            ),
        }

    # =========================================================================
    # DUE SCHEDULES
    # =========================================================================

    def get_due_schedules(
        self,
        target_date: datetime,
    ) -> list:

        session = self.Session()

        try:

            schedules = (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.is_active
                    == True,

                    PMSchedule.next_due
                    <= target_date,
                )
                .all()
            )

            return schedules

        finally:

            session.close()

    # =========================================================================
    # DUE SCHEDULES AHEAD
    # =========================================================================

    def get_due_schedules_ahead(
        self,
        target_date: datetime,
        days_ahead: int = 1,
    ) -> list:

        session = self.Session()

        try:

            cutoff = (
                target_date
                + timedelta(
                    days=days_ahead
                )
            )

            schedules = (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.is_active
                    == True,

                    PMSchedule.next_due
                    <= cutoff,
                )
                .all()
            )

            return schedules

        finally:

            session.close()

    # =========================================================================
    # UPDATE NEXT DUE DATE
    # =========================================================================

    def update_next_due_date(
        self,
        pm_id: int,
        completion_date: datetime,
    ) -> tuple[bool, str]:

        try:

            self.update_after_completion(
                pm_id,
                completion_date,
            )

            return (
                True,
                "تاریخ سررسید بعدی به‌روزرسانی شد.",
            )

        except ValueError as exc:

            return (
                False,
                str(exc),
            )

        except Exception as exc:

            return (
                False,
                f"خطا: {exc}",
            )

    # =========================================================================
    # UPCOMING PMS
    # =========================================================================

    def get_upcoming_pms(
        self,
        days=7,
    ):

        session = self.Session()

        try:

            now = tehran_now()

            future = (
                now
                + timedelta(
                    days=days
                )
            )

            return (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.is_active
                    == True,

                    PMSchedule.next_due
                    >= now,

                    PMSchedule.next_due
                    <= future,
                )
                .order_by(
                    PMSchedule.next_due
                )
                .all()
            )

        finally:

            session.close()

    # =========================================================================
    # UPCOMING PMS DICTIONARIES
    # =========================================================================

    def get_upcoming_pms_dict(
        self,
        days=7,
    ):

        session = self.Session()

        try:

            now = tehran_now()

            future = (
                now
                + timedelta(
                    days=days
                )
            )

            options = [
                joinedload(
                    PMSchedule.equipment
                ),
            ]

            if hasattr(
                PMSchedule,
                "technician",
            ):

                options.append(
                    joinedload(
                        PMSchedule.technician
                    )
                )

            if hasattr(
                PMSchedule,
                "department",
            ):

                options.append(
                    joinedload(
                        PMSchedule.department
                    )
                )

            schedules = (
                session.query(
                    PMSchedule
                )
                .options(
                    *options
                )
                .filter(
                    PMSchedule.is_active
                    == True,

                    PMSchedule.next_due
                    >= now,

                    PMSchedule.next_due
                    <= future,
                )
                .order_by(
                    PMSchedule.next_due
                )
                .all()
            )

            return [
                self._to_dict(
                    schedule
                )
                for schedule in schedules
            ]

        finally:

            session.close()

    # =========================================================================
    # OVERDUE COUNT
    # =========================================================================

    def get_overdue_count(
        self,
    ) -> int:

        session = self.Session()

        try:

            return (
                session.query(
                    PMSchedule
                )
                .filter(
                    PMSchedule.is_active
                    == True,

                    PMSchedule.next_due
                    < tehran_now(),
                )
                .count()
            )

        finally:

            session.close()
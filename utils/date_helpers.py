# utils/date_helpers.py
"""
Iranian date/time helpers - the single source of "now" for the application.

Why not ``datetime.now()``?
    Many client PCs run old Windows builds whose "Iran Standard Time" rule
    still applies daylight saving (Iran abolished DST in 2022).  On those PCs
    ``datetime.now()`` is one hour wrong for half of the year.  Here the real
    UTC clock is converted to Asia/Tehran with the bundled IANA tz database
    (no DST since 1401), with a fixed +03:30 fallback.

All values returned are NAIVE datetimes in Tehran local time, which is what
the database columns already hold for work orders, repair requests, PM
schedules, production logs, etc.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import jdatetime

try:  # bundled with the frozen build through the tzdata package
    from zoneinfo import ZoneInfo
    _TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:  # pragma: no cover - fallback when tzdata is missing
    _TEHRAN = timezone(timedelta(hours=3, minutes=30), "IRST")

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

WEEKDAYS_FA = ("شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه")
MONTHS_FA = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)


# ---------------------------------------------------------------------------
# "now"
# ---------------------------------------------------------------------------

def tehran_now() -> datetime:
    """Current Tehran wall-clock time as a naive datetime."""
    return datetime.now(timezone.utc).astimezone(_TEHRAN).replace(tzinfo=None)


def tehran_today() -> date:
    """Today's (Gregorian) date in Tehran."""
    return tehran_now().date()


def utc_to_tehran(dt):
    """Convert a naive UTC datetime (legacy columns) to naive Tehran time."""
    if dt is None or not isinstance(dt, datetime):
        return dt
    return dt.replace(tzinfo=timezone.utc).astimezone(_TEHRAN).replace(tzinfo=None)


def jalali_month_start(day: date | None = None) -> date:
    """Gregorian date of the 1st of the current Jalali month."""
    day = day or tehran_today()
    j = jdatetime.date.fromgregorian(date=day)
    return jdatetime.date(j.year, j.month, 1).togregorian()


def jalali_year_start(day: date | None = None) -> date:
    day = day or tehran_today()
    j = jdatetime.date.fromgregorian(date=day)
    return jdatetime.date(j.year, 1, 1).togregorian()


# ---------------------------------------------------------------------------
# formatting
# ---------------------------------------------------------------------------

def to_jalali_date_str(dt, format_str='%Y-%m-%d'):
    """
    Convert a Gregorian datetime/date to a Jalali date string.
    Returns '—' if dt is None.
    """
    if dt is None:
        return '—'
    if isinstance(dt, datetime):
        dt = dt.date()
    try:
        jd = jdatetime.date.fromgregorian(date=dt)
        return jd.strftime(format_str)
    except Exception:
        return '—'


_GREGORIAN_IN_TEXT = None


def jalalize_text_dates(text):
    """
    Replace Gregorian dates written inside a text (``2026-10-21`` or
    ``2026/10/21``, optionally followed by a time) with the Jalali date in
    the same layout (``1405-07-29``).  Used for titles that older versions
    stored with a Gregorian date, e.g. «[A-PM] سرویس ... 2026-10-21».
    Anything that is not a real Gregorian date (1900-2100) is left as is.
    """
    global _GREGORIAN_IN_TEXT
    if not text or not isinstance(text, str):
        return text
    if _GREGORIAN_IN_TEXT is None:
        import re
        _GREGORIAN_IN_TEXT = re.compile(
            r"(?<![0-9])((?:19|20)[0-9]{2})([-/])([0-9]{1,2})\2([0-9]{1,2})(?![0-9])"
        )

    def _swap(match):
        try:
            g = date(int(match.group(1)), int(match.group(3)), int(match.group(4)))
            sep = match.group(2)
            return jdatetime.date.fromgregorian(date=g).strftime(f"%Y{sep}%m{sep}%d")
        except Exception:
            return match.group(0)

    return _GREGORIAN_IN_TEXT.sub(_swap, text)


def jalali_stamp(with_seconds: bool = True) -> str:
    """Jalali timestamp for file names, e.g. 14050803_161200 (Tehran time)."""
    now = tehran_now()
    j = jdatetime.datetime.fromgregorian(datetime=now)
    return j.strftime("%Y%m%d_%H%M%S" if with_seconds else "%Y%m%d_%H%M")


def to_jalali_datetime_str(dt, date_format='%Y-%m-%d', time_format='%H:%M'):
    """
    Convert a Gregorian datetime to a Jalali date + time string.
    If dt is a date (no time), only the date part is returned.
    Returns '—' if dt is None.
    """
    if dt is None:
        return '—'
    date_part = to_jalali_date_str(dt, date_format)
    if isinstance(dt, datetime):
        time_part = dt.strftime(time_format)
        return f"{date_part} {time_part}"
    return date_part


def jalali_weekday_name(day: date) -> str:
    """Persian weekday name (شنبه = first day of the week)."""
    return WEEKDAYS_FA[(day.weekday() + 2) % 7]


def now_tehran_jalali_text(persian_digits: bool = True) -> str:
    """e.g. 'شنبه ۱۸ مهر ۱۴۰۵  ·  ۱۵:۴۲:۰۷' - used by the live clocks."""
    now = tehran_now()
    j = jdatetime.date.fromgregorian(date=now.date())
    text = (
        f"{jalali_weekday_name(now.date())} {j.day} {MONTHS_FA[j.month - 1]} {j.year}"
        f"  ·  {now:%H:%M:%S}"
    )
    return text.translate(_FA_DIGITS) if persian_digits else text

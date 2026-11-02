# services/machine_time.py
"""
Pure time calculations for the machine-hours shift log (no UI, no database).

Standard OEE time model for one shift of one machine:

    window              = finish - start              (night shift: finish < start)
    planned production  = window - planned stops      (CIP, planned maintenance, breaks, no plan)
    run time            = planned production - unplanned stops (breakdowns, material, ...)
    availability        = run time / planned production
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from utils.theme import latin_digits

DAY_MIN = 24 * 60


def parse_clock(text):
    """'8', '8:30', '08.30', '۸:۳۰', '24:00' -> minutes after midnight; '' -> None; bad -> ValueError."""
    t = latin_digits(text).replace(".", ":").replace("/", ":")
    if not t:
        return None
    parts = t.split(":")
    if len(parts) > 2 or not all(p.isdigit() for p in parts if p != "") or parts[0] == "":
        raise ValueError(text)
    h = int(parts[0])
    m = int(parts[1]) if len(parts) == 2 and parts[1] != "" else 0
    if not (0 <= m <= 59) or not (0 <= h <= 24) or (h == 24 and m):
        raise ValueError(text)
    return h * 60 + m


def fmt_clock(minutes):
    if minutes is None:
        return ""
    minutes = int(minutes) % DAY_MIN
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def fmt_hm(minutes):
    """125 -> '2:05' (hours:minutes), used for durations."""
    if minutes is None:
        return ""
    minutes = int(round(minutes))
    sign = "-" if minutes < 0 else ""
    minutes = abs(minutes)
    return f"{sign}{minutes // 60}:{minutes % 60:02d}"


def window_minutes(start_min, end_min):
    """Length of the run window; a finish at/before the start is the next day."""
    diff = end_min - start_min
    if diff <= 0:
        diff += DAY_MIN
    return diff


def offset_in_window(start_min, clock_min, is_end=False):
    """Minutes from shift start to a clock time (wrapping past midnight)."""
    off = (clock_min - start_min) % DAY_MIN
    if is_end and off == 0:
        off = DAY_MIN
    return off


def compute_shift(start_min, end_min, events, planned_lookup):
    """
    events: [(from_clock_min, to_clock_min, category_code), ...]
    planned_lookup: {category_code: bool}

    Returns dict(window, planned_stop, unplanned_stop, planned_production,
    run, availability(%) or None, errors[list of str]).
    """
    errors = []
    if start_min is None or end_min is None:
        return {"window": None, "planned_stop": 0, "unplanned_stop": 0,
                "planned_production": None, "run": None, "availability": None,
                "errors": errors}

    window = window_minutes(start_min, end_min)
    spans = []
    planned = unplanned = 0
    for i, (f, t, cat) in enumerate(events, start=1):
        a = offset_in_window(start_min, f)
        b = offset_in_window(start_min, t, is_end=True)
        if b <= a:
            errors.append(f"توقف {i}: «تا» باید بعد از «از» باشد.")
            continue
        if b > window:
            errors.append(f"توقف {i}: خارج از ساعت شروع تا پایان کار است.")
            continue
        for (x, y, j) in spans:
            if a < y and x < b:
                errors.append(f"توقف {i} با توقف {j} هم‌پوشانی دارد.")
                break
        spans.append((a, b, i))
        if planned_lookup.get(cat, False):
            planned += b - a
        else:
            unplanned += b - a

    planned_production = window - planned
    run = planned_production - unplanned
    availability = (run / planned_production * 100.0) if planned_production > 0 else None
    return {"window": window, "planned_stop": planned, "unplanned_stop": unplanned,
            "planned_production": planned_production, "run": run,
            "availability": availability, "errors": errors}


def to_datetime(day, start_min, clock_min, is_end=False):
    """Absolute datetime of a clock time inside the shift that starts on ``day``."""
    base = datetime.combine(day, time()) + timedelta(minutes=start_min)
    return base + timedelta(minutes=offset_in_window(start_min, clock_min, is_end))


def clock_of(dt):
    return None if dt is None else dt.hour * 60 + dt.minute

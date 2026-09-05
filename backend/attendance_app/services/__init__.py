"""Public attendance domain operations. HTTP views must not duplicate these rules."""

from .errors import PunchError
from .finalization import finalize_attendance
from .punches import process_punch
from .schedules import (
    holiday_for,
    is_scheduled,
    record_state,
    resolve_clock_in_date,
    scheduled_bounds,
)

__all__ = [
    "PunchError",
    "finalize_attendance",
    "process_punch",
    "holiday_for",
    "is_scheduled",
    "record_state",
    "resolve_clock_in_date",
    "scheduled_bounds",
]

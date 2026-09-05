"""Idempotent finalization, serialized with punches and administrator changes."""

from datetime import date

from core.models import Employee
from django.db import transaction
from django.utils import timezone

from attendance_app.models import AdminException, AttendanceRecord

from .schedules import holiday_for, is_scheduled, scheduled_bounds


def finalize_attendance(work_date: date, *, now=None):
    now = now or timezone.now()
    counts = {"absent_created": 0, "excused_created": 0, "missing_clock_out": 0, "skipped": 0}
    employee_ids = Employee.objects.filter(
        is_active=True, user__is_active=True, work_site__is_active=True, shift__is_active=True
    ).values_list("pk", flat=True)
    for employee_id in employee_ids:
        with transaction.atomic():
            employee = (
                Employee.objects.select_for_update(of=("self",))
                .select_related("user", "work_site", "shift")
                .get(pk=employee_id)
            )
            start, end = scheduled_bounds(employee, work_date)
            if (
                not is_scheduled(employee, work_date)
                or holiday_for(employee, work_date)
                or end > now
            ):
                counts["skipped"] += 1
                continue
            excused = AdminException.objects.filter(employee=employee, date=work_date).exists()
            record, created = AttendanceRecord.objects.get_or_create(
                employee=employee,
                work_date=work_date,
                defaults={
                    "site": employee.work_site,
                    "shift": employee.shift,
                    "scheduled_start": start,
                    "scheduled_end": end,
                    "grace_minutes": employee.shift.grace_minutes,
                    "state": AttendanceRecord.State.EXCUSED
                    if excused
                    else AttendanceRecord.State.ABSENT,
                },
            )
            if created:
                counts["excused_created" if excused else "absent_created"] += 1
            elif record.clock_in and not record.clock_out and not record.missing_clock_out:
                record.missing_clock_out = True
                record.save(update_fields=["missing_clock_out", "updated_at"])
                counts["missing_clock_out"] += 1
    return counts

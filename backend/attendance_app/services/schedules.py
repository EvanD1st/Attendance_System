from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from core.models import Employee, Holiday

from attendance_app.models import AttendanceRecord


def site_timezone(site):
    return ZoneInfo(site.timezone)


def scheduled_bounds(employee: Employee, work_date: date):
    zone = site_timezone(employee.work_site)
    start = datetime.combine(work_date, employee.shift.start_time, tzinfo=zone)
    end_date = (
        work_date + timedelta(days=1)
        if employee.shift.end_time <= employee.shift.start_time
        else work_date
    )
    end = datetime.combine(end_date, employee.shift.end_time, tzinfo=zone)
    return start, end


def is_scheduled(employee: Employee, work_date: date):
    return work_date.weekday() in employee.shift.working_weekdays


def holiday_for(employee: Employee, work_date: date):
    return (
        Holiday.objects.filter(date=work_date).filter(site__isnull=True).first()
        or Holiday.objects.filter(date=work_date, site=employee.work_site).first()
    )


def resolve_clock_in_date(employee: Employee, now):
    local_now = now.astimezone(site_timezone(employee.work_site))
    shift = employee.shift
    if shift.end_time <= shift.start_time and local_now.time() <= shift.end_time:
        previous = local_now.date() - timedelta(days=1)
        if is_scheduled(employee, previous):
            return previous
    return local_now.date()


def record_state(clock_in, scheduled_start, grace_minutes):
    if not clock_in:
        return AttendanceRecord.State.ABSENT
    threshold = scheduled_start + timedelta(minutes=grace_minutes)
    return AttendanceRecord.State.PRESENT if clock_in <= threshold else AttendanceRecord.State.LATE

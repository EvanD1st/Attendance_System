from datetime import timedelta
from decimal import Decimal
from time import sleep

from core.models import Employee
from django.conf import settings
from django.db import IntegrityError, OperationalError, connection, transaction
from django.utils import timezone

from attendance_app.models import AdminException, AttendanceAttempt, AttendanceRecord

from .errors import PunchError
from .geofence import haversine_meters
from .qr import parse_qr
from .schedules import (
    holiday_for,
    is_scheduled,
    record_state,
    resolve_clock_in_date,
    scheduled_bounds,
)


def _attempt_defaults(
    employee,
    action,
    payload,
    *,
    kiosk=None,
    site=None,
    distance=None,
    accepted=False,
    code="",
    detail="",
    record=None,
):
    return {
        "employee": employee,
        "action": action,
        "kiosk": kiosk,
        "site": site,
        "record": record,
        "latitude": payload["latitude"],
        "longitude": payload["longitude"],
        "accuracy_meters": payload["accuracy_meters"],
        "captured_at": payload["captured_at"],
        "distance_meters": Decimal(str(round(distance, 2))) if distance is not None else None,
        "accepted": accepted,
        "reason_code": code,
        "reason_detail": detail[:240],
    }


def log_rejection(employee, action, payload, error, *, kiosk=None, site=None, distance=None):
    try:
        with transaction.atomic():
            AttendanceAttempt.objects.get_or_create(
                request_id=payload["request_id"],
                defaults=_attempt_defaults(
                    employee,
                    action,
                    payload,
                    kiosk=kiosk,
                    site=site,
                    distance=distance,
                    code=error.code,
                    detail=error.detail,
                ),
            )
    except IntegrityError:
        pass


def _existing_attempt(employee, action, request_id):
    attempt = (
        AttendanceAttempt.objects.select_related("record").filter(request_id=request_id).first()
    )
    if not attempt:
        return None
    if attempt.employee_id != employee.pk or attempt.action != action:
        raise PunchError(
            "idempotency_conflict",
            "Request ID was already used for another attendance action.",
            409,
        )
    if not attempt.accepted:
        raise PunchError(
            attempt.reason_code or "rejected",
            attempt.reason_detail or "Attendance attempt was rejected.",
        )
    return attempt.record


def validate_punch_context(employee, payload, now):
    kiosk = None
    distance = None
    try:
        if not employee.is_active or not employee.user.is_active:
            raise PunchError(
                "inactive_employee", "Only active employees can record attendance.", 403
            )
        if employee.user.must_change_password:
            raise PunchError(
                "password_change_required",
                "Change your temporary password before recording attendance.",
                403,
            )
        if not employee.work_site.is_active or not employee.shift.is_active:
            raise PunchError("inactive_assignment", "Assigned work site or shift is inactive.")
        kiosk = parse_qr(payload["qr_token"])
        if kiosk.site_id != employee.work_site_id:
            raise PunchError("wrong_site", "This QR code is not for your assigned work site.")
        captured_at = payload["captured_at"]
        if captured_at > now + timedelta(seconds=settings.GPS_FUTURE_TOLERANCE_SECONDS):
            raise PunchError("future_location", "Location timestamp is ahead of server time.")
        if now - captured_at > timedelta(seconds=settings.GPS_FRESHNESS_SECONDS):
            raise PunchError(
                "stale_location",
                "Location reading is too old. Refresh your location and scan again.",
            )
        if float(payload["accuracy_meters"]) > settings.MAX_GPS_ACCURACY_METERS:
            raise PunchError(
                "poor_accuracy", "GPS accuracy is too low. Move to an open area and try again."
            )
        distance = haversine_meters(
            payload["latitude"],
            payload["longitude"],
            employee.work_site.latitude,
            employee.work_site.longitude,
        )
        if distance > employee.work_site.geofence_radius_meters:
            raise PunchError(
                "outside_geofence",
                f"You are {round(distance)} m from {employee.work_site.name}; the allowed radius is {employee.work_site.geofence_radius_meters} m.",
                kiosk=kiosk,
                distance=distance,
            )
        return kiosk, distance
    except PunchError as error:
        error.kiosk = error.kiosk or kiosk
        error.distance = error.distance if error.distance is not None else distance
        raise


def _process_punch(employee: Employee, action: str, payload):
    existing = _existing_attempt(employee, action, payload["request_id"])
    if existing:
        return existing, True

    now = timezone.now()
    kiosk = None
    distance = None
    try:
        kiosk, distance = validate_punch_context(employee, payload, now)
        if action == AttendanceAttempt.Action.CLOCK_IN:
            work_date = resolve_clock_in_date(employee, now)
            if not is_scheduled(employee, work_date):
                raise PunchError("not_scheduled", "You are not scheduled to work today.")
            if holiday_for(employee, work_date):
                raise PunchError("holiday", "Attendance is not required on this holiday.")
            if AdminException.objects.filter(employee=employee, date=work_date).exists():
                raise PunchError("excused", "An approved exception already covers this workday.")
            scheduled_start, scheduled_end = scheduled_bounds(employee, work_date)
            if now > scheduled_end:
                raise PunchError(
                    "shift_ended",
                    "This shift has already ended. Ask an administrator for a correction.",
                )
            with transaction.atomic():
                record = (
                    AttendanceRecord.objects.select_for_update()
                    .filter(employee=employee, work_date=work_date)
                    .first()
                )
                if (
                    AttendanceRecord.objects.filter(
                        employee=employee, clock_in__isnull=False, clock_out__isnull=True
                    )
                    .exclude(work_date=work_date)
                    .exists()
                ):
                    raise PunchError(
                        "open_shift",
                        "An earlier shift is still open. Ask an administrator to correct it before starting a new shift.",
                    )
                if record and record.clock_in:
                    raise PunchError(
                        "already_clocked_in", "You have already clocked in for this shift."
                    )
                if record and record.state == AttendanceRecord.State.EXCUSED:
                    raise PunchError(
                        "excused", "An approved exception already covers this workday."
                    )
                if not record:
                    record = AttendanceRecord(employee=employee, work_date=work_date)
                record.site = employee.work_site
                record.shift = employee.shift
                record.scheduled_start = scheduled_start
                record.scheduled_end = scheduled_end
                record.grace_minutes = employee.shift.grace_minutes
                record.clock_in = now
                record.state = record_state(now, scheduled_start, employee.shift.grace_minutes)
                record.missing_clock_out = False
                record.save()
                AttendanceAttempt.objects.create(
                    request_id=payload["request_id"],
                    **_attempt_defaults(
                        employee,
                        action,
                        payload,
                        kiosk=kiosk,
                        site=kiosk.site,
                        distance=distance,
                        accepted=True,
                        record=record,
                    ),
                )
                return record, False

        with transaction.atomic():
            record = (
                AttendanceRecord.objects.select_for_update()
                .filter(
                    employee=employee,
                    clock_in__isnull=False,
                    clock_out__isnull=True,
                    state__in=[AttendanceRecord.State.PRESENT, AttendanceRecord.State.LATE],
                )
                .order_by("-scheduled_start")
                .first()
            )
            if not record:
                raise PunchError("not_clocked_in", "No open clock-in was found.")
            if record.site_id != kiosk.site_id:
                raise PunchError("wrong_site", "Clock out at the same assigned work site.")
            record.clock_out = now
            record.worked_minutes = max(0, int((now - record.clock_in).total_seconds() // 60))
            record.missing_clock_out = False
            record.save(
                update_fields=["clock_out", "worked_minutes", "missing_clock_out", "updated_at"]
            )
            AttendanceAttempt.objects.create(
                request_id=payload["request_id"],
                **_attempt_defaults(
                    employee,
                    action,
                    payload,
                    kiosk=kiosk,
                    site=kiosk.site,
                    distance=distance,
                    accepted=True,
                    record=record,
                ),
            )
            return record, False
    except PunchError as error:
        error.kiosk = error.kiosk or kiosk
        error.distance = error.distance if error.distance is not None else distance
        raise


def process_punch(employee: Employee, action: str, payload):
    """Serialize every write for an employee, including first-punch creation.

    PostgreSQL locks the employee row; SQLite uses BEGIN IMMEDIATE. Rejections
    are written after rollback so a failed punch still has a durable audit.
    """
    for retry in range(6):
        try:
            with transaction.atomic():
                locked_employee = (
                    Employee.objects.select_for_update(of=("self",))
                    .select_related("user", "work_site", "shift")
                    .get(pk=employee.pk)
                )
                return _process_punch(locked_employee, action, payload)
        except OperationalError as error:
            if connection.vendor != "sqlite" or "locked" not in str(error).lower():
                raise
            if retry == 5:
                raise PunchError(
                    "busy", "Attendance is busy. Retry using the same request ID.", 503
                ) from error
            sleep(0.05 * (2**retry))
        except IntegrityError as error:
            existing = _existing_attempt(employee, action, payload["request_id"])
            if existing:
                return existing, True
            raise PunchError(
                "concurrent_conflict", "Attendance changed concurrently. Refresh your status.", 409
            ) from error
        except PunchError as error:
            # Conflicting IDs are already owned by another audited operation.
            if error.code != "idempotency_conflict":
                log_rejection(
                    employee,
                    action,
                    payload,
                    error,
                    kiosk=error.kiosk,
                    site=error.kiosk.site if error.kiosk else employee.work_site,
                    distance=error.distance,
                )
            raise
